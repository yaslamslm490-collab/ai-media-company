from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from email.message import Message
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
from backend.integrations import IntegrationStore  # noqa: E402
from backend.media_generators import MediaGenerator  # noqa: E402
from backend.server import make_handler  # noqa: E402
from backend.store import Store  # noqa: E402


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, content_type: str = "application/json"):
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1):
        if size < 0:
            return self.body
        content, self.body = self.body[:size], self.body[size:]
        return content


class MediaGenerationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "media.sqlite3"
        self.owner_token = "owner-test-token-with-more-than-24-chars"
        self.key = Fernet.generate_key().decode("ascii")
        self.env_patch = patch.dict(os.environ, {"AI_MEDIA_VAULT_KEY": self.key})
        self.env_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root=ROOT, db_path=self.db_path, owner_token=self.owner_token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.store = IntegrationStore(Store(self.db_path))

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.env_patch.stop()
        self.temp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None, *, authenticated: bool = True):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        if authenticated:
            headers["X-Owner-Token"] = self.owner_token
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else {}

    def add_account(self, label: str, provider: str, service: str):
        return self.request("POST", "/api/external-integrations/accounts", {
            "label": label,
            "provider": provider,
            "service": service,
            "credential": f"TEST_CREDENTIAL_{label}_0123456789abcdef",
        })

    def test_pipeline_submits_real_provider_shapes_and_persists_job(self):
        self.assertEqual(self.add_account("voice-one", "ElevenLabs", "AUDIO")[0], 201)
        self.assertEqual(self.add_account("video-one", "Kling", "VIDEO")[0], 201)
        audio = FakeResponse(b"simulated-mp3", "audio/mpeg")
        kling_payload = {"code": 0, "data": {"id": "kling-task-1", "status": "submitted"}}
        with patch("backend.media_generators.urlopen", side_effect=[audio, FakeResponse(json.dumps(kling_payload).encode())]) as outbound:
            status, result = self.request("POST", "/api/external-integrations/pipeline", {
                "script_text": "مرحبا بالعالم.",
                "visual_prompt": "مشهد سينمائي لواجهة مدينة مستقبلية عند الغروب.",
                "voice_id": "voice_abc123",
                "duration": 5,
                "resolution": "720p",
                "aspect_ratio": "16:9",
            })
        self.assertEqual(status, 200)
        job = result["generation"]
        self.assertEqual(job["kind"], "PIPELINE")
        self.assertEqual(job["status"], "PROCESSING")
        self.assertEqual(job["provider_task_id"], "kling-task-1")
        self.assertIsNotNone(job["audio_url"])
        self.assertIsNone(job["output_url"])
        self.assertEqual(outbound.call_count, 2)
        audio_request = outbound.call_args_list[0].args[0]
        kling_request = outbound.call_args_list[1].args[0]
        self.assertEqual(audio_request.get_method(), "POST")
        self.assertIn("/text-to-speech/voice_abc123", audio_request.full_url)
        self.assertTrue(any(name.lower() == "xi-api-key" for name in audio_request.headers))
        self.assertEqual(kling_request.get_method(), "POST")
        self.assertIn("/text-to-video/kling-3.0", kling_request.full_url)
        kling_body = json.loads(kling_request.data)
        self.assertEqual(kling_body["settings"]["audio"], "off")
        self.assertNotIn("audioUrl", kling_body)
        self.assertNotIn("credential", json.dumps(result))
        self.assertNotIn("TEST_CREDENTIAL", json.dumps(result))

    def test_rate_limit_pauses_first_account_notifies_and_fails_over(self):
        self.assertEqual(self.add_account("voice-first", "ElevenLabs", "AUDIO")[0], 201)
        self.assertEqual(self.add_account("voice-second", "ElevenLabs", "AUDIO")[0], 201)
        rate_limited = HTTPError("https://api.elevenlabs.io", 429, "Too Many Requests", {"Retry-After": "120"}, io.BytesIO(b'{"detail":{"status":"rate_limit_exceeded"}}'))
        with patch("backend.media_generators.urlopen", side_effect=[rate_limited, FakeResponse(b"simulated-mp3", "audio/mpeg")]):
            status, result = self.request("POST", "/api/external-integrations/generate/audio", {
                "text": "نص صوت تجريبي.", "voice_id": "voice_abc123", "model_id": "eleven_multilingual_v2",
            })
        self.assertEqual(status, 200)
        generation = result["generation"]
        self.assertEqual(generation["status"], "COMPLETED")
        self.assertEqual(len(generation["paused_accounts"]), 1)
        self.assertEqual(generation["paused_accounts"][0]["reason"], "RATE_LIMITED")
        self.assertTrue(generation["paused_accounts"][0]["pause_until"])
        self.assertNotEqual(generation["account_id"], generation["paused_accounts"][0]["id"])
        snapshot = self.store.snapshot()
        paused_accounts = [account for account in snapshot["accounts"] if account["status"] == "PAUSED"]
        self.assertEqual(len(paused_accounts), 1)
        paused = paused_accounts[0]
        self.assertEqual(paused["status"], "PAUSED")
        self.assertEqual(paused["pause_reason"], "RATE_LIMITED")
        self.assertEqual(snapshot["generation_adapters"]["AUDIO"], "READY")

    def test_auth_rejection_pauses_account_and_preserves_http_status(self):
        self.assertEqual(self.add_account("voice-invalid", "ElevenLabs", "AUDIO")[0], 201)
        auth_error = HTTPError("https://api.elevenlabs.io", 401, "Unauthorized", {}, io.BytesIO(b'{"detail":{"code":"invalid_api_key"}}'))
        with patch("backend.media_generators.urlopen", side_effect=[auth_error]):
            status, result = self.request("POST", "/api/external-integrations/generate/audio", {
                "text": "اختبار مصادقة.", "voice_id": "voice_abc123",
            })
        self.assertEqual(status, 401)
        self.assertEqual(result["error"]["code"], "all_accounts_paused")
        self.assertEqual(result["error"]["details"]["paused_accounts"][0]["reason"], "AUTH_ERROR")
        account = self.store.snapshot()["accounts"][0]
        self.assertEqual(account["status"], "PAUSED")
        self.assertEqual(account["connection_status"], "AUTH_ERROR")

    def test_generation_and_audio_file_require_owner_authentication(self):
        status, _ = self.request("POST", "/api/external-integrations/generate/audio", {
            "text": "test", "voice_id": "voice_abc123",
        }, authenticated=False)
        self.assertEqual(status, 401)
        status, not_found = self.request("GET", "/api/external-integrations/generations/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/audio", authenticated=False)
        self.assertEqual(status, 401)
        self.assertEqual(not_found["error"]["code"], "authentication_required")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/ffprobe are not installed")
    def test_pipeline_assembly_muxes_audio_and_video_tracks(self):
        self.store.initialize()
        generator = MediaGenerator(self.store)
        source_video = Path(self.temp.name) / "source.mp4"
        source_audio = Path(self.temp.name) / "voice.mp3"
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=160x90:r=24:d=1", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source_video)],
                       check=True, timeout=30)
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=1", "-codec:a", "libmp3lame", "-q:a", "8", str(source_audio)],
                       check=True, timeout=30)
        generation_id = "a" * 32
        audio_name = generator._save_bytes(f"{generation_id}.mp3", source_audio.read_bytes())
        with patch.object(generator, "_download_video", side_effect=lambda _url, target: shutil.copyfile(source_video, target)):
            result_name = generator._assemble_pipeline(generation_id, audio_name, "https://cdn.klingai.com/result.mp4")
        output = generator.media_dir / result_name
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(output)],
                               capture_output=True, text=True, timeout=20, check=True)
        stream_types = {stream["codec_type"] for stream in json.loads(probe.stdout)["streams"]}
        self.assertEqual(stream_types, {"video", "audio"})


if __name__ == "__main__":
    unittest.main()
