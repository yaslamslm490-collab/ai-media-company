from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

from backend.server import _persist_password, load_local_env, make_handler, system_health  # noqa: E402
from backend.store import Store  # noqa: E402


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {
            "OWNER_MASTER_PASSWORD": "", "OWNER_API_TOKEN": "", "OWNER_RECOVERY_CODE": "",
            "COOKIE_SECURE": "", "PUBLIC_BASE_URL": "", "RENDER_EXTERNAL_URL": "",
            "OWNER_PASSWORD_FILE": str(Path(self.temp.name) / "owner-password.txt"),
            "AI_ROUTER_HEALTH_URL": "", "AI_ROUTER_BASE_URL": "", "AI_ROUTER_CHAT_COMPLETIONS_URL": "", "AI_ROUTER_MODEL": "",
            "AI_ROUTER_API_KEY": "", "OPENAI_API_BASE": "", "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "", "GEMINI_MODEL": "", "GEMINI_BASE_URL": "",
            "MANUS_HEALTH_URL": "", "MANUS_API_TOKEN": "", "MANUS_API_KEY": "",
            "GITHUB_HEALTH_URL": "", "GITHUB_TOKEN": "", "GITHUB_USE_CLI": "", "EXTERNAL_HEALTH_URLS": "",
        })
        self.env_patch.start()
        self.token = "test-token-for-owner-access-32-chars"
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(root=ROOT, db_path=Path(self.temp.name) / "test.sqlite3", owner_token=self.token),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()
        self.env_patch.stop()

    def request(self, method: str, path: str, *, body: dict | None = None, token: str | None = None,
                cookie: str | None = None, origin: str | None = None, forwarded_proto: str | None = None):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if token is not None:
            headers["X-Owner-Token"] = token
        if cookie is not None:
            headers["Cookie"] = cookie
        if origin is not None:
            headers["Origin"] = origin
        if forwarded_proto is not None:
            headers["X-Forwarded-Proto"] = forwarded_proto
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                self.last_headers = response.headers
                raw = response.read()
                if not raw:
                    return response.status, {}
                try:
                    return response.status, json.loads(raw)
                except json.JSONDecodeError:
                    return response.status, raw.decode("utf-8", errors="replace")
        except HTTPError as error:
            self.last_headers = error.headers
            raw = error.read()
            if not raw:
                return error.code, {}
            try:
                return error.code, json.loads(raw)
            except json.JSONDecodeError:
                return error.code, raw.decode("utf-8", errors="replace")

    def test_local_env_fills_empty_host_values_without_overwriting_nonempty_values(self):
        with tempfile.TemporaryDirectory() as temp:
            env_file = Path(temp) / ".env"
            env_file.write_text("MANUS_API_KEY=dotenv-test-key\nOPENAI_API_KEY=dotenv-should-not-win\n")
            with patch.dict(os.environ, {"MANUS_API_KEY": "", "OPENAI_API_KEY": "host-test-key"}):
                load_local_env(Path(temp))
                self.assertEqual(os.environ["MANUS_API_KEY"], "dotenv-test-key")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "host-test-key")

    def test_health_checks_backend_and_database_and_does_not_claim_missing_integrations(self):
        status, payload = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["checks"]["backend"], "ONLINE")
        self.assertEqual(payload["checks"]["database"], "ONLINE")
        self.assertEqual(payload["checks"]["authentication"], "ONLINE")
        self.assertEqual(payload["checks"]["github"], "NOT_CONFIGURED")
        self.assertEqual(payload["checks"]["manus"], "NOT_CONFIGURED")
        self.assertEqual(payload["overall"], "NOT_CONFIGURED")

    def test_health_reports_database_error_when_ping_fails(self):
        store = Store(Path(self.temp.name) / "health-db-failure.sqlite3")
        store.initialize()
        with patch.object(store, "ping", return_value=False):
            health = system_health(store, self.token, environ={})
        self.assertEqual(health["checks"]["backend"], "ONLINE")
        self.assertEqual(health["checks"]["database"], "ERROR")
        self.assertEqual(health["overall"], "ERROR")

    def test_ai_router_falls_back_to_authenticated_openai_compatible_models_endpoint(self):
        store = Store(Path(self.temp.name) / "health-ai.sqlite3")
        store.initialize()
        env = {"OPENAI_API_BASE": "https://router.example/v1", "OPENAI_API_KEY": "test-ai-key"}
        with patch("backend.server._probe", return_value="ONLINE") as probe:
            health = system_health(store, self.token, environ=env)
        self.assertEqual(health["checks"]["ai_router"], "ONLINE")
        probe.assert_any_call("https://router.example/v1/models", "test-ai-key")

    def test_gemini_is_not_claimed_online_without_server_configuration(self):
        status, payload = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["checks"]["gemini"], "NOT_CONFIGURED")
        self.assertEqual(payload["integration_details"]["gemini"]["last_checked_at"], None)

        status, integrations = self.request("GET", "/api/service-integrations", token=self.token)
        self.assertEqual(status, 200)
        gemini = next(item for item in integrations["integrations"] if item["key"] == "gemini")
        self.assertEqual(gemini["automatic_status"], "NOT_CONFIGURED")
        self.assertFalse(gemini["configured"])

    def test_gemini_command_uses_server_key_and_persists_safe_online_status(self):
        fake_key = "unit-test-key"
        os.environ.update({"GEMINI_API_KEY": fake_key, "GEMINI_MODEL": "model-under-owner-control"})
        with patch("backend.gemini._request_json", return_value={"candidates": [{"content": {"parts": [{"text": "رد Gemini تجريبي"}]}}]}) as request:
            status, payload = self.request("POST", "/api/commands", token=self.token, body={"command": "اكتب ردًا تجريبيًا", "source": "text"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "SUCCESS")
        self.assertEqual(payload["response"], "رد Gemini تجريبي")
        request.assert_called_once()
        url, kwargs = request.call_args.args[0], request.call_args.kwargs
        self.assertIn("model-under-owner-control", url)
        self.assertEqual(kwargs["api_key"], fake_key)
        self.assertNotIn(fake_key, json.dumps(payload, ensure_ascii=False))

        status, health = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["checks"]["gemini"], "ONLINE")
        self.assertEqual(health["integration_details"]["gemini"]["model"], "model-under-owner-control")
        self.assertTrue(health["integration_details"]["gemini"]["last_checked_at"])

    def test_gemini_configuration_error_is_blocked_without_router_fallback(self):
        os.environ["GEMINI_MODEL"] = "model-without-key"
        status, payload = self.request("POST", "/api/commands", token=self.token, body={"command": "اختبار إعداد Gemini", "source": "text"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["report"]["tests"][2]["status"], "NOT_CONFIGURED")
        self.assertIn("GEMINI_API_KEY", payload["message"])

    def test_manus_api_key_uses_official_header_and_limited_health_query(self):
        store = Store(Path(self.temp.name) / "health-manus.sqlite3")
        store.initialize()
        env = {"MANUS_API_KEY": "test-manus-key"}
        with patch("backend.server._probe", return_value="ONLINE") as probe:
            health = system_health(store, self.token, environ=env)
        self.assertEqual(health["checks"]["manus"], "ONLINE")
        probe.assert_any_call(
            "https://api.manus.ai/v2/task.list?limit=1",
            "test-manus-key",
            auth_header="x-manus-api-key",
            auth_scheme="",
        )

    def test_github_cli_probe_is_opt_in_and_does_not_return_account_identity(self):
        store = Store(Path(self.temp.name) / "health-github.sqlite3")
        store.initialize()
        env = {"GITHUB_USE_CLI": "true"}
        with patch("backend.server._probe_github_cli", return_value="ONLINE") as probe:
            health = system_health(store, self.token, environ=env)
        self.assertEqual(health["checks"]["github"], "ONLINE")
        self.assertNotIn("username", json.dumps(health))
        probe.assert_called_once_with()

    def test_private_data_requires_owner_authentication(self):
        status, payload = self.request("GET", "/api/dashboard")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "authentication_required")
        status, payload = self.request("GET", "/api/company")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "authentication_required")
        status, payload = self.request("POST", "/api/tasks", body={"title": "Forbidden"})
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "authentication_required")
        status, _ = self.request("GET", "/api/dashboard", token="wrong-token")
        self.assertEqual(status, 401)

    def test_empty_dashboard_returns_actual_zero_counts_and_unconfigured_entities(self):
        status, payload = self.request("GET", "/api/dashboard", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(payload["company"]["task_counts"]["TOTAL"], 0)
        self.assertEqual(payload["company"]["waiting_approvals"]["value"], 0)
        self.assertEqual(payload["company"]["active_ai_employees"]["value"], 0)
        self.assertEqual(payload["company"]["active_characters"]["value"], 0)
        self.assertEqual(payload["company"]["active_projects"]["value"], 0)
        self.assertEqual(payload["company"]["active_characters"]["status"], "ONLINE")
        self.assertEqual(payload["recent_activity"], [])

    def test_seed_initial_data_is_idempotent_and_visible_in_dashboard_and_modules(self):
        store = Store(Path(self.temp.name) / "test.sqlite3")
        store.initialize()
        first = store.seed_initial_data()
        second = store.seed_initial_data()
        self.assertEqual(sum(first["inserted"].values()), 6)
        self.assertFalse(any(second["inserted"].values()))
        self.assertEqual(first["counts"], {"departments": 1, "ai_employees": 1, "characters": 1,
                                             "projects": 1, "tasks": 1, "approvals": 1})

        status, company = self.request("GET", "/api/company", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(company["departments"][0]["name"], "إنتاج المحتوى")
        self.assertEqual(company["ai_employees"][0]["department"], "إنتاج المحتوى")
        self.assertEqual(company["characters"][0]["name"], "ليان")
        self.assertEqual(company["projects"][0]["status"], "ACTIVE")

        status, dashboard = self.request("GET", "/api/dashboard", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["company"]["active_departments"]["value"], 1)
        self.assertEqual(dashboard["company"]["active_ai_employees"]["value"], 1)
        self.assertEqual(dashboard["company"]["active_characters"]["value"], 1)
        self.assertEqual(dashboard["company"]["active_projects"]["value"], 1)
        self.assertEqual(dashboard["company"]["task_counts"]["IN_PROGRESS"], 1)
        self.assertEqual(dashboard["company"]["waiting_approvals"]["value"], 1)

        status, modules = self.request("GET", "/api/modules")
        self.assertEqual(status, 200)
        states = {module["id"]: module["state"] for module in modules["modules"]}
        self.assertEqual(states["ai-team"], "READY")
        self.assertEqual(states["characters"], "READY")
        self.assertEqual(states["projects"], "READY")

    def test_global_search_requires_owner_and_returns_live_database_matches(self):
        status, payload = self.request("GET", "/api/search?q=NADA%20Search%20Regression")
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "authentication_required")

        status, created = self.request("POST", "/api/tasks", token=self.token, body={
            "title": "NADA Search Regression 8472", "description": "سجل اختبار محلي مؤقت.",
            "owner": "المالك", "assigned_employee": "", "department": "الاختبار",
            "priority": "NORMAL", "status": "TODO",
        })
        self.assertEqual(status, 201)
        status, results = self.request("GET", "/api/search?q=NADA%20Search%20Regression", token=self.token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(results["displayed_count"], 1)
        task_group = next(group for group in results["groups"] if group["id"] == "tasks")
        self.assertEqual(task_group["results"][0]["title"], "NADA Search Regression 8472")
        self.assertEqual(task_group["results"][0]["status"], "TODO")

        status, empty = self.request("GET", "/api/search?q=No%20Such%20Record%209913", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(empty["displayed_count"], 0)
        self.assertEqual(empty["groups"], [])

    def test_task_create_transition_dashboard_and_activity_are_persisted(self):
        status, payload = self.request("POST", "/api/tasks", token=self.token, body={
            "title": "مراجعة موجز الإطلاق", "description": "اعتماد النسخة النهائية.",
            "owner": "المالك", "assigned_employee": "", "department": "المحتوى",
            "priority": "HIGH", "status": "TODO",
        })
        self.assertEqual(status, 201)
        task = payload["task"]
        self.assertEqual(task["title"], "مراجعة موجز الإطلاق")
        self.assertEqual(task["status"], "TODO")
        self.assertTrue(task["id"])
        self.assertTrue(task["created_at"])
        self.assertTrue(task["updated_at"])

        status, updated = self.request("PATCH", f"/api/tasks/{task['id']}", token=self.token, body={"status": "IN_PROGRESS"})
        self.assertEqual(status, 200)
        self.assertEqual(updated["task"]["status"], "IN_PROGRESS")

        status, tasks = self.request("GET", "/api/tasks?status=IN_PROGRESS", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(tasks["tasks"]), 1)
        status, dashboard = self.request("GET", "/api/dashboard", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["company"]["task_counts"]["IN_PROGRESS"], 1)
        self.assertEqual(dashboard["company"]["activity_count"], 2)

    def test_approval_decision_is_saved_and_cannot_be_overwritten(self):
        status, payload = self.request("POST", "/api/approvals", token=self.token, body={
            "title": "اعتماد النص", "description": "النسخة الثانية", "submitted_by": "مراجع",
        })
        self.assertEqual(status, 201)
        approval_id = payload["approval"]["id"]
        status, missing_note = self.request("PATCH", f"/api/approvals/{approval_id}", token=self.token,
                                             body={"decision": "REQUEST_CHANGES", "note": ""})
        self.assertEqual(status, 400)
        self.assertEqual(missing_note["error"]["code"], "note_required")

        status, decided = self.request("PATCH", f"/api/approvals/{approval_id}", token=self.token,
                                       body={"decision": "REQUEST_CHANGES", "note": "اختصر المقدمة."})
        self.assertEqual(status, 200)
        self.assertEqual(decided["approval"]["status"], "CHANGES_REQUESTED")
        self.assertEqual(decided["approval"]["decision_note"], "اختصر المقدمة.")
        status, decisions = self.request("GET", f"/api/approvals/{approval_id}/decisions", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(decisions["decisions"]), 1)
        self.assertEqual(decisions["decisions"][0]["decision"], "REQUEST_CHANGES")
        status, duplicate = self.request("PATCH", f"/api/approvals/{approval_id}", token=self.token,
                                         body={"decision": "APPROVE"})
        self.assertEqual(status, 409)
        self.assertEqual(duplicate["error"]["code"], "approval_already_decided")

        status, activity = self.request("GET", "/api/activity", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(activity["activity"]), 4)
        self.assertTrue(any(item["action"] == "approval.request_changes" and item["status"] == "SUCCESS" for item in activity["activity"]))
        self.assertEqual(sum(item["status"] == "FAILURE" for item in activity["activity"]), 2)

    def test_validation_rejects_unknown_task_status(self):
        status, payload = self.request("POST", "/api/tasks", token=self.token,
                                       body={"title": "Invalid", "status": "RUNNING"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "invalid_status")
        status, dashboard = self.request("GET", "/api/dashboard", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["company"]["task_counts"]["TOTAL"], 0)

    def test_approve_and_reject_decisions_are_persisted(self):
        for title, decision, expected in [
            ("اعتماد تصميم", "APPROVE", "APPROVED"),
            ("رفض نسخة", "REJECT", "REJECTED"),
        ]:
            status, created = self.request("POST", "/api/approvals", token=self.token, body={"title": title})
            self.assertEqual(status, 201)
            approval_id = created["approval"]["id"]
            status, result = self.request("PATCH", f"/api/approvals/{approval_id}", token=self.token,
                                          body={"decision": decision, "note": "قرار اختباري"})
            self.assertEqual(status, 200)
            self.assertEqual(result["approval"]["status"], expected)
            status, history = self.request("GET", f"/api/approvals/{approval_id}/decisions", token=self.token)
            self.assertEqual(status, 200)
            self.assertEqual(history["decisions"][0]["decision"], decision)

    def test_text_command_generates_and_persists_response_using_local_mock_router(self):
        class MockRouterHandler(BaseHTTPRequestHandler):
            requests = []

            def log_message(self, _format, *_args):
                return

            def send_json(self, payload):
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                self.send_json({"data": [{"id": "mock-arabic-model"}]})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                self.__class__.requests.append({"payload": payload, "authorization": self.headers.get("Authorization")})
                self.send_json({"choices": [{"message": {"content": "مسودة عربية اختبارية محفوظة في تقرير التنفيذ."}}]})

        MockRouterHandler.requests.clear()
        router = ThreadingHTTPServer(("127.0.0.1", 0), MockRouterHandler)
        router_thread = threading.Thread(target=router.serve_forever, daemon=True)
        router_thread.start()
        try:
            base = f"http://127.0.0.1:{router.server_port}/v1"
            with patch.dict(os.environ, {"AI_ROUTER_BASE_URL": base, "AI_ROUTER_API_KEY": "local-mock-key", "AI_ROUTER_MODEL": "", "AI_ROUTER_CHAT_COMPLETIONS_URL": ""}):
                status, payload = self.request("POST", "/api/commands", token=self.token, body={
                    "command": "اكتب مسودة منشور تعريفي عن NADA AI.", "source": "text",
                })
            self.assertEqual(status, 200)
            self.assertTrue(payload["executed"])
            self.assertEqual(payload["status"], "SUCCESS")
            self.assertEqual(payload["response"], "مسودة عربية اختبارية محفوظة في تقرير التنفيذ.")
            self.assertEqual(payload["report"]["status"], "SUCCESS")
            response_step = next(step for step in payload["report"]["steps"] if step["key"] == "assistant_response")
            self.assertEqual(response_step["result"], payload["response"])
            generation_step = next(step for step in payload["report"]["steps"] if step["key"] == "generate")
            self.assertIn("mock-arabic-model", generation_step["label"])
            self.assertEqual(MockRouterHandler.requests[0]["authorization"], "Bearer local-mock-key")
            stored = Store(Path(self.temp.name) / "test.sqlite3").list_execution_reports(limit=1)[0]
            self.assertEqual(stored["steps"][2]["result"], payload["response"])
            voice_test = next(test for test in stored["tests"] if test["name"] == "Arabic voice input/output")
            self.assertEqual(voice_test["status"], "NOT_TESTED")
        finally:
            router.shutdown()
            router.server_close()
            router_thread.join(timeout=3)

    def test_text_command_without_router_is_blocked_not_reported_as_success(self):
        status, payload = self.request("POST", "/api/commands", token=self.token, body={
            "command": "اكتب مسودة محتوى تجريبية.", "source": "live-voice",
        })
        self.assertEqual(status, 200)
        self.assertTrue(payload["accepted"])
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertEqual(payload["report"]["status"], "BLOCKED")
        self.assertIn("AI_ROUTER_BASE_URL", payload["message"])
        self.assertEqual(payload["report"]["tests"][-1]["status"], "NOT_TESTED")
        stored = Store(Path(self.temp.name) / "test.sqlite3").list_execution_reports(limit=1)[0]
        self.assertEqual(stored["status"], "BLOCKED")

    def test_untranscribed_audio_upload_is_not_claimed_as_processed(self):
        status, payload = self.request("POST", "/api/commands", token=self.token, body={
            "command": "", "source": "audio-recorder", "audio_base64": "dGVzdA==",
        })
        self.assertEqual(status, 200)
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["status"], "BLOCKED")
        self.assertIn("لا يوجد محرك ASR", payload["message"])
        self.assertEqual(payload["report"]["tests"][-1]["status"], "NOT_TESTED")

    def test_static_server_does_not_expose_backend_database_or_environment_files(self):
        for path in ["/backend/store.py", "/data/secret.sqlite3", "/.env", "/tests/test_api.py"]:
            status, _ = self.request("GET", path)
            self.assertEqual(status, 404, path)
        status, _ = self.request("GET", "/")
        self.assertEqual(status, 200)

    def test_owner_api_auth_limits_failed_tokens_but_keeps_correct_owner_access(self):
        for _ in range(5):
            status, payload = self.request("GET", "/api/dashboard", token="wrong-owner-token")
            self.assertEqual(status, 401, payload)
        status, payload = self.request("GET", "/api/dashboard", token="wrong-owner-token")
        self.assertEqual(status, 429, payload)
        self.assertEqual(payload["error"]["code"], "too_many_auth_attempts")
        status, payload = self.request("GET", "/api/dashboard", token=self.token)
        self.assertEqual(status, 200, payload)

    def test_browser_login_uses_http_only_cookie_and_cookie_auth_requires_same_origin_for_writes(self):
        origin = self.base.replace("http://", "https://", 1)
        status, payload = self.request("POST", "/api/auth/login", body={"token": self.token}, origin=origin, forwarded_proto="https")
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload, {"authenticated": True})
        set_cookie = self.last_headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=None", set_cookie)
        self.assertIn("Secure", set_cookie)
        self.assertNotIn(self.token, set_cookie)
        cookie = set_cookie.split(";", 1)[0]
        status, session = self.request("GET", "/api/auth/session", cookie=cookie)
        self.assertEqual((status, session["authenticated"]), (200, True))
        status, dashboard = self.request("GET", "/api/dashboard", cookie=cookie)
        self.assertEqual(status, 200, dashboard)
        status, _ = self.request("POST", "/api/tasks", body={"title": "Cookie session task"}, cookie=cookie)
        self.assertEqual(status, 403)
        status, task = self.request("POST", "/api/tasks", body={"title": "Cookie session task"}, cookie=cookie, origin=origin, forwarded_proto="https")
        self.assertEqual(status, 201, task)
        status, _ = self.request("POST", "/api/tasks", body={"title": "Cross origin task"}, cookie=cookie, origin="https://attacker.example", forwarded_proto="https")
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/tasks", body={"title": "Downgrade origin task"}, cookie=cookie, origin=self.base, forwarded_proto="https")
        self.assertEqual(status, 403)

    def test_browser_logout_revokes_cookie_and_clears_it(self):
        status, _ = self.request("POST", "/api/auth/login", body={"token": self.token})
        self.assertEqual(status, 200)
        cookie = self.last_headers.get("Set-Cookie", "").split(";", 1)[0]
        status, _ = self.request("POST", "/api/auth/logout", cookie=cookie, origin="https://attacker.example", forwarded_proto="http")
        self.assertEqual(status, 403)
        status, session = self.request("GET", "/api/auth/session", cookie=cookie)
        self.assertEqual((status, session["authenticated"]), (200, True))
        status, payload = self.request("POST", "/api/auth/logout", cookie=cookie, origin=self.base)
        self.assertEqual(status, 200, payload)
        self.assertIn("Max-Age=0", self.last_headers.get("Set-Cookie", ""))
        status, session = self.request("GET", "/api/auth/session", cookie=cookie)
        self.assertEqual((status, session["authenticated"]), (200, False))
        status, _ = self.request("GET", "/api/dashboard", cookie=cookie)
        self.assertEqual(status, 401)

    def test_owner_login_limits_wrong_password_attempts_and_returns_secure_cookie_when_configured(self):
        for _ in range(5):
            status, _ = self.request("POST", "/api/auth/login", body={"token": "wrong-owner-password"})
            self.assertEqual(status, 401)
        status, payload = self.request("POST", "/api/auth/login", body={"token": "wrong-owner-password"})
        self.assertEqual(status, 429, payload)
        self.assertEqual(payload["error"]["code"], "too_many_auth_attempts")
        with patch.dict(os.environ, {"COOKIE_SECURE": "true"}):
            status, _ = self.request("POST", "/api/auth/login", body={"token": self.token})
        self.assertEqual(status, 200)
        self.assertIn("Secure", self.last_headers.get("Set-Cookie", ""))

    def test_password_rotation_revokes_existing_browser_sessions_and_issues_replacement(self):
        status, _ = self.request("POST", "/api/auth/login", body={"token": self.token})
        self.assertEqual(status, 200)
        old_cookie = self.last_headers.get("Set-Cookie", "").split(";", 1)[0]
        replacement = "NADA-rotated-auth-cookie-test-token"
        body = {"current_password": self.token, "new_password": replacement, "confirm_password": replacement}
        status, payload = self.request("POST", "/api/auth/change-password", body=body, cookie=old_cookie, origin=self.base)
        self.assertEqual(status, 200, payload)
        self.assertNotIn(replacement, json.dumps(payload))
        new_cookie = self.last_headers.get("Set-Cookie", "").split(";", 1)[0]
        status, session = self.request("GET", "/api/auth/session", cookie=new_cookie)
        self.assertEqual((status, session["authenticated"]), (200, True))
        status, session = self.request("GET", "/api/auth/session", cookie=old_cookie)
        self.assertEqual((status, session["authenticated"]), (200, False))
        status, _ = self.request("GET", "/api/dashboard", cookie=new_cookie)
        self.assertEqual(status, 200)

    def test_owner_recovery_limits_invalid_codes_without_writing_password(self):
        with patch.dict(os.environ, {"OWNER_RECOVERY_CODE": "test-recovery-code-with-sufficient-entropy"}):
            payload = {"recovery_code": "wrong-recovery-code", "new_password": "NADA-new-owner-token-2026", "confirm_password": "NADA-new-owner-token-2026"}
            for _ in range(5):
                status, _ = self.request("POST", "/api/auth/reset-password", body=payload)
                self.assertEqual(status, 401)
            status, response = self.request("POST", "/api/auth/reset-password", body=payload)
            self.assertEqual(status, 429)
            self.assertEqual(response["error"]["code"], "too_many_recovery_attempts")
            self.assertFalse(Path(os.environ["OWNER_PASSWORD_FILE"]).exists())

    def test_password_file_is_atomically_written_with_restrictive_mode(self):
        destination = Path(os.environ["OWNER_PASSWORD_FILE"])
        old_umask = os.umask(0o022)
        try:
            _persist_password("NADA-test-rotated-owner-token-2026")
        finally:
            os.umask(old_umask)
        self.assertEqual(destination.read_text(encoding="utf-8").strip(), "NADA-test-rotated-owner-token-2026")
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(destination.parent.glob(f".{destination.name}.*")), [])

    def test_password_file_permission_failure_preserves_existing_value(self):
        destination = Path(os.environ["OWNER_PASSWORD_FILE"])
        destination.write_text("existing-test-owner-token\n", encoding="utf-8")
        destination.chmod(0o600)
        with patch("backend.server.os.fchmod", side_effect=PermissionError("simulated permission failure")):
            with self.assertRaises(PermissionError):
                _persist_password("replacement-test-owner-token")
        self.assertEqual(destination.read_text(encoding="utf-8"), "existing-test-owner-token\n")
        self.assertEqual(list(destination.parent.glob(f".{destination.name}.*")), [])

    def test_failed_password_persistence_does_not_rotate_in_memory_token(self):
        body = {"current_password": self.token, "new_password": "NADA-replacement-owner-token-2026", "confirm_password": "NADA-replacement-owner-token-2026"}
        with patch("backend.server._persist_password", side_effect=OSError("simulated storage failure")):
            status, payload = self.request("POST", "/api/auth/change-password", body=body, token=self.token)
        self.assertEqual(status, 500, payload)
        self.assertEqual(payload["error"]["code"], "internal_error")
        self.assertNotIn("simulated storage failure", json.dumps(payload))
        status, _ = self.request("GET", "/api/dashboard", token=self.token)
        self.assertEqual(status, 200)


class AuthNotConfiguredTest(unittest.TestCase):
    def test_owner_master_password_accepts_six_digits_from_environment(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OWNER_MASTER_PASSWORD": "123456", "OWNER_API_TOKEN": ""}):
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root=ROOT, db_path=Path(temp) / "db.sqlite3"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(f"http://127.0.0.1:{server.server_port}/api/dashboard", headers={"X-Owner-Token": "123456"})
                with urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_render_style_owner_api_token_change_survives_process_restart_on_configured_disk(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "OWNER_MASTER_PASSWORD": "", "OWNER_API_TOKEN": "render-test-owner-token",
            "OWNER_PASSWORD_FILE": str(Path(temp) / "durable" / "owner-password.txt"),
        }):
            db_path = Path(temp) / "db.sqlite3"

            def start_server():
                instance = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root=ROOT, db_path=db_path))
                worker = threading.Thread(target=instance.serve_forever, daemon=True)
                worker.start()
                return instance, worker

            def stop_server(instance, worker):
                instance.shutdown()
                instance.server_close()
                worker.join(timeout=3)

            server, thread = start_server()
            try:
                rotated = "NADA-rotated-owner-token-2026"
                body = json.dumps({"current_password": "render-test-owner-token", "new_password": rotated, "confirm_password": rotated}).encode()
                request = Request(f"http://127.0.0.1:{server.server_port}/api/auth/change-password", data=body,
                                  headers={"Content-Type": "application/json", "X-Owner-Token": "render-test-owner-token"}, method="POST")
                with urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["changed"])
            finally:
                stop_server(server, thread)

            os.environ["OWNER_MASTER_PASSWORD"] = ""
            restarted, restarted_thread = start_server()
            try:
                request = Request(f"http://127.0.0.1:{restarted.server_port}/api/dashboard", headers={"X-Owner-Token": rotated})
                with urlopen(request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                old_request = Request(f"http://127.0.0.1:{restarted.server_port}/api/dashboard", headers={"X-Owner-Token": "render-test-owner-token"})
                with self.assertRaises(HTTPError) as raised:
                    urlopen(old_request, timeout=3)
                self.assertEqual(raised.exception.code, 401)
                self.assertEqual(Path(os.environ["OWNER_PASSWORD_FILE"]).stat().st_mode & 0o777, 0o600)
            finally:
                stop_server(restarted, restarted_thread)

    def test_environment_managed_owner_password_requires_host_secret_rotation(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "OWNER_MASTER_PASSWORD": "123456", "OWNER_API_TOKEN": "",
            "OWNER_PASSWORD_FILE": str(Path(temp) / "owner-password.txt"),
        }):
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root=ROOT, db_path=Path(temp) / "db.sqlite3"))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({"current_password": "123456", "new_password": "654321", "confirm_password": "654321"}).encode()
                request = Request(f"http://127.0.0.1:{server.server_port}/api/auth/change-password", data=body,
                                  headers={"Content-Type": "application/json", "X-Owner-Token": "123456"}, method="POST")
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=3)
                self.assertEqual(raised.exception.code, 409)
                error = json.loads(raised.exception.read())
                self.assertEqual(error["error"]["code"], "password_managed_by_environment")
                self.assertFalse(Path(os.environ["OWNER_PASSWORD_FILE"]).exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_password_rotation_rejects_weak_non_pin_without_changing_owner_token(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "OWNER_MASTER_PASSWORD": "", "OWNER_API_TOKEN": "",
            "OWNER_PASSWORD_FILE": str(Path(temp) / "owner-password.txt"),
        }):
            current = "owner-token-for-rotation-tests"
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root=ROOT, db_path=Path(temp) / "db.sqlite3", owner_token=current))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps({"current_password": current, "new_password": "weak-pass-123", "confirm_password": "weak-pass-123"}).encode()
                request = Request(f"http://127.0.0.1:{server.server_port}/api/auth/change-password", data=body,
                                  headers={"Content-Type": "application/json", "X-Owner-Token": current}, method="POST")
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=3)
                self.assertEqual(raised.exception.code, 400)
                self.assertEqual(json.loads(raised.exception.read())["error"]["code"], "invalid_new_password")
                self.assertFalse(Path(os.environ["OWNER_PASSWORD_FILE"]).exists())
                dashboard_request = Request(f"http://127.0.0.1:{server.server_port}/api/dashboard", headers={"X-Owner-Token": current})
                with urlopen(dashboard_request, timeout=3) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_owner_secret_rejects_fewer_than_six_characters(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "at least 6 characters"):
                make_handler(root=ROOT, db_path=Path(temp) / "db.sqlite3", owner_token="12345")

    def test_owner_master_password_requires_exactly_six_digits(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OWNER_MASTER_PASSWORD": "abc123", "OWNER_API_TOKEN": ""}):
            with self.assertRaisesRegex(ValueError, "exactly six digits"):
                make_handler(root=ROOT, db_path=Path(temp) / "db.sqlite3")

    def test_private_api_fails_closed_when_no_owner_token_exists(self):
        with patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as temp:
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(root=ROOT, db_path=Path(temp) / "db.sqlite3", owner_token=""))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/health", timeout=3) as response:
                    health = json.loads(response.read())
                self.assertEqual(health["checks"]["authentication"], "NOT_CONFIGURED")
                self.assertEqual(health["overall"], "NOT_CONFIGURED")
                request = Request(base + "/api/dashboard", headers={"X-Owner-Token": "anything"})
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=3)
                self.assertEqual(raised.exception.code, 503)
                body = json.loads(raised.exception.read())
                self.assertEqual(body["error"]["code"], "auth_not_configured")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
