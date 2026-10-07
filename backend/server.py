"""Same-origin HTTP server and REST API for the AI Media OS dashboard."""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import sqlite3
import sys
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from backend.modules import BUILDER_CAPABILITIES, MODULES
from backend.company_builder import (
    EMPLOYEE_STATUSES,
    EMPLOYEE_TYPES,
    EMPLOYEE_MODULE_IDS,
    PRIORITIES as COMPANY_PRIORITIES,
    TOOL_STATUSES,
    WORKFLOW_STATUSES,
    CompanyBuilderStore,
    _reject_secret_material,
)
from backend.store import (
    APPROVAL_DECISIONS,
    TASK_PRIORITIES,
    TASK_STATUSES,
    Store,
)
from backend.integrations import IntegrationProblem, IntegrationStore
from backend.media_generators import MediaGenerator

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 1_000_000


class ApiProblem(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def load_local_env(root: Path = ROOT) -> None:
    """Load simple KEY=VALUE entries, filling missing or empty host values only."""
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"\'')
        if key and (key not in os.environ or not os.environ[key]):
            os.environ[key] = value


def _probe(url: str, token: str = "", *, auth_header: str = "Authorization", auth_scheme: str = "Bearer ") -> str:
    if not url:
        return "NOT_CONFIGURED"
    headers = {"Accept": "application/json", "User-Agent": "AI-Media-OS-Health/1.0"}
    if token:
        headers[auth_header] = f"{auth_scheme}{token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return "ONLINE" if 200 <= response.status < 300 else "OFFLINE"
    except urllib.error.HTTPError as error:
        return "ERROR" if error.code >= 500 else "OFFLINE"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return "OFFLINE"


def _probe_github_cli() -> str:
    """Verify the host's existing gh auth without exposing the account or token."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
        return "ONLINE" if result.returncode == 0 and result.stdout.strip() else "OFFLINE"
    except FileNotFoundError:
        return "NOT_CONFIGURED"
    except (OSError, subprocess.TimeoutExpired):
        return "OFFLINE"


def system_health(store: Store, owner_token: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    try:
        database_status = "ONLINE" if store.ping() else "ERROR"
    except Exception:
        database_status = "ERROR"

    ai_url = env.get("AI_ROUTER_HEALTH_URL", "").strip()
    ai_token = env.get("AI_ROUTER_API_KEY", "")
    if not ai_url:
        router_base = (env.get("AI_ROUTER_BASE_URL", "") or env.get("OPENAI_API_BASE", "")).strip().rstrip("/")
        ai_token = ai_token or env.get("OPENAI_API_KEY", "")
        if router_base:
            ai_url = f"{router_base}/models"
    manus_url = env.get("MANUS_HEALTH_URL", "").strip()
    manus_token = env.get("MANUS_API_TOKEN", "") or env.get("MANUS_API_KEY", "")
    if not manus_url and manus_token:
        manus_url = "https://api.manus.ai/v2/task.list?limit=1"
    github_token = env.get("GITHUB_TOKEN", "")
    github_url = (env.get("GITHUB_HEALTH_URL", "").strip() or "https://api.github.com/user") if github_token else ""
    use_github_cli = env.get("GITHUB_USE_CLI", "").strip().lower() in {"1", "true", "yes"}

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
        "manus": _probe(manus_url, manus_token, auth_header="x-manus-api-key", auth_scheme=""),
        "github": _probe(github_url, github_token) if github_token else (_probe_github_cli() if use_github_cli else "NOT_CONFIGURED"),
        "external_integrations": ({name: _probe(url) for name, url in external.items()} if external else "NOT_CONFIGURED"),
    }
    statuses = [value for key, value in checks.items() if key not in {"authentication", "external_integrations"} and isinstance(value, str)]
    overall = "ERROR" if "ERROR" in statuses else (
        "OFFLINE" if "OFFLINE" in statuses else (
            "NOT_CONFIGURED" if "NOT_CONFIGURED" in statuses or checks["authentication"] == "NOT_CONFIGURED" else "ONLINE"
        )
    )
    return {"overall": overall, "checks": checks, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}


def module_catalog(store: Store, owner_token: str) -> list[dict[str, Any]]:
    health = system_health(store, owner_token)
    live_state = {
        "ai-team": "READY",
        "characters": "READY" if store.count_active("characters") else "NOT_CONFIGURED",
        "projects": "READY" if store.count_active("projects") else "NOT_CONFIGURED",
        "ai-router": health["checks"]["ai_router"],
        "manus": health["checks"]["manus"],
        "github": health["checks"]["github"],
    }
    return [{**module, "state": live_state.get(module["id"], module["state"]),
             "employee_accessible": module["id"] in EMPLOYEE_MODULE_IDS} for module in MODULES]


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


def _bounded_list(payload: dict[str, Any], key: str, *, maximum_items: int = 100, maximum_item: int = 180) -> list[str]:
    value = payload.get(key, [])
    if isinstance(value, str):
        value = [part.strip() for part in value.splitlines() if part.strip()]
    if not isinstance(value, list) or len(value) > maximum_items:
        raise ApiProblem(400, "invalid_list", f"قائمة {key} غير صالحة.")
    clean: list[str] = []
    for item in value:
        if not isinstance(item, str) or len(item.strip()) > maximum_item:
            raise ApiProblem(400, "invalid_list_item", f"عنصر في {key} غير صالح.")
        text = item.strip()
        if text and text not in clean:
            clean.append(text)
    return clean


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _router_json_request(url: str, *, token: str = "", body: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json", "User-Agent": "AI-Media-OS/1.0"}
    data = None
    method = "GET"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(1_000_000)
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise ApiProblem(502, "ai_router_invalid_response", "أعاد موجّه النماذج استجابة غير صالحة.")
        return result
    except urllib.error.HTTPError as error:
        raise ApiProblem(502, "ai_router_request_failed", f"رفض موجّه النماذج الطلب (HTTP {error.code}).") from error
    except ApiProblem:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApiProblem(502, "ai_router_unavailable", "تعذّر الاتصال بموجّه النماذج أو قراءة استجابته.") from error


def _employee_ai_response(employee: dict[str, Any], message: str, company_store: CompanyBuilderStore) -> dict[str, str]:
    env = os.environ
    key = env.get("AI_ROUTER_API_KEY", "") or env.get("OPENAI_API_KEY", "")
    chat_url = env.get("AI_ROUTER_CHAT_COMPLETIONS_URL", "").strip()
    base = (env.get("AI_ROUTER_BASE_URL", "") or env.get("OPENAI_API_BASE", "")).strip().rstrip("/")
    if not base:
        health_url = env.get("AI_ROUTER_HEALTH_URL", "").strip()
        if health_url.endswith("/models"):
            base = health_url[:-len("/models")].rstrip("/")
    if not chat_url and base:
        chat_url = f"{base}/chat/completions"
    if not chat_url:
        raise ApiProblem(503, "ai_router_not_configured", "موجّه النماذج غير مهيأ. لم يتم توليد إجابة تجريبية.")

    model = (employee.get("preferred_model") or "").strip()
    if not model and base:
        models_payload = _router_json_request(f"{base}/models", token=key)
        models = models_payload.get("data", [])
        model = next((item.get("id", "") for item in models if isinstance(item, dict) and re.fullmatch(r"[A-Za-z0-9._:/-]{1,120}", str(item.get("id", "")))), "") if isinstance(models, list) else ""
    if not model:
        raise ApiProblem(503, "ai_router_model_unconfigured", "لم يعثر موجّه النماذج على نموذج صالح للاختبار.")

    source_context = company_store.authorized_knowledge_context(employee["id"])
    context = "\n\n".join(f"[{source['name']}]\n{source['content']}" for source in source_context)
    system_prompt = (employee.get("system_prompt") or "").strip()
    if not system_prompt:
        system_prompt = f"أنت {employee['name']}، دورك {employee.get('role','مساعد AI')}. أجب بدقة وفق الوصف والمهام المصرح بها فقط."
    if context:
        system_prompt += "\n\nمراجع معرفة مصرح بها لهذا الموظف:\n" + context
    primary = model
    fallback = (employee.get("fallback_model") or "").strip()
    payload = {"model": primary, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": message}]}
    try:
        result = _router_json_request(chat_url, token=key, body=payload)
    except ApiProblem:
        if not fallback or fallback == primary:
            raise
        payload["model"] = fallback
        result = _router_json_request(chat_url, token=key, body=payload)
        primary = fallback
    choices = result.get("choices")
    content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ApiProblem(502, "ai_router_empty_response", "لم يُعِد موجّه النماذج نصاً صالحاً للاختبار.")
    return {"response": content[:12000], "model": primary}


def make_handler(*, root: Path = ROOT, db_path: str | Path | None = None, owner_token: str | None = None):
    project_root = Path(root).resolve()
    configured_static = os.environ.get("AI_MEDIA_STATIC_ROOT", "").strip()
    built_static = project_root / "dist"
    static_root = Path(configured_static).resolve() if configured_static else (built_static if (built_static / "index.html").is_file() else project_root)
    resolved_db = Path(db_path or os.environ.get("AI_MEDIA_DB_PATH", project_root / "data" / "dashboard.sqlite3"))
    master_password = os.environ.get("OWNER_MASTER_PASSWORD", "")
    token = owner_token if owner_token is not None else (master_password or os.environ.get("OWNER_API_TOKEN", ""))
    if owner_token is None and master_password and not re.fullmatch(r"[0-9]{6}", master_password):
        raise ValueError("OWNER_MASTER_PASSWORD must contain exactly six digits.")
    if token and len(token) < 6:
        raise ValueError("OWNER_MASTER_PASSWORD or OWNER_API_TOKEN must be at least 6 characters.")
    store = Store(resolved_db)
    store.initialize()
    company_store = CompanyBuilderStore(store)
    company_store.initialize()
    integration_store = IntegrationStore(store)
    integration_store.initialize()
    media_generator = MediaGenerator(integration_store)

    class Handler(SimpleHTTPRequestHandler):
        server_version = "AI-Media-OS/1.0"

        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=str(static_root), **kwargs)

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
                raise ApiProblem(503, "auth_not_configured", "المصادقة غير مهيأة. اضبط OWNER_MASTER_PASSWORD أو OWNER_API_TOKEN على الخادم أولاً.")
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
            except IntegrationProblem as problem:
                self._log_failure(problem.code, problem.message)
                envelope = {"error": {"code": problem.code, "message": problem.message}}
                if problem.details:
                    envelope["error"]["details"] = problem.details
                self._send_json(problem.status, envelope)
            except ValueError as error:
                code = str(error)
                messages = {
                    "approval_already_decided": "تم البت في هذا الطلب مسبقاً.",
                    "department_has_employees": "لا يمكن حذف قسم يضم موظفين.",
                    "department_has_tasks": "لا يمكن حذف قسم مرتبط بمهام.",
                    "employee_has_dependents": "لا يمكن حذف موظف له مهام أو تقارير مباشرة.",
                    "role_has_employees": "لا يمكن حذف دور مستخدم من موظفين.",
                    "system_role_protected": "لا يمكن حذف دور نظام أساسي.",
                    "manager_department_mismatch": "يجب أن يكون المدير في القسم نفسه؛ غيّر القسم والمدير معاً.",
                    "department_manager_mismatch": "اختر مديراً نشطاً من القسم نفسه؛ أنشئ المدير أولاً ثم عيّنه.",
                    "parent_department_mismatch": "يجب أن يكون الموظف الأعلى في القسم نفسه.",
                    "manager_must_be_active_manager": "اختر مدير AI نشطاً للموظف.",
                    "employee_not_active": "لا يمكن تكليف موظف متوقف أو غير نشط بمهمة.",
                    "employee_cannot_create_task": "لا يملك هذا الموظف صلاحية إنشاء المهام.",
                    "secret_in_tool_reference": "لا تحفظ مفاتيح أو أسراراً في مرجع الأداة.",
                    "workflow_steps_required": "أضف خطوة واحدة على الأقل لسير العمل.",
                    "organization_cycle": "لا يمكن أن يؤدي التغيير إلى دورة في الهيكل التنظيمي.",
                    "invalid_reference": "يشير الطلب إلى سجل غير موجود.",
                    "secret_material_rejected": "يبدو أن النص يحتوي على مفتاح أو رمز اعتماد؛ لا تحفظ الأسرار في قاعدة البيانات.",
                    "invalid_employee_module": "إحدى الوحدات المختارة غير مسموح تعيينها إلى موظف ذكاء اصطناعي.",
                }
                conflict_codes = {"approval_already_decided", "department_has_employees", "department_has_tasks", "employee_has_dependents", "role_has_employees", "system_role_protected"}
                self._log_failure(code if code in messages else "invalid_request", code if code in messages else "invalid_request")
                self._send_json(409 if code in conflict_codes else 400, {
                    "error": {"code": code if code in messages else "invalid_request", "message": messages.get(code, "تعذّر تنفيذ الطلب أو أن بعض حقوله غير صالحة.")}
                })
            except sqlite3.IntegrityError:
                self._log_failure("data_conflict", "data_conflict")
                self._send_json(409, {"error": {"code": "data_conflict", "message": "يتعارض هذا السجل مع قيمة أو علاقة موجودة."}})
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
            media_match = re.fullmatch(r"/api/external-integrations/generations/([a-f0-9]{32})/(audio|media)", urllib.parse.urlsplit(self.path).path)
            if media_match:
                return self._serve_generated_media(media_match.group(1), media_match.group(2))
            self._run(self._get_api)

        def _serve_generated_media(self, generation_id: str, media_kind: str) -> None:
            try:
                self._authenticate()
                media = media_generator.media_path(generation_id, media_kind)
                if media is None:
                    raise ApiProblem(404, "media_not_found", "ملف الوسائط غير متوفر أو انتهت صلاحيته المحلية.")
                path, content_type = media
                size = path.stat().st_size
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(size))
                self.send_header("Cache-Control", "private, no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Disposition", "inline")
                self.end_headers()
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        self.wfile.write(chunk)
            except ApiProblem as problem:
                self._log_failure(problem.code, problem.message)
                self._send_json(problem.status, {"error": {"code": problem.code, "message": problem.message}})
            except IntegrationProblem as problem:
                self._log_failure(problem.code, problem.message)
                self._send_json(problem.status, {"error": {"code": problem.code, "message": problem.message}})
            except OSError:
                self._send_json(404, {"error": {"code": "media_not_found", "message": "ملف الوسائط غير متوفر."}})

        def do_HEAD(self) -> None:
            if self._api():
                self._send_json(405, {"error": {"code": "method_not_allowed", "message": "الطريقة غير مسموحة."}})
                return
            self._serve_static(include_body=False)

        def _serve_static(self, *, include_body: bool) -> None:
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            relative = path.lstrip("/") or "index.html"
            target = (static_root / relative).resolve()
            allowed = (
                target == (static_root / "index.html").resolve()
                or (target.parent == static_root and target.name in {"styles.css", "manus-routes.json", "app.js"})
                or (target.parent == (static_root / "frontend").resolve() and target.suffix == ".js")
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

        def do_DELETE(self) -> None:
            if self._api():
                self._run(self._delete_api)
            else:
                self._send_json(404, {"error": {"code": "not_found", "message": "المسار غير موجود."}})

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Allow", "GET, POST, PATCH, DELETE, HEAD, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _get_api(self) -> dict[str, Any]:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/health":
                return system_health(store, token)
            if path == "/api/modules":
                return {"modules": module_catalog(store, token), "builder_capabilities": BUILDER_CAPABILITIES}
            self._authenticate()
            query = self._query()
            if path == "/api/dashboard":
                health = system_health(store, token)
                dashboard = store.dashboard(health)
                dashboard["company_builder"] = company_store.summary()
                return dashboard
            if path == "/api/company-builder/summary":
                return {"summary": company_store.summary()}
            if path == "/api/company/structure":
                return company_store.company_structure()
            if path == "/api/departments":
                return {"departments": company_store.list_departments()}
            if path == "/api/ai-employees":
                employee_type = query.get("type", "").upper()
                status = query.get("status", "").upper()
                if employee_type and employee_type not in EMPLOYEE_TYPES:
                    raise ApiProblem(400, "invalid_employee_type", "نوع الموظف غير صالح.")
                if status and status not in EMPLOYEE_STATUSES:
                    raise ApiProblem(400, "invalid_employee_status", "حالة الموظف غير صالحة.")
                return {"employees": company_store.list_employees(employee_type=employee_type, status=status, search=query.get("q", "")[:120])}
            employee_match = re.fullmatch(r"/api/ai-employees/([A-Za-z0-9_-]{1,80})", path)
            if employee_match:
                profile = company_store.employee_profile(employee_match.group(1))
                if profile is None:
                    raise ApiProblem(404, "employee_not_found", "موظف الذكاء الاصطناعي غير موجود.")
                return profile
            if path == "/api/roles":
                return {"roles": company_store.list_roles()}
            if path == "/api/permissions":
                return {"permissions": company_store.list_permissions()}
            if path == "/api/tools":
                return {"tools": company_store.list_tools()}
            if path == "/api/external-integrations":
                return integration_store.snapshot()
            generation_match = re.fullmatch(r"/api/external-integrations/generations/([a-f0-9]{32})", path)
            if generation_match:
                return media_generator.poll_generation(generation_match.group(1), "owner")
            if path == "/api/knowledge-sources":
                return {"knowledge_sources": company_store.list_knowledge_sources()}
            if path == "/api/workflows":
                return {"workflows": company_store.list_workflows()}
            if path == "/api/company":
                return {
                    "departments": company_store.list_departments(),
                    "ai_employees": company_store.list_employees(),
                    "characters": store.list_characters(),
                    "projects": store.list_projects(),
                }
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
            integration_test_match = re.fullmatch(r"/api/external-integrations/accounts/([a-f0-9]{32})/test", path)
            if integration_test_match:
                if payload:
                    raise ApiProblem(400, "unexpected_body", "لا يحتاج فحص الاتصال إلى بيانات إضافية.")
                result = integration_store.test_connection(integration_test_match.group(1), actor)
                if result is None:
                    raise ApiProblem(404, "external_account_not_found", "الحساب الخارجي غير موجود.")
                return result
            if path == "/api/external-integrations/generate/audio":
                allowed = {"voice_id", "text", "model_id", "output_format"}
                if set(payload) - allowed:
                    raise IntegrationProblem(400, "invalid_fields", "طلب توليد الصوت يحتوي حقولاً غير مدعومة.")
                result = media_generator.generate_audio(payload, actor)
                return {"generation": result}
            if path == "/api/external-integrations/generate/video":
                allowed = {"prompt", "duration", "aspect_ratio", "resolution", "audio"}
                if set(payload) - allowed:
                    raise IntegrationProblem(400, "invalid_fields", "طلب توليد الفيديو يحتوي حقولاً غير مدعومة.")
                result = media_generator.generate_video(payload, actor)
                return {"generation": result}
            if path == "/api/external-integrations/pipeline":
                allowed = {"script_text", "visual_prompt", "voice_id", "model_id", "output_format", "duration", "aspect_ratio", "resolution"}
                if set(payload) - allowed:
                    raise IntegrationProblem(400, "invalid_fields", "طلب أنبوب الإنتاج يحتوي حقولاً غير مدعومة.")
                result = media_generator.execute_pipeline(payload, actor)
                return {"generation": result}
            if path == "/api/external-integrations/accounts":
                _reject_secret_material(*(payload.get(key) for key in ("label", "provider", "service", "status")))
                account = integration_store.create_account(payload, actor)
                self._send_json(201, {"account": account})
                return None
            if path == "/api/external-integrations/rotate":
                if set(payload) != {"provider", "service"}:
                    raise ApiProblem(400, "invalid_fields", "يلزم إرسال اسم المزود ونوع الخدمة فقط.")
                _reject_secret_material(payload.get("provider"), payload.get("service"))
                account = integration_store.rotate_next(payload.get("service"), payload.get("provider"), actor)
                return {"account": account}
            _reject_secret_material(*payload.values())
            if path == "/api/departments":
                name = _bounded_text(payload, "name", required=True, maximum=180)
                code = _bounded_text(payload, "code", required=True, maximum=32).upper()
                status = _bounded_text(payload, "status", maximum=20).upper() or "ACTIVE"
                priority = _bounded_text(payload, "priority", maximum=20).upper() or "NORMAL"
                if status not in {"ACTIVE", "INACTIVE"} or priority not in COMPANY_PRIORITIES:
                    raise ApiProblem(400, "invalid_department_status", "حالة القسم أو أولويته غير صالحة.")
                department = company_store.create_department({
                    "name": name, "code": code, "description": _bounded_text(payload, "description", maximum=4000),
                    "status": status, "priority": priority, "manager_employee_id": _bounded_text(payload, "manager_employee_id", maximum=80),
                    "goals": _bounded_list(payload, "goals", maximum_items=40, maximum_item=500),
                    "kpis": _bounded_list(payload, "kpis", maximum_items=40, maximum_item=500),
                    "allowed_tools": _bounded_list(payload, "allowed_tools"),
                    "knowledge_source_ids": _bounded_list(payload, "knowledge_source_ids"),
                }, actor)
                self._send_json(201, {"department": department})
                return None
            if path == "/api/ai-employees":
                employee_type = _bounded_text(payload, "employee_type", maximum=20).upper() or "EMPLOYEE"
                if employee_type not in EMPLOYEE_TYPES:
                    raise ApiProblem(400, "invalid_employee_type", "نوع الموظف غير صالح.")
                status = _bounded_text(payload, "status", maximum=20).upper() or "ACTIVE"
                priority = _bounded_text(payload, "priority", maximum=20).upper() or "NORMAL"
                if status not in EMPLOYEE_STATUSES or priority not in COMPANY_PRIORITIES:
                    raise ApiProblem(400, "invalid_employee_status", "حالة الموظف أو أولويته غير صالحة.")
                employee = company_store.create_employee({
                    "name": _bounded_text(payload, "name", required=True, maximum=180),
                    "role": _bounded_text(payload, "role", maximum=120),
                    "role_id": _bounded_text(payload, "role_id", maximum=80),
                    "employee_type": employee_type,
                    "employee_code": _bounded_text(payload, "employee_code", maximum=32),
                    "department_id": _bounded_text(payload, "department_id", required=True, maximum=80),
                    "manager_employee_id": _bounded_text(payload, "manager_employee_id", maximum=80),
                    "parent_employee_id": _bounded_text(payload, "parent_employee_id", maximum=80),
                    "description": _bounded_text(payload, "description", maximum=4000),
                    "job_description": _bounded_text(payload, "job_description", maximum=4000),
                    "responsibilities": _bounded_list(payload, "responsibilities", maximum_items=50, maximum_item=500),
                    "goals": _bounded_list(payload, "goals", maximum_items=50, maximum_item=500),
                    "kpis": _bounded_list(payload, "kpis", maximum_items=50, maximum_item=500),
                    "system_prompt": _bounded_text(payload, "system_prompt", maximum=12000),
                    "personality": _bounded_text(payload, "personality", maximum=2000),
                    "skills": _bounded_list(payload, "skills", maximum_items=50, maximum_item=180),
                    "preferred_model": _bounded_text(payload, "preferred_model", maximum=120),
                    "fallback_model": _bounded_text(payload, "fallback_model", maximum=120),
                    "priority": priority, "memory_enabled": _as_bool(payload.get("memory_enabled", True)), "status": status,
                    "tools": _bounded_list(payload, "tools"),
                    "modules": _bounded_list(payload, "modules", maximum_items=100, maximum_item=80),
                    "knowledge_source_ids": _bounded_list(payload, "knowledge_source_ids"),
                    **({"permissions": _bounded_list(payload, "permissions")} if "permissions" in payload else {}),
                }, actor)
                self._send_json(201, {"employee": employee})
                return None
            employee_task_match = re.fullmatch(r"/api/ai-employees/([A-Za-z0-9_-]{1,80})/tasks", path)
            if employee_task_match:
                priority = _bounded_text(payload, "priority", maximum=20).upper() or "NORMAL"
                if priority not in TASK_PRIORITIES:
                    raise ApiProblem(400, "invalid_priority", "أولوية المهمة غير صالحة.")
                task = company_store.create_employee_task(employee_task_match.group(1), {
                    "title": _bounded_text(payload, "title", required=True, maximum=180),
                    "description": _bounded_text(payload, "description", maximum=4000),
                    "priority": priority,
                    "project_id": _bounded_text(payload, "project_id", maximum=80),
                    "deadline": _bounded_text(payload, "deadline", maximum=40),
                    "approval_required": _as_bool(payload.get("approval_required")),
                }, actor)
                if task is None:
                    raise ApiProblem(404, "employee_not_found", "موظف الذكاء الاصطناعي غير موجود.")
                self._send_json(201, {"task": task})
                return None
            employee_test_match = re.fullmatch(r"/api/ai-employees/([A-Za-z0-9_-]{1,80})/test", path)
            if employee_test_match:
                employee = company_store.get_employee(employee_test_match.group(1))
                if employee is None:
                    raise ApiProblem(404, "employee_not_found", "موظف الذكاء الاصطناعي غير موجود.")
                if employee["status"] != "ACTIVE":
                    raise ApiProblem(409, "employee_not_active", "فعّل الموظف قبل اختباره.")
                if "USE_AI_MODEL" not in employee["permissions"]:
                    raise ApiProblem(403, "employee_model_permission_missing", "لا يملك الموظف صلاحية استخدام نموذج الذكاء الاصطناعي.")
                message = _bounded_text(payload, "message", required=True, maximum=4000)
                result = _employee_ai_response(employee, message, company_store)
                with store.connect() as db:
                    store.log_activity(db, actor=actor, action="employee.tested", module="company-builder",
                                       object_type="ai_employee", object_id=employee["id"],
                                       result=json.dumps({"model": result["model"]}, ensure_ascii=False))
                return {"result": result, "knowledge_sources_used": len(company_store.authorized_knowledge_context(employee["id"]))}
            if path == "/api/tools":
                name = _bounded_text(payload, "name", required=True, maximum=160)
                tool_type = _bounded_text(payload, "tool_type", required=True, maximum=60)
                status = _bounded_text(payload, "status", maximum=20).upper() or "ACTIVE"
                if status not in TOOL_STATUSES:
                    raise ApiProblem(400, "invalid_status", "حالة الأداة غير صالحة.")
                tool = company_store.create_tool({
                    "name": name, "code": _bounded_text(payload, "code", maximum=32), "tool_type": tool_type,
                    "description": _bounded_text(payload, "description", maximum=4000),
                    "endpoint_ref": _bounded_text(payload, "endpoint_ref", maximum=500),
                    "required_permission": _bounded_text(payload, "required_permission", maximum=80), "status": status,
                }, actor)
                self._send_json(201, {"tool": tool})
                return None
            if path == "/api/roles":
                role = company_store.create_role({
                    "name": _bounded_text(payload,"name",required=True,maximum=120),
                    "code": _bounded_text(payload,"code",required=True,maximum=32),
                    "description": _bounded_text(payload,"description",maximum=4000),
                    "permissions": _bounded_list(payload,"permissions",maximum_items=100,maximum_item=80),
                },actor)
                self._send_json(201,{"role":role})
                return None
            if path == "/api/knowledge-sources":
                knowledge_status = _bounded_text(payload, "status", maximum=20).upper() or "ACTIVE"
                if knowledge_status not in TOOL_STATUSES:
                    raise ApiProblem(400, "invalid_status", "حالة مصدر المعرفة غير صالحة.")
                source = company_store.create_knowledge_source({
                    "name": _bounded_text(payload, "name", required=True, maximum=180),
                    "source_type": _bounded_text(payload, "source_type", required=True, maximum=60),
                    "description": _bounded_text(payload, "description", maximum=4000),
                    "source_ref": _bounded_text(payload, "source_ref", maximum=500),
                    "content": _bounded_text(payload, "content", maximum=50000),
                    "status": knowledge_status,
                }, actor)
                self._send_json(201, {"knowledge_source": source})
                return None
            if path == "/api/workflows":
                status = _bounded_text(payload, "status", maximum=20).upper() or "DRAFT"
                if status not in WORKFLOW_STATUSES:
                    raise ApiProblem(400, "invalid_status", "حالة سير العمل غير صالحة.")
                workflow = company_store.create_workflow({
                    "name": _bounded_text(payload, "name", required=True, maximum=180),
                    "description": _bounded_text(payload, "description", maximum=4000),
                    "status": status,
                    "steps": _bounded_list(payload, "steps", maximum_items=50, maximum_item=180),
                }, actor)
                self._send_json(201, {"workflow": workflow})
                return None
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
                                          "priority": priority, "status": status,
                                          "assigned_employee_id": _bounded_text(payload, "assigned_employee_id", maximum=80),
                                          "project_id": _bounded_text(payload, "project_id", maximum=80),
                                          "deadline": _bounded_text(payload, "deadline", maximum=40),
                                          "approval_required": _as_bool(payload.get("approval_required"))}, actor)
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
            integration_match = re.fullmatch(r"/api/external-integrations/accounts/([a-f0-9]{32})", path)
            if integration_match:
                _reject_secret_material(*(value for key, value in payload.items() if key != "credential"))
                account = integration_store.update_account(integration_match.group(1), payload, actor)
                if account is None:
                    raise ApiProblem(404, "external_account_not_found", "الحساب الخارجي غير موجود.")
                return {"account": account}
            _reject_secret_material(*payload.values())
            role_match = re.fullmatch(r"/api/roles/([A-Za-z0-9_-]{1,80})", path)
            if role_match:
                update: dict[str,Any]={}
                if "name" in payload: update["name"]=_bounded_text(payload,"name",maximum=120)
                if "description" in payload: update["description"]=_bounded_text(payload,"description",maximum=4000)
                if "permissions" in payload: update["permissions"]=_bounded_list(payload,"permissions",maximum_items=100,maximum_item=80)
                role=company_store.update_role(role_match.group(1),update,actor)
                if role is None: raise ApiProblem(404,"role_not_found","الدور غير موجود.")
                return {"role":role}
            department_match = re.fullmatch(r"/api/departments/([A-Za-z0-9_-]{1,80})", path)
            if department_match:
                update: dict[str, Any] = {}
                for key, maximum in (("name",180),("code",32),("description",4000),("status",20),("priority",20),("manager_employee_id",80)):
                    if key in payload:
                        update[key] = _bounded_text(payload,key,maximum=maximum).upper() if key in {"code","status","priority"} else _bounded_text(payload,key,maximum=maximum)
                for key in ("goals","kpis","allowed_tools","knowledge_source_ids"):
                    if key in payload: update[key] = _bounded_list(payload,key,maximum_items=100,maximum_item=500)
                item = company_store.update_department(department_match.group(1),update,actor)
                if item is None: raise ApiProblem(404,"department_not_found","القسم غير موجود.")
                return {"department":item}
            permission_match = re.fullmatch(r"/api/ai-employees/([A-Za-z0-9_-]{1,80})/permissions", path)
            if permission_match:
                permissions = _bounded_list(payload,"permissions",maximum_items=100,maximum_item=80)
                item = company_store.set_employee_permissions(permission_match.group(1),permissions,actor)
                if item is None: raise ApiProblem(404,"employee_not_found","موظف الذكاء الاصطناعي غير موجود.")
                return {"employee":item}
            employee_match = re.fullmatch(r"/api/ai-employees/([A-Za-z0-9_-]{1,80})", path)
            if employee_match:
                update: dict[str, Any] = {}
                text_fields={"name":180,"role":120,"description":4000,"employee_code":32,"job_description":4000,
                             "system_prompt":12000,"personality":2000,"preferred_model":120,"fallback_model":120,
                             "department_id":80,"manager_employee_id":80,"parent_employee_id":80,"role_id":80}
                for key,maximum in text_fields.items():
                    if key in payload: update[key]=_bounded_text(payload,key,maximum=maximum)
                for key in ("responsibilities","goals","kpis","skills","tools","knowledge_source_ids","modules","permissions"):
                    if key in payload: update[key]=_bounded_list(payload,key,maximum_items=100,maximum_item=500)
                if "status" in payload: update["status"]=_bounded_text(payload,"status",maximum=20).upper()
                if "priority" in payload: update["priority"]=_bounded_text(payload,"priority",maximum=20).upper()
                if "memory_enabled" in payload: update["memory_enabled"]=_as_bool(payload["memory_enabled"])
                item=company_store.update_employee(employee_match.group(1),update,actor)
                if item is None: raise ApiProblem(404,"employee_not_found","موظف الذكاء الاصطناعي غير موجود.")
                return {"employee":item}
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

        def _delete_api(self) -> dict[str, Any]:
            path = urllib.parse.urlsplit(self.path).path
            actor = self._authenticate()
            integration_match = re.fullmatch(r"/api/external-integrations/accounts/([a-f0-9]{32})", path)
            if integration_match:
                if not integration_store.delete_account(integration_match.group(1), actor):
                    raise ApiProblem(404, "external_account_not_found", "الحساب الخارجي غير موجود.")
                return {"deleted": True}
            role_match = re.fullmatch(r"/api/roles/([A-Za-z0-9_-]{1,80})", path)
            if role_match:
                if not company_store.delete_role(role_match.group(1),actor):
                    raise ApiProblem(404,"role_not_found","الدور غير موجود.")
                return {"deleted":True}
            department_match = re.fullmatch(r"/api/departments/([A-Za-z0-9_-]{1,80})", path)
            if department_match:
                if not company_store.delete_department(department_match.group(1),actor):
                    raise ApiProblem(404,"department_not_found","القسم غير موجود.")
                return {"deleted":True}
            employee_match = re.fullmatch(r"/api/ai-employees/([A-Za-z0-9_-]{1,80})", path)
            if employee_match:
                if not company_store.delete_employee(employee_match.group(1),actor):
                    raise ApiProblem(404,"employee_not_found","موظف الذكاء الاصطناعي غير موجود.")
                return {"deleted":True}
            raise ApiProblem(404,"not_found","مسار API غير موجود.")

    return Handler


def main() -> None:
    load_local_env()
    bind = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    handler = make_handler()
    server = ThreadingHTTPServer((bind, port), handler)
    print(f"AI Media OS listening at http://{bind}:{port}")
    owner_password = os.environ.get("OWNER_MASTER_PASSWORD", "") or os.environ.get("OWNER_API_TOKEN", "")
    print(f"Owner authentication: {'configured' if owner_password else 'NOT CONFIGURED (read-only health endpoint only)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
