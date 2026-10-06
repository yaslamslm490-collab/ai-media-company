"""Owner-triggered media generation through authorized SQLite account pools."""
from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from backend.integrations import IntegrationProblem, IntegrationStore

KLING_BASE = "https://api-singapore.klingai.com"
ELEVEN_BASE = "https://api.elevenlabs.io/v1"
MAX_ACCOUNT_ATTEMPTS = 20
MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_VIDEO_BYTES = 256 * 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PIPELINE_TEXT = 5000


class ProviderFailure(Exception):
    def __init__(self, status: int, code: str, message: str, *, pause_reason: str = "", pause_seconds: int | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.pause_reason = pause_reason
        self.pause_seconds = pause_seconds
        super().__init__(message)


class MediaGenerator:
    """Provider adapters. API credentials remain encrypted in IntegrationStore."""

    def __init__(self, integrations: IntegrationStore):
        self.integrations = integrations
        self.media_dir = Path(integrations.store.path).resolve().parent / "generated_media"
        self.media_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.media_dir, 0o700)
        except OSError:
            pass

    @staticmethod
    def _required_text(payload: dict[str, Any], name: str, maximum: int) -> str:
        value = payload.get(name)
        if not isinstance(value, str):
            raise IntegrationProblem(400, "invalid_generation_input", "أكمل حقول التوليد المطلوبة بنص صالح.")
        value = value.strip()
        if not value or len(value) > maximum or "\x00" in value:
            raise IntegrationProblem(400, "invalid_generation_input", f"الحقل {name} مطلوب وبحد أقصى {maximum} محرفاً.")
        return value

    @staticmethod
    def _safe_error_body(raw: bytes) -> dict[str, Any]:
        try:
            data = json.loads(raw[:MAX_RESPONSE_BYTES].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _error_detail(payload: dict[str, Any]) -> tuple[str, str]:
        detail = payload.get("detail")
        if isinstance(detail, dict):
            code = str(detail.get("code") or detail.get("status") or "")
            message = str(detail.get("message") or "")
            return code[:120], message[:500]
        code = str(payload.get("code") or payload.get("error_code") or "")
        message = str(payload.get("message") or "")
        return code[:120], message[:500]

    @staticmethod
    def _retry_after(headers: Any) -> int | None:
        value = headers.get("Retry-After") if headers else None
        if not value:
            return None
        try:
            return max(1, min(int(value), 86400))
        except (TypeError, ValueError):
            try:
                until = parsedate_to_datetime(value)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                return max(1, min(int((until - datetime.now(timezone.utc)).total_seconds()), 86400))
            except (TypeError, ValueError, OverflowError):
                return None

    @classmethod
    def _provider_failure(cls, provider: str, status: int, payload: dict[str, Any], headers: Any = None) -> ProviderFailure:
        code, _upstream_message = cls._error_detail(payload)
        normalized = code.casefold()
        kling_code = str(payload.get("code") or "") if provider == "kling" else ""
        if isinstance(payload.get("data"), dict) and not kling_code:
            kling_code = str(payload["data"].get("code") or "")
        if normalized in {"payment_required", "quota_exceeded", "insufficient_credits", "insufficient_quota"} or kling_code in {"1101", "1102"} or status == 402:
            return ProviderFailure(402, "credits_exhausted", "نفد رصيد الحساب أو انتهت حزمة موارده.", pause_reason="CREDITS_EXHAUSTED")
        if status in {401, 403}:
            auth_status = status
            return ProviderFailure(auth_status, "provider_auth_error", "رفض المزود الاعتماد أو إعدادات الحساب/الصلاحية.", pause_reason="AUTH_ERROR")
        if kling_code in {"1000", "1001", "1002", "1003", "1004", "1100", "1103", "1304"}:
            auth_status = 429 if kling_code in {"1100", "1304"} else 403 if kling_code == "1103" else 401
            return ProviderFailure(auth_status, "provider_auth_error", "رفض المزود الاعتماد أو إعدادات الحساب/الصلاحية.", pause_reason="AUTH_ERROR")
        if status == 429 or kling_code in {"1302", "1303"} or normalized in {"rate_limit_exceeded", "concurrent_limit_exceeded", "rate_limit_error"}:
            return ProviderFailure(429, "provider_rate_limited", "قيّد المزود الطلب (429)؛ أُوقف الحساب مؤقتاً وسيُجرّب حساب نشط آخر.",
                                   pause_reason="RATE_LIMITED", pause_seconds=cls._retry_after(headers) or 60)
        if normalized in {"quota_exceeded", "insufficient_credits", "payment_required"} or any(term in _upstream_message.casefold() for term in ("insufficient credits", "credits remaining", "quota exceeded", "out of credits")):
            return ProviderFailure(402, "credits_exhausted", "نفد رصيد الحساب أو انتهت حزمة موارده.", pause_reason="CREDITS_EXHAUSTED")
        safe_status = status if 400 <= status <= 599 else 502
        return ProviderFailure(safe_status, "provider_request_failed", f"رفض المزود الطلب (HTTP {safe_status})؛ راجع الحقول أو إعدادات الحساب.")

    def _read_json_request(self, request: Request, provider: str, *, timeout: int = 90) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise IntegrationProblem(502, "provider_response_too_large", "أعاد المزود استجابة أكبر من الحد المسموح.")
                payload = self._safe_error_body(raw)
                if not payload and raw.strip() not in (b"{}", b"null"):
                    raise IntegrationProblem(502, "provider_invalid_response", "تعذّر تفسير استجابة المزود.")
                if response.status >= 400 or payload.get("code") not in (None, 0, "0"):
                    raise self._provider_failure(provider, response.status, payload, response.headers)
                return payload
        except HTTPError as error:
            payload = self._safe_error_body(error.read(MAX_RESPONSE_BYTES))
            raise self._provider_failure(provider, error.code, payload, error.headers) from error
        except (URLError, TimeoutError, OSError) as error:
            raise IntegrationProblem(502, "provider_network_error", "تعذّر الوصول إلى المزود؛ لم يُجرَ تبديل تلقائي لأن نتيجة الطلب غير مؤكدة.") from error

    def _read_audio_request(self, request: Request) -> tuple[bytes, str]:
        try:
            with urlopen(request, timeout=120) as response:
                raw = response.read(MAX_AUDIO_BYTES + 1)
                if len(raw) > MAX_AUDIO_BYTES:
                    raise IntegrationProblem(502, "audio_result_too_large", "حجم ملف الصوت الناتج تجاوز 32 ميغابايت.")
                if response.status >= 400:
                    payload = self._safe_error_body(raw)
                    raise self._provider_failure("elevenlabs", response.status, payload, response.headers)
                mime = response.headers.get("Content-Type", "audio/mpeg").split(";", 1)[0].strip()
                if mime.startswith("application/json"):
                    raise self._provider_failure("elevenlabs", response.status, self._safe_error_body(raw), response.headers)
                if not mime.startswith("audio/"):
                    raise IntegrationProblem(502, "elevenlabs_invalid_audio", "لم يُعِد ElevenLabs ملفاً صوتياً صالحاً.")
                return raw, mime
        except HTTPError as error:
            payload = self._safe_error_body(error.read(MAX_RESPONSE_BYTES))
            raise self._provider_failure("elevenlabs", error.code, payload, error.headers) from error
        except (URLError, TimeoutError, OSError) as error:
            raise IntegrationProblem(502, "provider_network_error", "تعذّر الوصول إلى ElevenLabs؛ لم يُجرَ تبديل تلقائي لأن نتيجة الطلب غير مؤكدة.") from error

    def _with_rotation(self, *, service: str, provider: str, actor: str, call: Callable[[dict[str, Any], str], Any]) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        attempted: set[str] = set()
        paused: list[dict[str, Any]] = []
        last_failure: ProviderFailure | None = None
        while len(attempted) < MAX_ACCOUNT_ATTEMPTS:
            try:
                account = self.integrations.rotate_next(service, provider, actor)
            except IntegrationProblem as problem:
                if problem.code == "no_active_account":
                    break
                raise
            account_id = account["id"]
            if account_id in attempted:
                break
            attempted.add(account_id)
            credential = self.integrations._credential_for_dispatch(account_id)
            try:
                return call(account, credential), account, paused
            except ProviderFailure as failure:
                if not failure.pause_reason:
                    failure.details = {"paused_accounts": paused}
                    raise IntegrationProblem(failure.status, failure.code, failure.message, failure.details) from failure
                last_failure = failure
                paused_account = self.integrations.pause_for_failover(
                    account_id, reason=failure.pause_reason, pause_seconds=failure.pause_seconds, actor=actor
                )
                paused.append({
                    "id": account_id,
                    "label": account.get("label", "حساب"),
                    "provider": account.get("provider", provider),
                    "reason": failure.pause_reason,
                    "status": "PAUSED",
                    "pause_until": paused_account.get("pause_until") if paused_account else None,
                })
                continue
        if not attempted:
            raise IntegrationProblem(409, "no_active_account", f"لا يوجد حساب نشط مهيأ لمزود {provider} وخدمة {service}.")
        message = "أُوقفت الحسابات التي رفضت الطلب، ولا يوجد حساب نشط آخر لإكمال التوليد." if paused else "تعذّر إكمال التوليد."
        final_status = 429 if last_failure and last_failure.pause_reason == "RATE_LIMITED" else 402 if last_failure and last_failure.pause_reason == "CREDITS_EXHAUSTED" else last_failure.status if last_failure and last_failure.pause_reason == "AUTH_ERROR" else 409
        raise IntegrationProblem(final_status, "all_accounts_paused" if paused else "no_active_account", message,
                                 {"paused_accounts": paused, "last_failure": last_failure.code if last_failure else None})

    def _save_bytes(self, filename: str, content: bytes) -> str:
        if not re.fullmatch(r"[a-f0-9]{32}\.(mp3|mp4|wav|m4a)", filename):
            raise IntegrationProblem(500, "invalid_media_filename", "اسم ملف الوسائط الداخلي غير صالح.")
        self.media_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self.media_dir / filename
        temp = target.with_suffix(target.suffix + ".tmp")
        try:
            with temp.open("wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp, 0o600)
            temp.replace(target)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
        return filename

    def _new_job(self, *, kind: str, provider: str, prompt: str, params: dict[str, Any], actor: str) -> dict[str, Any]:
        return self.integrations.create_generation(kind=kind, provider=provider, prompt=prompt, params=params, actor=actor)

    def _call_elevenlabs(self, credential: str, *, voice_id: str, text: str, model_id: str, output_format: str) -> bytes:
        query = "?output_format=" + quote(output_format, safe="_")
        url = f"{ELEVEN_BASE}/text-to-speech/{quote(voice_id, safe='')}" + query
        body = json.dumps({"text": text, "model_id": model_id}, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers={"xi-api-key": credential, "Content-Type": "application/json", "Accept": "audio/mpeg"}, method="POST")
        content, _mime = self._read_audio_request(request)
        return content

    def _call_kling(self, credential: str, *, prompt: str, settings: dict[str, Any], external_task_id: str) -> dict[str, Any]:
        body = {"prompt": prompt, "settings": settings, "options": {"external_task_id": external_task_id}}
        request = Request(f"{KLING_BASE}/text-to-video/kling-3.0", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                          headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        payload = self._read_json_request(request, "kling")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not data["id"]:
            raise IntegrationProblem(502, "kling_invalid_task", "أعاد Kling رداً لا يحتوي معرّف مهمة صالحاً.")
        return data

    @staticmethod
    def _audio_args(payload: dict[str, Any]) -> tuple[str, str, str, str]:
        voice_id = MediaGenerator._required_text(payload, "voice_id", 120)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", voice_id):
            raise IntegrationProblem(400, "invalid_voice_id", "معرّف الصوت يحتوي أحرفاً غير مدعومة.")
        text = MediaGenerator._required_text(payload, "text", 5000)
        model_id = payload.get("model_id", "eleven_multilingual_v2")
        if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", model_id.strip()):
            raise IntegrationProblem(400, "invalid_model_id", "معرّف نموذج ElevenLabs غير صالح.")
        model_id = model_id.strip()
        output_format = payload.get("output_format", "mp3_44100_128")
        if output_format not in {"mp3_44100_128", "mp3_22050_32", "mp3_44100_192"}:
            raise IntegrationProblem(400, "invalid_output_format", "صيغة الصوت غير مدعومة في اللوحة.")
        return voice_id, text, model_id, output_format

    @staticmethod
    def _video_args(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        prompt = MediaGenerator._required_text(payload, "prompt", 3072)
        resolution = payload.get("resolution", "720p")
        aspect_ratio = payload.get("aspect_ratio", "16:9")
        duration = payload.get("duration", 5)
        audio = payload.get("audio", "off")
        if resolution not in {"720p", "1080p", "4k"} or aspect_ratio not in {"16:9", "9:16", "1:1"}:
            raise IntegrationProblem(400, "invalid_video_settings", "دقة الفيديو أو نسبة الأبعاد غير مدعومة.")
        try:
            duration = int(duration)
        except (TypeError, ValueError) as error:
            raise IntegrationProblem(400, "invalid_video_duration", "مدة Kling يجب أن تكون من 3 إلى 15 ثانية.") from error
        if duration not in range(3, 16) or audio not in {"off", "native"}:
            raise IntegrationProblem(400, "invalid_video_settings", "مدة Kling من 3 إلى 15 ثانية، وخيار الصوت غير صالح.")
        return prompt, {"resolution": resolution, "aspect_ratio": aspect_ratio, "duration": duration, "audio": audio, "multi_shot": False}

    def generate_audio(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        voice_id, text, model_id, output_format = self._audio_args(payload)
        job = self._new_job(kind="AUDIO", provider="elevenlabs", prompt=text,
                            params={"voice_id": voice_id, "model_id": model_id, "output_format": output_format}, actor=actor)
        paused: list[dict[str, Any]] = []
        try:
            content, account, paused = self._with_rotation(
                service="AUDIO", provider="elevenlabs", actor=actor,
                call=lambda selected, key: self._call_elevenlabs(key, voice_id=voice_id, text=text, model_id=model_id, output_format=output_format),
            )
            extension = "wav" if output_format.startswith("pcm_") else "mp3"
            filename = self._save_bytes(f"{job['id']}.{extension}", content)
            updated = self.integrations.update_generation(job["id"], actor=actor, status="COMPLETED", account_id=account["id"],
                                                          audio_file=filename, failover_json=json.dumps(paused, ensure_ascii=False))
            return updated or job
        except IntegrationProblem as problem:
            details = dict(problem.details)
            paused = details.get("paused_accounts", paused)
            self.integrations.update_generation(job["id"], actor=actor, status="FAILED", error_message=problem.message,
                                                failover_json=json.dumps(paused, ensure_ascii=False))
            problem.details = {**details, "generation_id": job["id"], "paused_accounts": paused}
            raise

    def generate_video(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        prompt, settings = self._video_args(payload)
        job = self._new_job(kind="VIDEO", provider="kling", prompt=prompt, params=settings, actor=actor)
        try:
            result, account, paused = self._with_rotation(
                service="VIDEO", provider="kling", actor=actor,
                call=lambda selected, key: self._call_kling(key, prompt=prompt, settings=settings, external_task_id=job["id"]),
            )
            updated = self.integrations.update_generation(job["id"], actor=actor, provider_task_id=result["id"],
                                                          external_task_id=job["id"], account_id=account["id"],
                                                          failover_json=json.dumps(paused, ensure_ascii=False))
            return updated or job
        except IntegrationProblem as problem:
            paused = problem.details.get("paused_accounts", [])
            self.integrations.update_generation(job["id"], actor=actor, status="FAILED", error_message=problem.message,
                                                failover_json=json.dumps(paused, ensure_ascii=False))
            problem.details = {**problem.details, "generation_id": job["id"]}
            raise

    def execute_pipeline(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        script_text = self._required_text(payload, "script_text", MAX_PIPELINE_TEXT)
        visual_prompt = self._required_text(payload, "visual_prompt", 3072)
        voice_id, _, model_id, output_format = self._audio_args({"voice_id": payload.get("voice_id"), "text": script_text,
                                                                  "model_id": payload.get("model_id", "eleven_multilingual_v2"),
                                                                  "output_format": payload.get("output_format", "mp3_44100_128")})
        video_settings = self._video_args({"prompt": visual_prompt, "duration": payload.get("duration", 15),
                                           "resolution": payload.get("resolution", "720p"), "aspect_ratio": payload.get("aspect_ratio", "16:9"),
                                           "audio": "off"})[1]
        params = {"voice_id": voice_id, "model_id": model_id, "output_format": output_format,
                  "video_settings": video_settings, "assembly": "ffmpeg_voiceover"}
        job = self._new_job(kind="PIPELINE", provider="pipeline", prompt=visual_prompt, params={**params, "script_text": script_text}, actor=actor)
        paused: list[dict[str, Any]] = []
        audio_file = ""
        try:
            audio_data, audio_account, newly_paused = self._with_rotation(
                service="AUDIO", provider="elevenlabs", actor=actor,
                call=lambda selected, key: self._call_elevenlabs(key, voice_id=voice_id, text=script_text, model_id=model_id, output_format=output_format),
            )
            paused.extend(newly_paused)
            extension = "wav" if output_format.startswith("pcm_") else "mp3"
            audio_file = self._save_bytes(f"{job['id']}.{extension}", audio_data)
            self.integrations.update_generation(job["id"], actor=actor, audio_account_id=audio_account["id"], audio_file=audio_file,
                                                failover_json=json.dumps(paused, ensure_ascii=False))
            video_data, video_account, newly_paused = self._with_rotation(
                service="VIDEO", provider="kling", actor=actor,
                call=lambda selected, key: self._call_kling(key, prompt=visual_prompt, settings=video_settings, external_task_id=job["id"]),
            )
            paused.extend(newly_paused)
            updated = self.integrations.update_generation(job["id"], actor=actor, status="PROCESSING",
                                                          video_account_id=video_account["id"], provider_task_id=video_data["id"],
                                                          external_task_id=job["id"], failover_json=json.dumps(paused, ensure_ascii=False))
            return updated or job
        except IntegrationProblem as problem:
            paused.extend(problem.details.get("paused_accounts", []))
            self.integrations.update_generation(job["id"], actor=actor, status="FAILED", error_message=problem.message,
                                                failover_json=json.dumps(paused, ensure_ascii=False))
            problem.details = {**problem.details, "generation_id": job["id"], "paused_accounts": paused,
                               "audio_url": f"/api/external-integrations/generations/{job['id']}/audio" if audio_file else None}
            raise

    @staticmethod
    def _download_video(url: str, target: Path) -> None:
        parsed = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise IntegrationProblem(502, "invalid_provider_media_url", "أعاد Kling رابط وسائط غير آمن.")
        request = Request(url, headers={"Accept": "video/mp4,application/octet-stream", "User-Agent": "AI-Media-OS/1.0"}, method="GET")
        try:
            with urlopen(request, timeout=120) as response, target.open("wb") as stream:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_VIDEO_BYTES:
                        raise IntegrationProblem(502, "video_result_too_large", "حجم فيديو Kling تجاوز حد التنزيل البالغ 256 ميغابايت.")
                    stream.write(chunk)
            os.chmod(target, 0o600)
        except HTTPError as error:
            raise IntegrationProblem(502, "video_download_failed", f"تعذّر تنزيل نتيجة Kling (HTTP {error.code}).") from error
        except (URLError, TimeoutError, OSError) as error:
            raise IntegrationProblem(502, "video_download_failed", "تعذّر تنزيل نتيجة الفيديو من رابط Kling المؤقت.") from error

    @staticmethod
    def _duration(path: Path) -> float:
        try:
            result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                                    capture_output=True, text=True, timeout=20, check=True)
            duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0))
            if duration <= 0:
                raise ValueError("invalid duration")
            return duration
        except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError) as error:
            raise IntegrationProblem(503, "media_probe_failed", "تعذّر فحص مدة ملفات الوسائط بواسطة ffprobe.") from error

    def _assemble_pipeline(self, generation_id: str, audio_filename: str, video_url: str) -> str:
        if not audio_filename or Path(audio_filename).name != audio_filename or not re.fullmatch(r"[a-f0-9]{32}\.(mp3|wav|m4a)", audio_filename):
            raise IntegrationProblem(500, "pipeline_audio_missing", "ملف الصوت الخاص بمهمة الإنتاج غير موجود.")
        audio_path = self.media_dir / audio_filename
        if not audio_path.is_file():
            raise IntegrationProblem(500, "pipeline_audio_missing", "تعذّر العثور على ملف الصوت الناتج.")
        temp_video = self.media_dir / f"{generation_id}.source.mp4"
        temp_output = self.media_dir / f"{generation_id}.final.tmp.mp4"
        final_output = self.media_dir / f"{generation_id}.mp4"
        try:
            self._download_video(video_url, temp_video)
            video_duration = self._duration(temp_video)
            audio_duration = self._duration(audio_path)
            target_duration = max(video_duration, audio_duration)
            video_pad = max(0.0, target_duration - video_duration)
            audio_pad = max(0.0, target_duration - audio_duration)
            filters = f"[0:v:0]tpad=stop_mode=clone:stop_duration={video_pad:.3f},format=yuv420p[v];[1:a:0]apad=pad_dur={audio_pad:.3f}[a]"
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(temp_video), "-i", str(audio_path),
                       "-filter_complex", filters, "-map", "[v]", "-map", "[a]", "-t", f"{target_duration:.3f}",
                       "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
                       "-movflags", "+faststart", str(temp_output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=360, check=False)
            if result.returncode != 0 or not temp_output.is_file() or temp_output.stat().st_size < 1024:
                raise IntegrationProblem(502, "media_assembly_failed", "تعذّر دمج الصوت والفيديو محلياً؛ احتُفظ بمخرجي الصوت والفيديو المنفصلين.")
            os.chmod(temp_output, 0o600)
            temp_output.replace(final_output)
            return final_output.name
        except subprocess.TimeoutExpired as error:
            raise IntegrationProblem(504, "media_assembly_timeout", "استغرق دمج الصوت والفيديو وقتاً أطول من الحد؛ احتُفظ بالمخرجات المنفصلة.") from error
        finally:
            for path in (temp_video, temp_output):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def poll_generation(self, generation_id: str, actor: str) -> dict[str, Any]:
        job = self.integrations.get_generation(generation_id)
        if job is None:
            raise IntegrationProblem(404, "generation_not_found", "مهمة التوليد غير موجودة.")
        if job["status"] != "PROCESSING" or job["kind"] not in {"VIDEO", "PIPELINE"}:
            return job
        account_id = job.get("video_account_id") if job["kind"] == "PIPELINE" else job.get("account_id")
        provider_task_id = job.get("provider_task_id")
        external_task_id = job.get("external_task_id") or generation_id
        if not account_id or not provider_task_id:
            raise IntegrationProblem(409, "generation_task_incomplete", "لم يُسجّل معرّف مهمة Kling بعد.")
        credential = self.integrations._credential_for_dispatch(account_id)
        query = quote(external_task_id, safe="")
        request = Request(f"{KLING_BASE}/tasks?external_task_ids={query}",
                          headers={"Authorization": f"Bearer {credential}", "Accept": "application/json"}, method="GET")
        try:
            payload = self._read_json_request(request, "kling", timeout=45)
        except ProviderFailure as failure:
            # A polling limit is transient; do not create another task. Permanent account errors
            # still pause the account and are surfaced to the owner.
            if failure.pause_reason in {"AUTH_ERROR", "CREDITS_EXHAUSTED"}:
                self.integrations.pause_for_failover(account_id, reason=failure.pause_reason, pause_seconds=None, actor=actor)
                return self.integrations.update_generation(generation_id, actor=actor, status="FAILED", error_message=failure.message) or job
            return self.integrations.update_generation(generation_id, actor=actor,
                                                        error_message="تعذّر فحص حالة Kling مؤقتاً؛ أعد المحاولة لاحقاً.") or job
        data = payload.get("data")
        task = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
        if not isinstance(task, dict):
            raise IntegrationProblem(502, "kling_task_missing", "لم يعثر Kling على نتيجة للمهمة المسجلة.")
        status = str(task.get("status") or "").casefold()
        if status in {"submitted", "processing", "pending"}:
            return self.integrations.update_generation(generation_id, actor=actor, error_message="المهمة قيد التنفيذ لدى Kling.") or job
        if status in {"failed", "error"}:
            message = str(task.get("message") or "فشل إنشاء الفيديو لدى Kling.")[:400]
            return self.integrations.update_generation(generation_id, actor=actor, status="FAILED", error_message=message) or job
        if status not in {"succeeded", "succeed", "completed"}:
            raise IntegrationProblem(502, "kling_unknown_task_status", "أعاد Kling حالة مهمة غير معروفة.")
        outputs = task.get("outputs") if isinstance(task.get("outputs"), list) else []
        video = next((item for item in outputs if isinstance(item, dict) and item.get("type") == "video" and item.get("url")), None)
        if not video:
            raise IntegrationProblem(502, "kling_video_output_missing", "اكتملت مهمة Kling دون رابط فيديو صالح.")
        video_url = str(video["url"])
        if job["kind"] == "PIPELINE":
            with self.integrations.store.connect() as db:
                stored = db.execute("SELECT audio_file FROM media_generation_jobs WHERE id=?", (generation_id,)).fetchone()
            audio_filename = stored["audio_file"] if stored else ""
            try:
                output_file = self._assemble_pipeline(generation_id, audio_filename, video_url)
            except IntegrationProblem as problem:
                # Keep task and audio usable even if local muxing fails.
                return self.integrations.update_generation(generation_id, actor=actor, status="FAILED", video_url=video_url,
                                                          error_message=problem.message) or job
            return self.integrations.update_generation(generation_id, actor=actor, status="COMPLETED", video_url=video_url,
                                                       output_file=output_file, error_message="") or job
        return self.integrations.update_generation(generation_id, actor=actor, status="COMPLETED", video_url=video_url,
                                                   error_message="") or job

    def media_path(self, generation_id: str, media_kind: str) -> tuple[Path, str] | None:
        job = self.integrations.get_generation(generation_id)
        if not job:
            return None
        with self.integrations.store.connect() as db:
            row = db.execute("SELECT audio_file,output_file FROM media_generation_jobs WHERE id=?", (generation_id,)).fetchone()
        if row is None:
            return None
        filename = row["audio_file"] if media_kind == "audio" else row["output_file"] if media_kind == "media" else ""
        if not filename or Path(filename).name != filename or not re.fullmatch(r"[a-f0-9]{32}\.(mp3|mp4|wav|m4a)", filename):
            return None
        path = self.media_dir / filename
        if not path.is_file():
            return None
        mime = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav" if filename.endswith(".wav") else "video/mp4"
        return path, mime
