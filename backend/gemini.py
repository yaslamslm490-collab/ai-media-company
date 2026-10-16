"""Server-only Gemini adapter using Google's OpenAI-compatible endpoint."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
_MAX_RESPONSE_BYTES = 1_000_000


class GeminiError(Exception):
    """Safe, user-facing Gemini adapter error without credential material."""


class GeminiNotConfigured(GeminiError):
    pass


class GeminiRequestFailed(GeminiError):
    pass


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str
    model: str
    base_url: str = GEMINI_OPENAI_BASE_URL

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "GeminiConfig":
        env = environ if environ is not None else os.environ
        api_key = env.get("GEMINI_API_KEY", "").strip()
        model = env.get("GEMINI_MODEL", "").strip()
        if not api_key:
            raise GeminiNotConfigured("Gemini غير مهيأ: GEMINI_API_KEY غير مضبوط في بيئة الخادم.")
        if not model:
            raise GeminiNotConfigured("Gemini غير مهيأ: GEMINI_MODEL غير مضبوط في بيئة الخادم.")
        base_url = env.get("GEMINI_OPENAI_BASE_URL", GEMINI_OPENAI_BASE_URL).strip().rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise GeminiNotConfigured("عنوان Gemini غير صالح في إعدادات الخادم.")
        return cls(api_key=api_key, model=model, base_url=base_url)


class GeminiAdapter:
    def __init__(self, config: GeminiConfig, *, opener: Callable[..., Any] | None = None):
        self.config = config
        self._opener = opener or urllib.request.urlopen

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None, *, opener: Callable[..., Any] | None = None) -> "GeminiAdapter":
        return cls(GeminiConfig.from_env(environ), opener=opener)

    def chat(self, message: str | list[dict[str, str]], *, system_prompt: str = "") -> dict[str, str]:
        if isinstance(message, str):
            text = message.strip()
            conversation = [{"role": "user", "content": text}] if text else []
        elif isinstance(message, list):
            conversation = []
            for item in message[-20:]:
                if not isinstance(item, dict):
                    continue
                role, content = item.get("role"), item.get("content")
                if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
                    continue
                conversation.append({"role": role, "content": content.strip()[:4000]})
        else:
            conversation = []
        if not conversation or conversation[-1]["role"] != "user":
            raise GeminiRequestFailed("لم يُرسل نص صالح إلى Gemini.")
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.extend(conversation)
        payload = {"model": self.config.model, "messages": messages}
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "User-Agent": "NADA-AI-Media-OS/1.0",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=45) as response:
                raw = response.read(_MAX_RESPONSE_BYTES)
            result = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise GeminiRequestFailed(f"رفض Gemini الطلب (HTTP {error.code}).") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise GeminiRequestFailed("تعذّر الاتصال بخدمة Gemini.") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise GeminiRequestFailed("أعاد Gemini استجابة غير صالحة.") from error
        if not isinstance(result, dict):
            raise GeminiRequestFailed("أعاد Gemini استجابة غير صالحة.")
        choices = result.get("choices")
        content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        if not isinstance(content, str) or not content.strip():
            raise GeminiRequestFailed("لم يُعِد Gemini نصاً صالحاً.")
        return {"response": content[:12000], "model": self.config.model}
