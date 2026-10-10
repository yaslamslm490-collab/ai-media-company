"""HTTP client for the separately deployed NADA AI Manus bridge."""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from typing import Any


class ManusBridgeError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


class ManusBridgeClient:
    """Small standard-library client; never logs tokens or upstream response bodies."""

    def _configuration(self) -> tuple[str, str]:
        base = os.environ.get("MANUS_BRIDGE_URL", "").strip().rstrip("/")
        token = os.environ.get("MANUS_BRIDGE_TOKEN", "").strip()
        if not base or not token:
            raise ManusBridgeError(503, "manus_bridge_not_configured", "اتصال Manus Bridge غير مهيأ على الخادم.")
        parsed = urlsplit(base)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme != "https" and not local_http) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ManusBridgeError(503, "manus_bridge_url_invalid", "عنوان Manus Bridge يجب أن يكون HTTPS صالحًا.")
        return base, token

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        base, token = self._configuration()
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}", "User-Agent": "NADA-AI-Backend/1.0"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ManusBridgeError(502, "manus_bridge_response_too_large", "استجابة Manus Bridge أكبر من الحد المسموح.")
                result = json.loads(raw.decode("utf-8"))
        except ManusBridgeError:
            raise
        except HTTPError as error:
            # Never forward upstream bodies: they can contain deployment details.
            if error.code == 404:
                raise ManusBridgeError(404, "manus_task_not_found", "مهمة Manus غير موجودة في الجسر.") from None
            if error.code == 400:
                raise ManusBridgeError(400, "manus_bridge_invalid_request", "رفض الجسر بيانات الطلب.") from None
            if error.code == 503:
                raise ManusBridgeError(503, "manus_bridge_not_ready", "الجسر أو Manus API غير جاهز حاليًا.") from None
            raise ManusBridgeError(502, "manus_bridge_upstream_error", "تعذّر إكمال الطلب عبر Manus Bridge.") from None
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ManusBridgeError(502, "manus_bridge_unavailable", "تعذّر الاتصال الآمن بـManus Bridge.") from None
        if not isinstance(result, dict):
            raise ManusBridgeError(502, "manus_bridge_invalid_response", "أعاد الجسر استجابة غير متوقعة.")
        return result

    @staticmethod
    def _task_id(task_id: str) -> str:
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task_id):
            raise ManusBridgeError(400, "invalid_manus_task_id", "معرّف مهمة Manus غير صالح.")
        return quote(task_id, safe="")

    def submit_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/tasks", payload)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/tasks/{self._task_id(task_id)}")

    def send_message(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/v1/tasks/{self._task_id(task_id)}/messages", payload)
