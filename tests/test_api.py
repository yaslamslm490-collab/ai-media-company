from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

from backend.server import load_local_env, make_handler, system_health  # noqa: E402
from backend.store import Store  # noqa: E402


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {
            "AI_ROUTER_HEALTH_URL": "", "AI_ROUTER_API_KEY": "", "OPENAI_API_BASE": "", "OPENAI_API_KEY": "",
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

    def request(self, method: str, path: str, *, body: dict | None = None, token: str | None = None):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if token is not None:
            headers["X-Owner-Token"] = token
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                raw = response.read()
                if not raw:
                    return response.status, {}
                try:
                    return response.status, json.loads(raw)
                except json.JSONDecodeError:
                    return response.status, raw.decode("utf-8", errors="replace")
        except HTTPError as error:
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

    def test_ai_router_falls_back_to_authenticated_openai_compatible_models_endpoint(self):
        store = Store(Path(self.temp.name) / "health-ai.sqlite3")
        store.initialize()
        env = {"OPENAI_API_BASE": "https://router.example/v1", "OPENAI_API_KEY": "test-ai-key"}
        with patch("backend.server._probe", return_value="ONLINE") as probe:
            health = system_health(store, self.token, environ=env)
        self.assertEqual(health["checks"]["ai_router"], "ONLINE")
        probe.assert_any_call("https://router.example/v1/models", "test-ai-key")

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

    def test_static_server_does_not_expose_backend_database_or_environment_files(self):
        for path in ["/backend/store.py", "/data/secret.sqlite3", "/.env", "/tests/test_api.py"]:
            status, _ = self.request("GET", path)
            self.assertEqual(status, 404, path)
        status, _ = self.request("GET", "/")
        self.assertEqual(status, 200)


class AuthNotConfiguredTest(unittest.TestCase):
    def test_private_api_fails_closed_when_no_owner_token_exists(self):
        with tempfile.TemporaryDirectory() as temp:
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
