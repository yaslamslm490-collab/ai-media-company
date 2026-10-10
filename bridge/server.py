"""Secure REST bridge between ChatGPT Actions and Manus API v2."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API_BASE = "https://api.manus.ai"
WEBHOOK_PATH = "/webhooks/manus"
MAX_BODY_BYTES = 1_000_000
MAX_PROMPT_CHARS = 18_000
MAX_FOLLOWUP_CHARS = 8_000
_KEY_CACHE_SECONDS = 3600
_KEY_CACHE: dict[str, Any] = {"pem": "", "expires": 0.0}
_KEY_CACHE_LOCK = threading.Lock()


class BridgeProblem(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_environment() -> None:
    """Load bridge/.env without overriding non-empty host environment values."""
    env_file = Path(os.environ.get("BRIDGE_ENV_FILE", Path(__file__).with_name(".env"))).expanduser()
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and (key not in os.environ or not os.environ[key]):
            os.environ[key] = value


def database_path() -> Path:
    return Path(os.environ.get("BRIDGE_DB_PATH", "./data/manus_bridge.sqlite3")).expanduser()


def connect_db() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize_db() -> None:
    with closing(connect_db()) as db:
        db.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS bridge_tasks (
                task_id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                task_url TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'accepted',
                stop_reason TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL DEFAULT '',
                attachments_json TEXT NOT NULL DEFAULT '[]',
                structured_output_json TEXT NOT NULL DEFAULT 'null',
                last_event_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS bridge_tasks_updated_idx ON bridge_tasks(updated_at DESC);
            """
        )
        db.commit()


def _manus_key() -> str:
    return os.environ.get("MANUS_API_KEY", "").strip() or os.environ.get("MANUS_API_TOKEN", "").strip()


def manus_request(method: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    key = _manus_key()
    if not key:
        raise BridgeProblem(503, "manus_api_not_configured", "Manus API credential is not configured on the bridge host.")
    headers = {"Accept": "application/json", "User-Agent": "NADA-AI-Manus-Bridge/1.0", "x-manus-api-key": key}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(API_BASE + route, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise BridgeProblem(502, "manus_api_error", f"Manus API returned HTTP {error.code}.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise BridgeProblem(502, "manus_api_unavailable", "Manus API request failed or returned invalid JSON.") from None
    if not isinstance(result, dict):
        raise BridgeProblem(502, "manus_api_invalid_response", "Manus API returned an unexpected response.")
    if result.get("ok") is False:
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        code = str(error.get("code", "manus_api_error"))[:80]
        raise BridgeProblem(502, code, "Manus API rejected the request.")
    return result


def configured_connectors() -> list[str]:
    return [item.strip() for item in os.environ.get("MANUS_CONNECTOR_IDS", "").split(",") if item.strip()]


def submit_task(data: dict[str, Any]) -> dict[str, Any]:
    prompt = data.get("prompt")
    title = data.get("title", "")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        raise BridgeProblem(400, "invalid_prompt", f"prompt must be non-empty and at most {MAX_PROMPT_CHARS} characters.")
    if not isinstance(title, str) or len(title) > 120:
        raise BridgeProblem(400, "invalid_title", "title must be a string of at most 120 characters.")

    message: dict[str, Any] = {"content": prompt.strip()}
    connectors = configured_connectors()
    if connectors:
        message["connectors"] = connectors
    request_data: dict[str, Any] = {
        "message": message,
        "locale": os.environ.get("MANUS_LOCALE", "ar").strip() or "ar",
        "share_visibility": "private",
    }
    if title.strip():
        request_data["title"] = title.strip()
    project_id = os.environ.get("MANUS_PROJECT_ID", "").strip()
    if project_id:
        request_data["project_id"] = project_id

    result = manus_request("POST", "/v2/task.create", request_data)
    task_id = result.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise BridgeProblem(502, "missing_task_id", "Manus accepted an unexpected response without a task ID.")
    title_result = str(result.get("task_title") or title.strip())
    task_url = str(result.get("task_url") or "")
    stamp = now_iso()
    with closing(connect_db()) as db:
        db.execute(
            """INSERT INTO bridge_tasks(task_id,title,task_url,status,created_at,updated_at)
               VALUES(?,?,?,'running',?,?)
               ON CONFLICT(task_id) DO UPDATE SET
                 title=CASE WHEN excluded.title='' THEN bridge_tasks.title ELSE excluded.title END,
                 task_url=CASE WHEN excluded.task_url='' THEN bridge_tasks.task_url ELSE excluded.task_url END,
                 status=CASE WHEN bridge_tasks.status='accepted' THEN 'running' ELSE bridge_tasks.status END,
                 updated_at=excluded.updated_at""",
            (task_id, title_result, task_url, stamp, stamp),
        )
        current = db.execute("SELECT status FROM bridge_tasks WHERE task_id=?", (task_id,)).fetchone()
        db.commit()
    return {"task_id": task_id, "task_title": title_result, "task_url": task_url, "status": str(current["status"])}


def send_followup(task_id: str, data: dict[str, Any]) -> dict[str, Any]:
    content = data.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > MAX_FOLLOWUP_CHARS:
        raise BridgeProblem(400, "invalid_content", f"content must be non-empty and at most {MAX_FOLLOWUP_CHARS} characters.")
    with closing(connect_db()) as db:
        known_task = db.execute("SELECT 1 FROM bridge_tasks WHERE task_id=?", (task_id,)).fetchone()
    if known_task is None:
        raise BridgeProblem(404, "task_not_found", "Only tasks created or received by this bridge can be continued.")
    result = manus_request("POST", "/v2/task.sendMessage", {"task_id": task_id, "message": {"content": content.strip()}})
    stamp = now_iso()
    with closing(connect_db()) as db:
        db.execute("UPDATE bridge_tasks SET status='running', stop_reason='', updated_at=? WHERE task_id=?", (stamp, task_id))
        db.commit()
    return {"task_id": str(result.get("task_id", task_id)), "status": "running"}


def webhook_url() -> str:
    base = os.environ.get("BRIDGE_PUBLIC_URL", "").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise BridgeProblem(503, "public_https_url_required", "Set BRIDGE_PUBLIC_URL to the public HTTPS origin of this service.")
    return base + WEBHOOK_PATH


def _manus_webhook_public_key() -> str:
    now = time.monotonic()
    with _KEY_CACHE_LOCK:
        if _KEY_CACHE.get("pem") and float(_KEY_CACHE.get("expires", 0)) > now:
            return str(_KEY_CACHE["pem"])
    result = manus_request("GET", "/v2/webhook.publicKey")
    pem = result.get("public_key")
    if not isinstance(pem, str) or "BEGIN PUBLIC KEY" not in pem:
        raise BridgeProblem(502, "webhook_public_key_missing", "Manus API did not return a usable webhook public key.")
    with _KEY_CACHE_LOCK:
        _KEY_CACHE["pem"] = pem
        _KEY_CACHE["expires"] = now + _KEY_CACHE_SECONDS
    return pem


def verify_webhook_signature(public_key_pem: str, url: str, body: bytes, signature_b64: str, timestamp: str, *, now: int | None = None) -> bool:
    try:
        ts = int(timestamp)
        current = int(time.time()) if now is None else now
        if abs(current - ts) > 300:
            return False
        signature = base64.b64decode(signature_b64, validate=True)
        body_hash = hashlib.sha256(body).hexdigest()
        signed = f"{timestamp}.{url}.{body_hash}".encode("utf-8")
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        public_key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        return True
    except (ValueError, TypeError, InvalidSignature, Exception):
        return False


def record_webhook_event(event: dict[str, Any]) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    detail = event.get("task_detail")
    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str) or not isinstance(detail, dict):
        raise BridgeProblem(400, "invalid_webhook_payload", "Webhook payload is missing required fields.")
    if event_type not in {"task_created", "task_stopped"}:
        raise BridgeProblem(400, "unsupported_webhook_event", "Webhook event type is not supported.")
    task_id = detail.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise BridgeProblem(400, "invalid_webhook_payload", "Webhook task ID is missing.")

    title = str(detail.get("task_title") or "")[:200]
    task_url = str(detail.get("task_url") or "")[:1000]
    stop_reason = str(detail.get("stop_reason") or "")[:40]
    message = str(detail.get("message") or "")[:50_000]
    attachments = detail.get("attachments") if isinstance(detail.get("attachments"), list) else []
    structured = detail.get("structured_output")
    if event_type == "task_created":
        status = "running"
    elif stop_reason == "ask":
        status = "waiting_for_input"
    elif stop_reason == "finish":
        status = "stopped_unverified"
    else:
        status = "stopped_unverified"
    stamp = now_iso()

    with closing(connect_db()) as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO webhook_events(event_id,task_id,event_type,received_at) VALUES(?,?,?,?)",
            (event_id[:200], task_id[:200], event_type, stamp),
        )
        if cursor.rowcount == 0:
            return False
        db.execute(
            """INSERT INTO bridge_tasks(task_id,title,task_url,status,stop_reason,message,attachments_json,
                   structured_output_json,last_event_id,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(task_id) DO UPDATE SET
                 title=CASE WHEN excluded.title='' THEN bridge_tasks.title ELSE excluded.title END,
                 task_url=CASE WHEN excluded.task_url='' THEN bridge_tasks.task_url ELSE excluded.task_url END,
                 status=CASE WHEN excluded.status='running' AND bridge_tasks.status IN ('completed','waiting_for_input')
                             THEN bridge_tasks.status ELSE excluded.status END,
                 stop_reason=excluded.stop_reason,
                 message=CASE WHEN excluded.message='' THEN bridge_tasks.message ELSE excluded.message END,
                 attachments_json=excluded.attachments_json,
                 structured_output_json=excluded.structured_output_json,
                 last_event_id=excluded.last_event_id,
                 updated_at=excluded.updated_at""",
            (
                task_id[:200], title, task_url, status, stop_reason, message,
                json.dumps(attachments, ensure_ascii=False),
                json.dumps(structured, ensure_ascii=False), event_id[:200], stamp, stamp,
            ),
        )
        db.commit()
    return True


def _refresh_completion(task: dict[str, Any]) -> dict[str, Any]:
    if task["status"] not in {"stopped_unverified", "running_background", "completion_unknown"}:
        return task
    detail = manus_request("GET", "/v2/task.detail?task_id=" + task["task_id"])
    remote = detail.get("task") if isinstance(detail.get("task"), dict) else {}
    has_background = remote.get("has_running_background_jobs")
    remote_status = str(remote.get("status") or "").lower()
    if remote_status == "error":
        new_status = "failed"
    elif remote_status == "waiting" or task["stop_reason"] == "ask":
        new_status = "waiting_for_input"
    elif remote_status == "running":
        new_status = "running"
    elif has_background is True:
        new_status = "running_background"
    elif remote_status == "stopped" and has_background is False and task["stop_reason"] == "finish":
        new_status = "completed"
    else:
        new_status = "completion_unknown"
    stamp = now_iso()
    with closing(connect_db()) as db:
        db.execute("UPDATE bridge_tasks SET status=?,updated_at=? WHERE task_id=?", (new_status, stamp, task["task_id"]))
        db.commit()
    task["status"] = new_status
    task["updated_at"] = stamp
    return task


def get_task(task_id: str) -> dict[str, Any]:
    if not task_id or len(task_id) > 200 or not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
        raise BridgeProblem(400, "invalid_task_id", "task_id is invalid.")
    with closing(connect_db()) as db:
        row = db.execute("SELECT * FROM bridge_tasks WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        raise BridgeProblem(404, "task_not_found", "No task with that ID is registered in this bridge.")
    task = dict(row)
    task = _refresh_completion(task)
    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "task_url": task["task_url"],
        "status": task["status"],
        "stop_reason": task["stop_reason"],
        "message": task["message"],
        "attachments": json.loads(task["attachments_json"] or "[]"),
        "structured_output": json.loads(task["structured_output_json"] or "null"),
        "last_event_id": task["last_event_id"],
        "updated_at": task["updated_at"],
    }


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    token = os.environ.get("BRIDGE_API_TOKEN", "").strip()
    if not token:
        handler.send_json(503, {"error": {"code": "bridge_auth_not_configured", "message": "Bridge API authentication is not configured."}})
        return False
    header = handler.headers.get("Authorization", "")
    scheme, _, supplied = header.partition(" ")
    if scheme.lower() != "bearer" or not supplied or not hmac.compare_digest(supplied.strip(), token):
        handler.send_json(401, {"error": {"code": "unauthorized", "message": "Valid Bearer token required."}})
        return False
    return True


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "NADA-Manus-Bridge/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep request bodies, headers, and secret values out of access logs.
        print(f"{self.log_date_time_string()} {self.client_address[0]} {fmt % args}")

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> tuple[bytes, dict[str, Any]]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            raise BridgeProblem(400, "invalid_content_length", "Content-Length is invalid.") from None
        if length < 0 or length > MAX_BODY_BYTES:
            raise BridgeProblem(413, "body_too_large", "Request body exceeds the configured limit.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BridgeProblem(400, "invalid_json", "Request body must be valid UTF-8 JSON.") from None
        if not isinstance(payload, dict):
            raise BridgeProblem(400, "invalid_json", "Request body must be a JSON object.")
        return raw, payload

    def do_GET(self) -> None:  # noqa: N802
        try:
            path = urlsplit(self.path).path
            if path == "/health":
                try:
                    initialize_db()
                    database_ok = True
                except (OSError, sqlite3.Error):
                    database_ok = False
                self.send_json(200 if database_ok else 503, {
                    "status": "ok" if database_ok else "error",
                    "database_ready": database_ok,
                    "manus_api_configured": bool(_manus_key()),
                    "chatgpt_auth_configured": bool(os.environ.get("BRIDGE_API_TOKEN", "").strip()),
                    "webhook_url_configured": bool(os.environ.get("BRIDGE_PUBLIC_URL", "").strip()),
                })
                return
            if not _authorized(self):
                return
            match = re.fullmatch(r"/v1/tasks/([A-Za-z0-9_-]+)", path)
            if match:
                self.send_json(200, get_task(match.group(1)))
                return
            self.send_json(404, {"error": {"code": "not_found", "message": "Route not found."}})
        except BridgeProblem as problem:
            self.send_json(problem.status, {"error": {"code": problem.code, "message": problem.message}})
        except (sqlite3.Error, OSError, ValueError):
            self.send_json(500, {"error": {"code": "internal_error", "message": "The bridge could not complete the request."}})

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlsplit(self.path).path
            if path == WEBHOOK_PATH:
                raw, payload = self.read_json()
                if urlsplit(self.path).query:
                    raise BridgeProblem(400, "webhook_query_not_supported", "Webhook URL query parameters are not supported.")
                signature = self.headers.get("X-Webhook-Signature", "")
                timestamp = self.headers.get("X-Webhook-Timestamp", "")
                if not signature or not timestamp:
                    raise BridgeProblem(400, "missing_signature", "Manus webhook signature headers are required.")
                try:
                    public_key = _manus_webhook_public_key()
                    canonical_url = webhook_url()
                except BridgeProblem as problem:
                    self.send_json(problem.status, {"error": {"code": problem.code, "message": problem.message}})
                    return
                if not verify_webhook_signature(public_key, canonical_url, raw, signature, timestamp):
                    raise BridgeProblem(401, "invalid_signature", "Webhook signature verification failed.")
                if payload.get("event_type") not in {"task_created", "task_stopped"}:
                    # Manus may send a signed setup/verification event before activating a webhook.
                    self.send_json(200, {"accepted": True, "ignored": True})
                    return
                inserted = record_webhook_event(payload)
                self.send_json(200, {"accepted": True, "duplicate": not inserted})
                return

            if not _authorized(self):
                return
            raw, payload = self.read_json()
            if path == "/v1/tasks":
                task = submit_task(payload)
                self.send_json(202, task)
                return
            match = re.fullmatch(r"/v1/tasks/([A-Za-z0-9_-]+)/messages", path)
            if match:
                task = send_followup(match.group(1), payload)
                self.send_json(202, task)
                return
            self.send_json(404, {"error": {"code": "not_found", "message": "Route not found."}})
        except BridgeProblem as problem:
            self.send_json(problem.status, {"error": {"code": problem.code, "message": problem.message}})
        except (sqlite3.Error, OSError, ValueError):
            self.send_json(500, {"error": {"code": "internal_error", "message": "The bridge could not complete the request."}})


def make_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    initialize_db()
    return ThreadingHTTPServer(
        (host or os.environ.get("HOST", "0.0.0.0"), port if port is not None else int(os.environ.get("PORT", "8123"))),
        BridgeHandler,
    )


def main() -> None:
    load_environment()
    server = make_server()
    print(f"NADA AI Manus bridge listening on {server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
