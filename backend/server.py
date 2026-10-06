"""Same-origin HTTP server and REST API for the AI Media OS dashboard."""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from backend.modules import BUILDER_CAPABILITIES, MODULES
from backend.store import (
    APPROVAL_DECISIONS,
    TASK_PRIORITIES,
    TASK_STATUSES,
    Store,
)

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 1_000_000


class ApiProblem(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def load_local_env(root: Path = ROOT) -> None:
    """Load simple KEY=VALUE entries without overwriting the host environment."""
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"\'')
        if key and key not in os.environ:
            os.environ[key] = value


def _probe(url: str, token: str = "") -> str:
    if not url:
        return "NOT_CONFIGURED"
    headers = {"Accept": "application/json", "User-Agent": "AI-Media-OS-Health/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return "ONLINE" if 200 <= response.status < 300 else "OFFLINE"
    except urllib.error.HTTPError as error:
        return "ERROR" if error.code >= 500 else "OFFLINE"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return "OFFLINE"


def system_health(store: Store, owner_token: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    try:
        database_status = "ONLINE" if store.ping() else "ERROR"
    except Exception:
        database_status = "ERROR"

    ai_url = env.get("AI_ROUTER_HEALTH_URL", "").strip()
    ai_token = env.get("AI_ROUTER_API_KEY", "")
    manus_url = env.get("MANUS_HEALTH_URL", "").strip()
    manus_token = env.get("MANUS_API_TOKEN", "")
    github_token = env.get("GITHUB_TOKEN", "")
    github_url = (env.get("GITHUB_HEALTH_URL", "").strip() or "https://api.github.com/user") if github_token else ""

    external: dict[str, str] = {}
    raw_external = env.get("EXTERNAL_HEALTH_URLS", "").strip()
    if raw_external:
        try:
            candidates = json.loads(raw_external)
            if isinstance(candidates, dict):
                external = {str(name): str(url) for name, url in candidates.items() if str(name).strip() and str(url).strip()}
        except (json.JSONDecodeError, TypeError):
            external = {"configuration": ""}

    checks = {
        "backend": "ONLINE",
        "database": database_status,
        "authentication": "ONLINE" if owner_token else "NOT_CONFIGURED",
        "ai_router": _probe(ai_url, ai_token),
        "manus": _probe(manus_url, manus_token),
        "github": _probe(github_url, github_token),
        "external_integrations": ({name: _probe(url) for name, url in external.items()} if external else "NOT_CONFIGURED"),
    }
    statuses = [value for key, value in checks.items() if key not in {"authentication", "external_integrations"} and isinstance(value, str)]
    overall = "ERROR" if "ERROR" in statuses else ("OFFLINE" if "OFFLINE" in statuses else ("NOT_CONFIGURED" if checks["authentication"] == "NOT_CONFIGURED" else "ONLINE"))
    return {"overall": overall, "checks": checks, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}


def _bounded_text(payload: dict[str, Any], key: str, *, required: bool = False, maximum: int = 4000) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ApiProblem(400, "invalid_field", f"الحقل {key} يجب أن يكون نصاً.")
    value = value.strip()
    if required and not value:
        raise ApiProblem(400, "required_field", f"الحقل {key} مطلوب.")
    if len(value) > maximum:
        raise ApiProblem(400, "field_too_long", f"الحقل {key} أطول من المسموح.")
    return value


def make_handler(*, root: Path = ROOT, db_path: str | Path | None = None, owner_token: str | None = None):
    resolved_root = Path(root).resolve()
    resolved_db = Path(db_path or os.environ.get("AI_MEDIA_DB_PATH", resolved_root / "data" / "dashboard.sqlite3"))
    token = owner_token if owner_token is not None else os.environ.get("OWNER_API_TOKEN", "")
    if token and len(token) < 24:
        raise ValueError("OWNER_API_TOKEN must be at least 24 characters.")
    store = Store(resolved_db)
    store.initialize()

    class Handler(SimpleHTTPRequestHandler):
        server_version = "AI-Media-OS/1.0"

        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=str(resolved_root), **kwargs)

        def log_message(self, fmt: str, *args: Any) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ApiProblem(400, "invalid_content_length", "تعذّر قراءة حجم الطلب.") from error
            if length <= 0 or length > MAX_BODY:
                raise ApiProblem(413 if length > MAX_BODY else 400, "invalid_body_size", "حجم الطلب غير صالح.")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ApiProblem(400, "invalid_json", "جسم الطلب يجب أن يكون JSON صالحاً.") from error
            if not isinstance(payload, dict):
                raise ApiProblem(400, "invalid_body", "جسم الطلب يجب أن يكون كائناً.")
            return payload

        def _authenticate(self) -> str:
            if not token:
                raise ApiProblem(503, "auth_not_configured", "المصادقة غير مهيأة. اضبط OWNER_API_TOKEN على الخادم أولاً.")
            supplied = self.headers.get("X-Owner-Token", "")
            if not supplied:
                raise ApiProblem(401, "authentication_required", "يلزم رمز دخول المالك للوصول إلى بيانات مساحة العمل.")
            if not hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
                raise ApiProblem(401, "invalid_token", "رمز دخول المالك غير صالح.")
            return "owner"

        def _query(self) -> dict[str, str]:
            return {key: values[0] for key, values in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items() if values}

        def _body(self) -> dict[str, Any]:
            return self._read_json()

        def _api(self) -> bool:
            return urllib.parse.urlsplit(self.path).path.startswith("/api/")

        def _run(self, callback) -> None:
            try:
                result = callback()
                if result is not None:
                    self._send_json(200, result)
            except ApiProblem as problem:
                self._log_failure(problem.code, problem.message)
                self._send_json(problem.status, {"error": {"code": problem.code, "message": problem.message}})
            except ValueError as error:
                code = str(error)
                if code == "approval_already_decided":
                    self._log_failure(code, "approval_already_decided")
                    self._send_json(409, {"error": {"code": code, "message": "تم البت في هذا الطلب مسبقاً."}})
                else:
                    self._log_failure("invalid_request", "invalid_request")
                    self._send_json(400, {"error": {"code": "invalid_request", "message": "تعذّر تنفيذ الطلب."}})
            except Exception:
                self._log_failure("internal_error", "internal_error")
                self._send_json(500, {"error": {"code": "internal_error", "message": "حدث خطأ داخلي. راجع سجل الخادم."}})

        def _log_failure(self, code: str, message: str) -> None:
            supplied = self.headers.get("X-Owner-Token", "")
            if not token or not supplied or not hmac.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
                return
            path = urllib.parse.urlsplit(self.path).path
            pieces = path.strip("/").split("/")
            module = pieces[1] if len(pieces) > 1 else "system"
            try:
                with store.connect() as db:
                    store.log_activity(db, actor="owner", action="api.request_failed", module=module,
                                       object_type="request", object_id=path, status="FAILURE",
                                       result=code, error=message[:500])
            except Exception:
                pass

        def do_GET(self) -> None:
            if not self._api():
                return self._serve_static(include_body=True)
            self._run(self._get_api)

        def do_HEAD(self) -> None:
            if self._api():
                self._send_json(405, {"error": {"code": "method_not_allowed", "message": "الطريقة غير مسموحة."}})
                return
            self._serve_static(include_body=False)

        def _serve_static(self, *, include_body: bool) -> None:
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            relative = path.lstrip("/") or "index.html"
            target = (resolved_root / relative).resolve()
            allowed = (
                target == (resolved_root / "index.html").resolve()
                or (target.parent == resolved_root and target.name in {"styles.css", "manus-routes.json"})
                or (target.parent == (resolved_root / "frontend").resolve() and target.suffix == ".js")
            )
            if not allowed or not target.is_file():
                body = '{"error":{"code":"not_found","message":"المورد غير موجود."}}'.encode("utf-8")
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if include_body:
                    self.wfile.write(body)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type in {"text/html", "text/css", "text/javascript", "application/javascript", "application/json"}:
                content_type += "; charset=utf-8"
            size = target.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if include_body:
                with target.open("rb") as file:
                    self.wfile.write(file.read())

        def do_POST(self) -> None:
            if self._api():
                self._run(self._post_api)
            else:
                self._send_json(404, {"error": {"code": "not_found", "message": "المسار غير موجود."}})

        def do_PATCH(self) -> None:
            if self._api():
                self._run(self._patch_api)
            else:
                self._send_json(404, {"error": {"code": "not_found", "message": "المسار غير موجود."}})

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Allow", "GET, POST, PATCH, HEAD, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _get_api(self) -> dict[str, Any]:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                return system_health(store, token)
            if path == "/api/modules":
                return {"modules": MODULES, "builder_capabilities": BUILDER_CAPABILITIES}
            self._authenticate()
            query = self._query()
            if path == "/api/dashboard":
                health = system_health(store, token)
                return store.dashboard(health)
            if path == "/api/tasks":
                status = query.get("status", "").upper()
                if status and status not in TASK_STATUSES:
                    raise ApiProblem(400, "invalid_status", "حالة المهمة غير صالحة.")
                try:
                    limit = min(max(int(query.get("limit", "200")), 1), 500)
                except ValueError as error:
                    raise ApiProblem(400, "invalid_limit", "حد النتائج غير صالح.") from error
                return {"tasks": store.list_tasks(status=status, search=query.get("q", "")[:120], limit=limit), "statuses": sorted(TASK_STATUSES)}
            if path == "/api/approvals":
                status = query.get("status", "").upper()
                valid_statuses = {"WAITING_APPROVAL", "APPROVED", "REJECTED", "CHANGES_REQUESTED"}
                if status and status not in valid_statuses:
                    raise ApiProblem(400, "invalid_status", "حالة الموافقة غير صالحة.")
                return {"approvals": store.list_approvals(status=status, search=query.get("q", "")[:120])}
            decision_match = re.fullmatch(r"/api/approvals/([A-Za-z0-9_-]{1,80})/decisions", path)
            if decision_match:
                approval_id = decision_match.group(1)
                if store.get_approval(approval_id) is None:
                    raise ApiProblem(404, "approval_not_found", "طلب الموافقة غير موجود.")
                return {"decisions": store.list_approval_decisions(approval_id)}
            if path == "/api/activity":
                status = query.get("status", "").upper()
                if status and status not in {"SUCCESS", "FAILURE"}:
                    raise ApiProblem(400, "invalid_status", "حالة النشاط غير صالحة.")
                return {"activity": store.list_activity(search=query.get("q", "")[:120], status=status)}
            raise ApiProblem(404, "not_found", "مسار API غير موجود.")

        def _post_api(self) -> dict[str, Any] | None:
            path = urllib.parse.urlsplit(self.path).path
            actor = self._authenticate()
            payload = self._body()
            if path == "/api/tasks":
                title = _bounded_text(payload, "title", required=True, maximum=180)
                description = _bounded_text(payload, "description", maximum=4000)
                owner = _bounded_text(payload, "owner", maximum=120) or actor
                assigned = _bounded_text(payload, "assigned_employee", maximum=120)
                department = _bounded_text(payload, "department", maximum=120)
                priority = _bounded_text(payload, "priority", maximum=20).upper() or "NORMAL"
                status = _bounded_text(payload, "status", maximum=30).upper() or "TODO"
                if priority not in TASK_PRIORITIES:
                    raise ApiProblem(400, "invalid_priority", "أولوية المهمة غير صالحة.")
                if status not in TASK_STATUSES:
                    raise ApiProblem(400, "invalid_status", "حالة المهمة غير صالحة.")
                task = store.create_task({"title": title, "description": description, "owner": owner,
                                          "assigned_employee": assigned, "department": department,
                                          "priority": priority, "status": status}, actor)
                self._send_json(201, {"task": task})
                return None
            if path == "/api/approvals":
                title = _bounded_text(payload, "title", required=True, maximum=180)
                description = _bounded_text(payload, "description", maximum=4000)
                submitted_by = _bounded_text(payload, "submitted_by", maximum=120) or actor
                approval = store.create_approval({"title": title, "description": description, "submitted_by": submitted_by}, actor)
                self._send_json(201, {"approval": approval})
                return None
            raise ApiProblem(404, "not_found", "مسار API غير موجود.")

        def _patch_api(self) -> dict[str, Any]:
            path = urllib.parse.urlsplit(self.path).path
            actor = self._authenticate()
            payload = self._body()
            task_match = re.fullmatch(r"/api/tasks/([A-Za-z0-9_-]{1,80})", path)
            if task_match:
                status = _bounded_text(payload, "status", required=True, maximum=30).upper()
                if status not in TASK_STATUSES:
                    raise ApiProblem(400, "invalid_status", "حالة المهمة غير صالحة.")
                task = store.update_task_status(task_match.group(1), status, actor)
                if task is None:
                    raise ApiProblem(404, "task_not_found", "المهمة غير موجودة.")
                return {"task": task}
            approval_match = re.fullmatch(r"/api/approvals/([A-Za-z0-9_-]{1,80})", path)
            if approval_match:
                decision = _bounded_text(payload, "decision", required=True, maximum=30).upper()
                if decision not in APPROVAL_DECISIONS:
                    raise ApiProblem(400, "invalid_decision", "قرار الموافقة غير صالح.")
                note = _bounded_text(payload, "note", maximum=2000)
                if decision == "REQUEST_CHANGES" and not note:
                    raise ApiProblem(400, "note_required", "اكتب التعديلات المطلوبة قبل الإرسال.")
                approval = store.decide_approval(approval_match.group(1), decision, note, actor)
                if approval is None:
                    raise ApiProblem(404, "approval_not_found", "طلب الموافقة غير موجود.")
                return {"approval": approval}
            raise ApiProblem(404, "not_found", "مسار API غير موجود.")

    return Handler


def main() -> None:
    load_local_env()
    bind = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    handler = make_handler()
    server = ThreadingHTTPServer((bind, port), handler)
    print(f"AI Media OS listening at http://{bind}:{port}")
    print(f"Owner authentication: {'configured' if os.environ.get('OWNER_API_TOKEN') else 'NOT CONFIGURED (read-only health endpoint only)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
