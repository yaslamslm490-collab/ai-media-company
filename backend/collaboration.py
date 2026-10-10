"""Embedded collaboration tools for AI Media OS: MCP, canonical task records, and Manus API."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from backend.company_builder import _reject_secret_material
from backend.oauth import required_scopes
from backend.store import TASK_PRIORITIES, TASK_STATUSES, Store, new_id

MCP_PROTOCOL_VERSION = "2025-03-26"
MCP_PATH = "/mcp"
MANUS_WEBHOOK_PATH = "/api/collaboration/manus/webhook"
MAX_UPDATE_CHARS = 50_000
_WEBHOOK_KEY_CACHE: dict[str, Any] = {"pem": "", "expires": 0.0}
_WEBHOOK_KEY_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _bounded(value: Any, maximum: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_text")
    value = value.strip()
    if required and not value:
        raise ValueError("required_text")
    if len(value) > maximum:
        raise ValueError("text_too_long")
    return value


def manus_request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call only the official Manus API. Credentials are read from host environment."""
    api_key = os.environ.get("MANUS_API_KEY", "").strip() or os.environ.get("MANUS_API_TOKEN", "").strip()
    if not api_key:
        raise RuntimeError("manus_not_configured")
    if not path.startswith("/v2/"):
        raise RuntimeError("invalid_manus_path")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        "https://api.manus.ai" + path,
        data=data,
        headers={"Accept": "application/json", "x-manus-api-key": api_key,
                 **({"Content-Type": "application/json"} if data is not None else {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            result = json.loads(response.read(1_000_000).decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError("manus_upstream_rejected") from error
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("manus_upstream_unavailable") from error
    if not isinstance(result, dict) or result.get("ok") is False:
        raise RuntimeError("manus_invalid_response")
    return result


class Collaboration:
    def __init__(self, store: Store):
        self.store = store

    def status(self) -> dict[str, Any]:
        return {
            "application_tasks": "ONLINE" if self.store.ping() else "ERROR",
            "manus_api": "CONFIGURED" if (os.environ.get("MANUS_API_KEY", "").strip() or os.environ.get("MANUS_API_TOKEN", "").strip()) else "NOT_CONFIGURED",
            "mcp_endpoint": "CONFIGURED" if len(os.environ.get("NADA_MCP_TOKEN", "").strip()) >= 32 else "NOT_CONFIGURED",
            "public_https": "CONFIGURED" if self._webhook_url() else "NOT_CONFIGURED",
        }

    def list_tasks(self, status: str = "", query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        status = status.upper().strip()
        if status and status not in TASK_STATUSES:
            raise ValueError("invalid_status")
        return self.store.list_tasks(status=status, search=_bounded(query, 120), limit=min(max(int(limit), 1), 100))

    def create_task(self, title: str, description: str = "", priority: str = "NORMAL") -> dict[str, Any]:
        title = _bounded(title, 180, required=True)
        description = _bounded(description, 4000)
        _reject_secret_material(title, description)
        priority = priority.upper().strip()
        if priority not in TASK_PRIORITIES:
            raise ValueError("invalid_priority")
        return self.store.create_task({"title": title, "description": description, "priority": priority,
                                       "status": "TODO", "owner": "ChatGPT / MCP"}, "chatgpt")

    def update_task(self, task_id: str, status: str) -> dict[str, Any]:
        task_id = _bounded(task_id, 80, required=True)
        status = status.upper().strip()
        if status not in TASK_STATUSES:
            raise ValueError("invalid_status")
        item = self.store.update_task_status(task_id, status, "collaboration")
        if item is None:
            raise ValueError("task_not_found")
        return item

    def add_update(self, task_id: str, content: str, provider: str = "chatgpt", status: str = "NOTE",
                   external_ref: str = "") -> dict[str, Any]:
        task_id = _bounded(task_id, 80, required=True)
        content = _bounded(content, MAX_UPDATE_CHARS, required=True)
        _reject_secret_material(content)
        provider = provider.lower().strip()
        if provider not in {"chatgpt", "manus", "owner"}:
            raise ValueError("invalid_provider")
        if self.store.get_task(task_id) is None:
            raise ValueError("task_not_found")
        return self.store.add_collaboration_update(task_id, provider, status[:30], content,
                                                   _bounded(external_ref, 200))

    def task_updates(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        task_id = _bounded(task_id, 80, required=True)
        if self.store.get_task(task_id) is None:
            raise ValueError("task_not_found")
        return self.store.list_collaboration_updates(task_id, min(max(int(limit), 1), 100))

    def submit_to_manus(self, task_id: str) -> dict[str, Any]:
        task = self.store.get_task(_bounded(task_id, 80, required=True))
        if task is None:
            raise ValueError("task_not_found")
        _reject_secret_material(task.get("title", ""), task.get("description", ""))
        existing = self.store.get_collaboration_link(task["id"], "manus")
        if existing:
            return existing
        prompt = f"Task from NADA AI / AI Media OS\nTitle: {task['title']}\n\n{task.get('description', '')}\n\nReturn the result in your final response."
        response = manus_request("POST", "/v2/task.create", {
            "title": task["title"], "message": {"content": prompt},
            "share_visibility": "private", "interactive_mode": True,
        })
        remote_id = response.get("task_id")
        if not isinstance(remote_id, str) or not remote_id:
            raise RuntimeError("manus_task_id_missing")
        link = self.store.link_collaboration_task(task["id"], "manus", remote_id,
                                                  str(response.get("task_url") or f"https://manus.im/app/{remote_id}"), "running")
        self.add_update(task["id"], f"تم إرسال المهمة إلى Manus. معرّف المهمة: {remote_id}", "manus", "SUBMITTED", remote_id)
        return link

    def create_and_send_to_manus(self, title: str, description: str = "", priority: str = "NORMAL") -> dict[str, Any]:
        task = self.create_task(title, description, priority)
        try:
            link = self.submit_to_manus(task["id"])
        except Exception:
            self.add_update(task["id"], "تعذّر إرسال المهمة إلى Manus؛ بقيت محفوظة داخل NADA AI فقط.",
                            "owner", "SUBMISSION_FAILED", "manus-submit-failed:" + task["id"])
            raise
        return {"task": task, "manus_link": link}

    def reply_to_manus(self, task_id: str, content: str) -> dict[str, Any]:
        task_id = _bounded(task_id, 80, required=True)
        content = _bounded(content, 5000, required=True)
        link = self.store.get_collaboration_link(task_id, "manus")
        if not link:
            raise ValueError("manus_task_not_linked")
        response = manus_request("POST", "/v2/task.sendMessage", {
            "task_id": link["external_task_id"], "message": {"content": content},
        })
        self.add_update(task_id, content, "chatgpt", "REPLY_SENT", "reply:" + str(response.get("request_id", new_id())))
        self.store.update_collaboration_link(task_id, "manus", "running")
        return {"task_id": task_id, "manus_task_id": link["external_task_id"], "status": "running"}

    def sync_manus(self, task_id: str) -> dict[str, Any]:
        task_id = _bounded(task_id, 80, required=True)
        link = self.store.get_collaboration_link(task_id, "manus")
        if not link:
            raise ValueError("manus_task_not_linked")
        remote_id = link["external_task_id"]
        query = urllib.parse.urlencode({"task_id": remote_id})
        detail = manus_request("GET", "/v2/task.detail?" + query).get("task", {})
        messages_payload = manus_request("GET", "/v2/task.listMessages?" + urllib.parse.urlencode({"task_id": remote_id, "order": "desc", "limit": 20}))
        messages = messages_payload.get("messages", [])
        latest_result = ""
        latest_ref = ""
        for message in messages if isinstance(messages, list) else []:
            assistant = message.get("assistant_message") if isinstance(message, dict) else None
            content = assistant.get("content") if isinstance(assistant, dict) else ""
            if isinstance(content, str) and content.strip():
                latest_result = content[:MAX_UPDATE_CHARS]
                latest_ref = str(message.get("id") or "")
                break
        remote_status = str(detail.get("status") or "unknown").lower()
        background = detail.get("has_running_background_jobs")
        if remote_status == "error":
            local_status = "FAILED"
        elif remote_status == "waiting":
            local_status = "WAITING_APPROVAL"
        elif remote_status == "stopped" and background is False:
            local_status = "COMPLETED"
        elif remote_status == "running" or remote_status == "stopped":
            # Missing background-job state is unknown, not evidence of completion.
            local_status = "IN_PROGRESS"
        else:
            local_status = "IN_PROGRESS"
        if latest_result and latest_ref:
            self.add_update(task_id, latest_result, "manus", "RESULT", latest_ref)
        if local_status != task_status(self.store, task_id):
            self.store.update_task_status(task_id, local_status, "manus")
        updated_link = self.store.update_collaboration_link(task_id, "manus", remote_status)
        return {"task_id": task_id, "manus_task_id": remote_id, "manus_status": remote_status,
                "background_jobs": background if isinstance(background, bool) else "UNKNOWN",
                "task_status": local_status, "result_saved": bool(latest_result), "link": updated_link}

    def _webhook_url(self) -> str:
        base = (os.environ.get("PUBLIC_BASE_URL", "").strip() or os.environ.get("RENDER_EXTERNAL_URL", "").strip()).rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
            return ""
        return base + MANUS_WEBHOOK_PATH

    def register_webhook(self) -> dict[str, Any]:
        url = self._webhook_url()
        if not url:
            raise RuntimeError("public_https_url_required")
        payload = manus_request("GET", "/v2/webhook.list")
        existing = next((item for item in payload.get("data", []) if isinstance(item, dict) and item.get("url") == url and item.get("status") == "active"), None)
        if existing:
            return {"registered": True, "already_registered": True, "webhook_id": existing.get("id"), "url": url}
        created = manus_request("POST", "/v2/webhook.create", {"url": url}).get("webhook", {})
        return {"registered": bool(created.get("id")), "already_registered": False,
                "webhook_id": created.get("id"), "url": url}

    def verify_webhook(self, raw: bytes, signature_b64: str, timestamp: str, full_url: str) -> bool:
        try:
            stamp = int(timestamp)
            if abs(int(time.time()) - stamp) > 300:
                return False
            pem = os.environ.get("MANUS_WEBHOOK_PUBLIC_KEY", "").strip()
            if not pem:
                with _WEBHOOK_KEY_LOCK:
                    cached_pem = str(_WEBHOOK_KEY_CACHE["pem"])
                    cache_valid = float(_WEBHOOK_KEY_CACHE["expires"]) > time.monotonic()
                if cached_pem and cache_valid:
                    pem = cached_pem
                else:
                    pem = manus_request("GET", "/v2/webhook.publicKey").get("public_key", "")
                    if not isinstance(pem, str) or "BEGIN PUBLIC KEY" not in pem:
                        return False
                    with _WEBHOOK_KEY_LOCK:
                        _WEBHOOK_KEY_CACHE["pem"] = pem
                        _WEBHOOK_KEY_CACHE["expires"] = time.monotonic() + 3600
            signature = base64.b64decode(signature_b64, validate=True)
            signed = f"{timestamp}.{full_url}.{hashlib.sha256(raw).hexdigest()}".encode("utf-8")
            public_key = serialization.load_pem_public_key(pem.encode("utf-8"))
            public_key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
            return True
        except Exception:
            return False

    def receive_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = payload.get("event_id")
        event_type = payload.get("event_type")
        detail = payload.get("task_detail")
        if not isinstance(event_id, str) or not event_id or event_type not in {"task_created", "task_stopped"} or not isinstance(detail, dict):
            raise ValueError("invalid_webhook_payload")
        remote_id = detail.get("task_id")
        if not isinstance(remote_id, str) or not remote_id:
            raise ValueError("invalid_webhook_payload")
        link = self.store.get_collaboration_link_by_external("manus", remote_id)
        if not link:
            return {"accepted": True, "linked": False, "duplicate": False}
        if not self.store.record_collaboration_webhook_event(event_id, remote_id, event_type):
            return {"accepted": True, "linked": True, "duplicate": True, "result_saved": False}
        status = str(detail.get("stop_reason") or "running")
        message = detail.get("message")
        saved = False
        if isinstance(message, str) and message.strip():
            self.add_update(link["task_id"], message[:MAX_UPDATE_CHARS], "manus", "RESULT", event_id)
            saved = True
        if event_type == "task_stopped" and status == "ask":
            self.store.update_task_status(link["task_id"], "WAITING_APPROVAL", "manus")
            self.store.update_collaboration_link(link["task_id"], "manus", "waiting")
        elif event_type == "task_stopped" and status == "finish":
            # Do not infer completion from a webhook alone. A later authenticated sync checks
            # task.detail.has_running_background_jobs before setting COMPLETED.
            self.store.update_collaboration_link(link["task_id"], "manus", "stopped_unverified")
        return {"accepted": True, "linked": True, "duplicate": False, "result_saved": saved}


def task_status(store: Store, task_id: str) -> str:
    task = store.get_task(task_id)
    return str(task.get("status") if task else "")


TOOLS = [
    {"name": "list_work_tasks", "title": "List NADA AI tasks", "description": "Read tasks from the canonical NADA AI workspace.",
     "inputSchema": {"type": "object", "properties": {"status": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}}, "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "create_work_task", "title": "Create NADA AI task", "description": "Create a task in NADA AI's shared task database.",
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "string", "enum": sorted(TASK_PRIORITIES)}}, "required": ["title"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}},
    {"name": "update_work_task", "title": "Update NADA AI task status", "description": "Change the status of a task in the shared NADA AI workspace.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string", "enum": sorted(TASK_STATUSES)}}, "required": ["task_id", "status"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}},
    {"name": "add_work_update", "title": "Save collaboration result", "description": "Append a result or note to the shared task history in NADA AI.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "content": {"type": "string"}}, "required": ["task_id", "content"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}},
    {"name": "get_work_updates", "title": "Get collaboration history", "description": "Read saved collaboration updates for a NADA AI task.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["task_id"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}},
    {"name": "send_task_to_manus", "title": "Send NADA AI task to Manus", "description": "Submit a shared NADA AI task to the official Manus API and store its task ID in the same workspace.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "create_and_send_task_to_manus", "title": "Create and assign to Manus", "description": "Create one canonical NADA AI task and submit the same task to Manus; this starts external work and may consume Manus credits. Use only when requested.",
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}, "priority": {"type": "string", "enum": sorted(TASK_PRIORITIES)}}, "required": ["title"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "sync_manus_result", "title": "Sync Manus task result", "description": "Fetch an existing linked Manus task's real status and latest result, then save it in NADA AI. Completion is claimed only when Manus reports no background jobs.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "reply_to_manus", "title": "Reply to linked Manus task", "description": "Send a follow-up to the Manus task already linked to a NADA AI task.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "content": {"type": "string"}}, "required": ["task_id", "content"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
    {"name": "register_manus_webhook", "title": "Enable automatic Manus updates", "description": "Register the NADA AI HTTPS callback with Manus once. Does not create a duplicate URL registration.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}},
]


class MCPProblem(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


def handle_mcp(payload: dict[str, Any], authorization: str, service: Collaboration,
               *, granted_scopes: set[str] | None = None) -> tuple[int, dict[str, Any] | None]:
    """Stateless MCP Streamable HTTP JSON request handler."""
    if granted_scopes is None:
        expected = os.environ.get("NADA_MCP_TOKEN", "").strip()
        if len(expected) < 32:
            raise MCPProblem(503, "The embedded MCP endpoint is not configured.")
        supplied = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
        if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise MCPProblem(401, "Authentication is required.")
        granted_scopes = {"*"}
    method = payload.get("method")
    request_id = payload.get("id")
    if not isinstance(method, str):
        return 400, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid Request"}}
    if method.startswith("notifications/"):
        return 202, None
    if method == "initialize":
        result = {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}},
                  "serverInfo": {"name": "nada-ai-collaboration", "version": "1.0.0"},
                  "instructions": "NADA AI is the canonical task and result store. Use its task tools before creating duplicate work. Confirm consequential external actions with the user."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        if "*" not in granted_scopes and "tasks:read" not in granted_scopes:
            return 403, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32003, "message": "Insufficient scope: tasks:read"}}
        # Advertise available tools; every call still enforces its own scope and can trigger step-up OAuth.
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        name = params.get("name")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        required = required_scopes(str(name or ""))
        if required and "*" not in granted_scopes and not required.issubset(granted_scopes):
            requested = " ".join(sorted(required - granted_scopes))
            return 403, {"jsonrpc": "2.0", "id": request_id,
                         "error": {"code": -32003, "message": "Insufficient scope: " + requested}}
        try:
            value = _call_tool(service, str(name or ""), args)
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "structuredContent": value, "isError": False}
        except Exception as error:
            code = str(error)
            user_message = {
                "manus_not_configured": "Manus API is not configured on the application host.",
                "public_https_url_required": "Set PUBLIC_BASE_URL to the permanent HTTPS origin before registering the webhook.",
                "manus_task_not_linked": "This NADA AI task has no linked Manus task.",
                "task_not_found": "The NADA AI task was not found.",
            }.get(code, "The collaboration action could not be completed.")
            result = {"content": [{"type": "text", "text": user_message}], "isError": True}
    else:
        if request_id is None:
            return 202, None
        return 200, {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
    if request_id is None:
        return 202, None
    return 200, {"jsonrpc": "2.0", "id": request_id, "result": result}


def _call_tool(service: Collaboration, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "list_work_tasks":
        return {"tasks": service.list_tasks(str(args.get("status", "")), str(args.get("query", "")), args.get("limit", 50))}
    if name == "create_work_task":
        return {"task": service.create_task(args.get("title"), args.get("description", ""), args.get("priority", "NORMAL"))}
    if name == "update_work_task":
        return {"task": service.update_task(args.get("task_id"), args.get("status"))}
    if name == "add_work_update":
        return {"update": service.add_update(args.get("task_id"), args.get("content"), "chatgpt", "RESULT")}
    if name == "get_work_updates":
        return {"updates": service.task_updates(args.get("task_id"), args.get("limit", 50))}
    if name == "send_task_to_manus":
        return {"manus_link": service.submit_to_manus(args.get("task_id"))}
    if name == "create_and_send_task_to_manus":
        return service.create_and_send_to_manus(args.get("title"), args.get("description", ""), args.get("priority", "NORMAL"))
    if name == "sync_manus_result":
        return service.sync_manus(args.get("task_id"))
    if name == "reply_to_manus":
        return service.reply_to_manus(args.get("task_id"), args.get("content"))
    if name == "register_manus_webhook":
        return service.register_webhook()
    raise ValueError("tool_not_found")
