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

from backend.server import make_handler
from backend.store import Store


ROOT = Path(__file__).resolve().parents[1]


class CompanyBuilderApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {
            "AI_ROUTER_HEALTH_URL": "", "AI_ROUTER_API_KEY": "", "AI_ROUTER_BASE_URL": "",
            "AI_ROUTER_CHAT_COMPLETIONS_URL": "", "AI_ROUTER_MODEL": "",
            "OPENAI_API_BASE": "", "OPENAI_API_KEY": "",
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
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else {}

    def post(self, path: str, body: dict):
        return self.request("POST", path, body=body, token=self.token)

    def patch_api(self, path: str, body: dict):
        return self.request("PATCH", path, body=body, token=self.token)

    def get(self, path: str):
        return self.request("GET", path, token=self.token)

    def department(self, name="Content Production", code="CONTENT"):
        status, body = self.post("/api/departments", {
            "name": name, "code": code, "description": "Department for owner-managed company content.",
            "goals": ["Plan editorial work"], "kpis": ["Review cycle time"],
        })
        self.assertEqual(status, 201, body)
        return body["department"]

    def employee(self, department_id: str, *, name="AI Editor", employee_type="EMPLOYEE", manager_id="", parent_id="", role_id=""):
        payload = {"name": name, "department_id": department_id, "employee_type": employee_type,
                   "manager_employee_id": manager_id, "parent_employee_id": parent_id,
                   "job_description": "Editorial planning and review.",
                   "responsibilities": ["Plan work"], "goals": ["Improve review quality"],
                   "kpis": ["Turnaround time"], "skills": ["Editing"], "modules": ["tasks"]}
        if role_id:
            payload["role_id"] = role_id
        status, body = self.post("/api/ai-employees", payload)
        self.assertEqual(status, 201, body)
        return body["employee"]

    def test_department_manager_employee_worker_and_organization_tree_are_persisted(self):
        department = self.department()
        manager = self.employee(department["id"], name="Content Manager", employee_type="MANAGER")
        employee = self.employee(department["id"], name="AI Editor", manager_id=manager["id"])
        worker = self.employee(department["id"], name="Script Worker", employee_type="WORKER", parent_id=employee["id"])

        status, departments = self.get("/api/departments")
        self.assertEqual(status, 200)
        self.assertEqual(departments["departments"][0]["manager_employee_id"], manager["id"])
        status, employees = self.get("/api/ai-employees?status=ACTIVE")
        self.assertEqual(status, 200)
        self.assertEqual({employee["id"], manager["id"], worker["id"]}, {item["id"] for item in employees["employees"]})
        self.assertEqual(employee["id"], next(item for item in employees["employees"] if item["name"] == "AI Editor")["id"])

        status, structure = self.get("/api/company/structure")
        self.assertEqual(status, 200)
        department_node = structure["departments"][0]
        manager_node = department_node["employees"][0]
        self.assertEqual(manager_node["id"], manager["id"])
        self.assertEqual({employee["id"]}, {child["id"] for child in manager_node["children"]})
        self.assertEqual({worker["id"]}, {child["id"] for child in manager_node["children"][0]["children"]})

        status, profile = self.get(f"/api/ai-employees/{employee['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(profile["employee"]["manager_employee_id"], manager["id"])
        self.assertIn("USE_AI_MODEL", profile["employee"]["permissions"])
        self.assertEqual(profile["employee"]["responsibilities"], ["Plan work"])
        self.assertEqual(profile["employee"]["modules"], ["tasks"])
        self.assertEqual(profile["tasks"], [])

        status, blocked_module = self.patch_api(f"/api/ai-employees/{employee['id']}", {"modules": ["security"]})
        self.assertEqual(status, 400)
        self.assertEqual(blocked_module["error"]["code"], "invalid_employee_module")

    def test_department_mismatch_and_reporting_cycle_are_rejected(self):
        first = self.department("Content Production", "CONTENT")
        second = self.department("Research", "RESEARCH")
        manager_a = self.employee(first["id"], name="Manager A", employee_type="MANAGER")
        manager_b = self.employee(second["id"], name="Manager B", employee_type="MANAGER")
        status, body = self.post("/api/ai-employees", {
            "name": "Wrong Department", "department_id": first["id"], "employee_type": "EMPLOYEE",
            "manager_employee_id": manager_b["id"],
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "manager_department_mismatch")

        lower_manager = self.employee(first["id"], name="Manager C", employee_type="MANAGER", manager_id=manager_a["id"])
        status, body = self.patch_api(f"/api/ai-employees/{manager_a['id']}", {"manager_employee_id": lower_manager["id"]})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "organization_cycle")

    def test_roles_permissions_and_owner_only_mutations(self):
        status, roles_payload = self.get("/api/roles")
        self.assertEqual(status, 200)
        self.assertTrue(any(role["code"] == "AI_MANAGER" for role in roles_payload["roles"]))
        status, permissions_payload = self.get("/api/permissions")
        self.assertEqual(status, 200)
        self.assertIn("PUBLISH", {permission["code"] for permission in permissions_payload["permissions"]})

        status, role_payload = self.post("/api/roles", {
            "name": "باحث محتوى", "code": "CONTENT_RESEARCHER", "description": "Research-only access.",
            "permissions": ["VIEW_DATA", "USE_AI_MODEL"],
        })
        self.assertEqual(status, 201, role_payload)
        role = role_payload["role"]
        self.assertEqual(set(role["permissions"]), {"VIEW_DATA", "USE_AI_MODEL"})
        status, updated = self.patch_api(f"/api/roles/{role['id']}", {"permissions": ["VIEW_DATA"]})
        self.assertEqual(status, 200)
        self.assertEqual(updated["role"]["permissions"], ["VIEW_DATA"])

        department = self.department()
        employee = self.employee(department["id"], name="Researcher", role_id=role["id"])
        status, denied = self.patch_api(f"/api/ai-employees/{employee['id']}/permissions", {"permissions": ["UNKNOWN"]})
        self.assertEqual(status, 400)
        status, changed = self.patch_api(f"/api/ai-employees/{employee['id']}/permissions", {"permissions": ["VIEW_DATA"]})
        self.assertEqual(status, 200)
        self.assertEqual(changed["employee"]["permissions"], ["VIEW_DATA"])
        status, edited = self.patch_api(f"/api/ai-employees/{employee['id']}", {"permissions": ["VIEW_DATA", "CREATE_TASK"]})
        self.assertEqual(status, 200)
        self.assertEqual(set(edited["employee"]["permissions"]), {"VIEW_DATA", "CREATE_TASK"})
        status, blocked = self.request("DELETE", f"/api/roles/{role['id']}", token=self.token)
        self.assertEqual(status, 409)
        self.assertEqual(blocked["error"]["code"], "role_has_employees")

        status, unauthenticated = self.request("POST", "/api/roles", body={"name": "No Access", "code": "NO_ACCESS"})
        self.assertEqual(status, 401)

    def test_employee_status_task_and_delete_guards(self):
        department = self.department()
        manager = self.employee(department["id"], name="Task Manager", employee_type="MANAGER")
        employee = self.employee(department["id"], name="Assigned Worker", manager_id=manager["id"])
        status, task_payload = self.post(f"/api/ai-employees/{employee['id']}/tasks", {
            "title": "Draft first outline", "description": "Prepare a structured outline.",
            "priority": "HIGH", "approval_required": True,
        })
        self.assertEqual(status, 201, task_payload)
        task = task_payload["task"]
        self.assertEqual(task["assigned_employee_id"], employee["id"])
        self.assertTrue(task["approval_required"])
        status, profile = self.get(f"/api/ai-employees/{employee['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(profile["tasks"][0]["id"], task["id"])
        self.assertTrue(any(event["object_id"] == task["id"] for event in profile["activity"]))

        status, paused = self.patch_api(f"/api/ai-employees/{employee['id']}", {"status": "PAUSED"})
        self.assertEqual(status, 200)
        self.assertEqual(paused["employee"]["status"], "PAUSED")
        status, dashboard = self.get("/api/dashboard")
        self.assertEqual(status, 200)
        self.assertEqual(dashboard["company_builder"]["paused_employees"], 1)

        status, forbidden = self.request("DELETE", f"/api/ai-employees/{employee['id']}", token=self.token)
        self.assertEqual(status, 409)
        self.assertEqual(forbidden["error"]["code"], "employee_has_dependents")
        status, blocked_department = self.request("DELETE", f"/api/departments/{department['id']}", token=self.token)
        self.assertEqual(status, 409)
        self.assertEqual(blocked_department["error"]["code"], "department_has_employees")

    def test_tools_knowledge_and_workflow_are_real_and_secrets_are_not_stored(self):
        status, tool_payload = self.post("/api/tools", {
            "name": "Editorial QA", "tool_type": "internal", "endpoint_ref": "quality-checker-v1",
            "required_permission": "USE_TOOL",
        })
        self.assertEqual(status, 201, tool_payload)
        tool = tool_payload["tool"]
        self.assertEqual(tool["name"], "Editorial QA")
        status, bad_tool = self.post("/api/tools", {
            "name": "Unsafe", "tool_type": "API", "endpoint_ref": "https://service.example/?api_key=very-long-secret-value-12345",
        })
        self.assertEqual(status, 400)
        self.assertEqual(bad_tool["error"]["code"], "secret_material_rejected")

        status, knowledge_payload = self.post("/api/knowledge-sources", {
            "name": "Editorial Policy", "source_type": "Policy", "description": "Approved editorial policy.",
            "content": "Every article needs an editor review before publication.",
        })
        self.assertEqual(status, 201, knowledge_payload)
        knowledge = knowledge_payload["knowledge_source"]
        self.assertNotIn("content", knowledge)
        status, index = self.get("/api/knowledge-sources")
        self.assertEqual(status, 200)
        self.assertNotIn("content", index["knowledge_sources"][0])

        status, workflow_error = self.post("/api/workflows", {"name": "Empty workflow", "steps": []})
        self.assertEqual(status, 400)
        status, workflow_payload = self.post("/api/workflows", {
            "name": "Editorial review", "description": "Draft, review, approve.",
            "status": "DRAFT", "steps": ["Draft", "Review", "Approval"],
        })
        self.assertEqual(status, 201, workflow_payload)
        self.assertEqual([step["position"] for step in workflow_payload["workflow"]["steps"]], [1, 2, 3])

    def test_ai_employee_test_requires_router_and_never_returns_a_fake_answer(self):
        department = self.department()
        employee = self.employee(department["id"], name="Real AI Test")
        status, body = self.post(f"/api/ai-employees/{employee['id']}/test", {"message": "Answer this test prompt."})
        self.assertEqual(status, 503)
        self.assertEqual(body["error"]["code"], "ai_router_not_configured")
        self.assertNotIn("response", body)

    def test_ai_employee_test_uses_router_and_only_authorized_knowledge(self):
        department = self.department()
        employee = self.employee(department["id"], name="Knowledge Tester")
        status, knowledge_payload = self.post("/api/knowledge-sources", {
            "name": "Allowed Handbook", "source_type": "Policy", "content": "Use the approved two-step review process.",
        })
        self.assertEqual(status, 201)
        source_id = knowledge_payload["knowledge_source"]["id"]
        status, updated = self.patch_api(f"/api/ai-employees/{employee['id']}", {"knowledge_source_ids": [source_id]})
        self.assertEqual(status, 200)

        calls=[]
        def fake_router(url, *, token="", body=None):
            calls.append((url,token,body))
            if body is None:
                return {"data":[{"id":"test-model"}]}
            return {"choices":[{"message":{"content":"Router response: two-step review."}}]}

        with patch.dict("os.environ", {"AI_ROUTER_BASE_URL":"https://router.example/v1", "AI_ROUTER_API_KEY":"test-router-token"}), patch("backend.server._router_json_request", side_effect=fake_router):
            status, result = self.post(f"/api/ai-employees/{employee['id']}/test", {"message":"Explain the review process."})
        self.assertEqual(status, 200, result)
        self.assertEqual(result["result"]["response"], "Router response: two-step review.")
        self.assertEqual(result["result"]["model"], "test-model")
        self.assertEqual(result["knowledge_sources_used"], 1)
        self.assertIn("Use the approved two-step review process.", calls[1][2]["messages"][0]["content"])
        self.assertEqual(calls[1][1], "test-router-token")

        store=Store(self.temp.name + "/test.sqlite3")
        with store.connect() as db:
            activity_text=" ".join(row[0] for row in db.execute("SELECT result || error FROM activity_logs").fetchall())
        self.assertNotIn("Explain the review process", activity_text)


if __name__ == "__main__":
    import unittest
    unittest.main()
