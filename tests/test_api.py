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

from backend.server import make_handler  # noqa: E402


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {
            "AI_ROUTER_HEALTH_URL": "", "AI_ROUTER_API_KEY": "",
            "MANUS_HEALTH_URL": "", "MANUS_API_TOKEN": "",
            "GITHUB_HEALTH_URL": "", "GITHUB_TOKEN": "", "EXTERNAL_HEALTH_URLS": "",
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

    def test_health_checks_backend_and_database_and_does_not_claim_missing_integrations(self):
        status, payload = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["checks"]["backend"], "ONLINE")
        self.assertEqual(payload["checks"]["database"], "ONLINE")
        self.assertEqual(payload["checks"]["authentication"], "ONLINE")
        self.assertEqual(payload["checks"]["github"], "NOT_CONFIGURED")
        self.assertEqual(payload["checks"]["manus"], "NOT_CONFIGURED")

    def test_private_data_requires_owner_authentication(self):
        status, payload = self.request("GET", "/api/dashboard")
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
        self.assertIsNone(payload["company"]["active_characters"]["value"])
        self.assertEqual(payload["company"]["active_characters"]["status"], "NOT_CONFIGURED")
        self.assertEqual(payload["recent_activity"], [])

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
