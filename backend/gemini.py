"""Google Gemini server-side integration for NADA AI.

The API key is read only from the server environment and is sent in the
x-goog-api-key header. This module never logs credentials or prompt contents.
"""
from __future__ import annotations

import json
import base64
import binascii
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]{1,120}$")
_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProblem(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def configuration(environ: dict[str, str] | None = None) -> dict[str, str | bool]:
    env = environ if environ is not None else os.environ
    key = env.get("GEMINI_API_KEY", "").strip()
    model = env.get("GEMINI_MODEL", "").strip()
    if model.startswith("models/"):
        model = model[len("models/"):]
    base_url = (env.get("GEMINI_BASE_URL", "").strip() or _DEFAULT_BASE_URL).rstrip("/")
    valid_model = bool(model and _MODEL_PATTERN.fullmatch(model))
    return {
        "configured": bool(key and valid_model),
        "has_key": bool(key),
        "model": model,
        "base_url": base_url,
        "model_valid": valid_model,
    }


def _request_json(url: str, *, api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "NADA-AI-MEDIA-OS/1.0",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(1_000_000)
        result = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            raise GeminiProblem(502, "gemini_auth_failed", "رفض Gemini اعتماد الخادم؛ تحقق من GEMINI_API_KEY.") from error
        if error.code == 429:
            raise GeminiProblem(502, "gemini_rate_limited", "رفض Gemini الطلب بسبب حد الاستخدام؛ لم تُسجّل العملية كنجاح.") from error
        raise GeminiProblem(502, "gemini_request_failed", f"رفض Gemini الطلب (HTTP {error.code})؛ لم تُسجّل العملية كنجاح.") from error
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GeminiProblem(502, "gemini_unavailable", "تعذّر الاتصال بـ Gemini أو قراءة استجابته؛ لم تُسجّل العملية كنجاح.") from error
    if not isinstance(result, dict):
        raise GeminiProblem(502, "gemini_invalid_response", "أعاد Gemini استجابة غير صالحة؛ لم تُسجّل العملية كنجاح.")
    return result


def generate_content(message: str, *, system_instruction: str = "", attachment_base64: str = "", attachment_type: str = "", environ: dict[str, str] | None = None) -> dict[str, str]:
    env = environ if environ is not None else os.environ
    config = configuration(env)
    if not config["has_key"]:
        raise GeminiProblem(503, "gemini_key_not_configured", "Gemini غير مهيأ: أضف GEMINI_API_KEY إلى أسرار الخادم.")
    if not config["model_valid"]:
        raise GeminiProblem(503, "gemini_model_not_configured", "Gemini غير مهيأ: أضف GEMINI_MODEL صالحًا إلى إعدادات الخادم.")
    model = str(config["model"])
    url = f"{config['base_url']}/models/{urllib.parse.quote(model, safe='')}:generateContent"
    parts: list[dict[str, Any]] = [{"text": message}]
    if attachment_base64:
        encoded = attachment_base64.split(",", 1)[1] if attachment_base64.startswith("data:") and "," in attachment_base64 else attachment_base64
        try:
            base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise GeminiProblem(400, "gemini_invalid_attachment", "المرفق ليس Base64 صالحًا؛ لم يُرسل إلى Gemini.") from error
        mime_type = attachment_type.split(";", 1)[0].strip().lower() or "application/octet-stream"
        parts.append({"inlineData": {"mimeType": mime_type[:120], "data": encoded}})
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "text/plain"},
    }
    if system_instruction.strip():
        body["systemInstruction"] = {"parts": [{"text": system_instruction.strip()}]}
    result = _request_json(url, api_key=str(env.get("GEMINI_API_KEY", "").strip()), body=body)
    candidates = result.get("candidates")
    parts = candidates[0].get("content", {}).get("parts", []) if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else []
    text = "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)).strip()
    if not text:
        raise GeminiProblem(502, "gemini_empty_response", "لم يُعد Gemini نصًا صالحًا؛ لم تُسجّل العملية كنجاح.")
    return {"response": text[:12000], "model": model}
