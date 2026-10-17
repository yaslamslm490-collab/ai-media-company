from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ROOT = Path(__file__).resolve().parents[1]
from backend.collaboration import Collaboration, handle_mcp  # noqa: E402
from backend.company_builder import CompanyBuilderStore  # noqa: E402
from backend.server import make_handler  # noqa: E402
from backend.store import Store  # noqa: E402


class CollaborationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "collab.sqlite3")
        self.store.initialize()
        CompanyBuilderStore(self.store).initialize()
        self.service = Collaboration(self.store)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_shared_task_update_deduplicates_external_event_and_keeps_existing_task_table(self):
        task = self.service.create_task("مراجعة خطة نشر", "نتيجة اختبار داخل قاعدة مؤقتة")
        first = self.service.add_update(task["id"], "نتيجة Manus التجريبية", "manus", "RESULT", "evt-1")
        second = self.service.add_update(task["id"], "نتيجة مختلفة لنفس الحدث", "manus", "RESULT", "evt-1")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.store.get_task(task["id"])["title"], "مراجعة خطة نشر")
        updates = self.service.task_updates(task["id"])
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["content"], "نتيجة Manus التجريبية")

    def test_sync_requires_confirmed_no_background_work_before_completed(self):
        task = self.service.create_task("اختبار ربط Manus")
        with patch.dict(os.environ, {"MANUS_API_KEY": "test-key-only"}):
            with patch("backend.collaboration.manus_request") as request:
                request.return_value = {"ok": True, "task_id": "manus_test_001", "task_url": "https://manus.im/app/manus_test_001"}
                link = self.service.submit_to_manus(task["id"])
                self.assertEqual(link["external_task_id"], "manus_test_001")
                request.side_effect = [
                    {"ok": True, "task": {"status": "stopped", "has_running_background_jobs": True}},
                    {"ok": True, "messages": [{"id": "msg-1", "assistant_message": {"content": "نتيجة اختبار Manus"}}]},
                ]
                pending = self.service.sync_manus(task["id"])
                self.assertEqual(pending["task_status"], "IN_PROGRESS")
                self.assertTrue(pending["result_saved"])
                request.side_effect = [
                    {"ok": True, "task": {"status": "stopped", "has_running_background_jobs": False}},
                    {"ok": True, "messages": [{"id": "msg-1", "assistant_message": {"content": "نتيجة اختبار Manus"}}]},
                ]
                completed = self.service.sync_manus(task["id"])
        self.assertEqual(completed["task_status"], "COMPLETED")
        self.assertEqual(len(self.service.task_updates(task["id"])), 2)

    def test_webhook_signature_verifies_exact_url_timestamp_and_raw_body(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = private.public_key().public_bytes(serialization.Encoding.PEM,
                                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        raw = json.dumps({"event_id": "evt", "event_type": "task_created", "task_detail": {"task_id": "remote"}}, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        url = "https://nada.example.test/api/collaboration/manus/webhook"
        signed = f"{timestamp}.{url}.{hashlib.sha256(raw).hexdigest()}".encode()
        signature = base64.b64encode(private.sign(signed, padding.PKCS1v15(), hashes.SHA256())).decode()
        with patch.dict(os.environ, {"MANUS_WEBHOOK_PUBLIC_KEY": public_pem}):
            self.assertTrue(self.service.verify_webhook(raw, signature, timestamp, url))
            self.assertFalse(self.service.verify_webhook(raw, signature, "1", url))
            self.assertFalse(self.service.verify_webhook(raw + b"!", signature, timestamp, url))

    def test_manus_webhook_events_are_idempotent_and_write_one_result(self):
        task = self.service.create_task("حدث Manus")
        self.store.link_collaboration_task(task["id"], "manus", "remote-task-001",
                                           "https://manus.im/app/remote-task-001", "running")
        event = {"event_id": "webhook-event-001", "event_type": "task_stopped", "task_detail": {
            "task_id": "remote-task-001", "stop_reason": "ask", "message": "أحتاج معلومة إضافية."}}
        first = self.service.receive_webhook(event)
        second = self.service.receive_webhook(event)
        self.assertTrue(first["linked"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(self.store.get_task(task["id"])["status"], "WAITING_APPROVAL")
        self.assertEqual(len(self.service.task_updates(task["id"])), 1)

    def test_mcp_auth_fails_closed_if_token_is_missing_or_too_short(self):
        with patch.dict(os.environ, {"NADA_MCP_TOKEN": ""}):
            with self.assertRaisesRegex(Exception, "not configured"):
                handle_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, "", self.service)
        with patch.dict(os.environ, {"NADA_MCP_TOKEN": "short"}):
            with self.assertRaisesRegex(Exception, "not configured"):
                handle_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, "Bearer short", self.service)


class EmbeddedMCPHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.token = "unit-test-mcp-token-" + "x" * 40
        self.owner_token = "test-owner-" + secrets.token_urlsafe(32)
        self.env_patch = patch.dict(os.environ, {
            "NADA_MCP_TOKEN": self.token,
            "MANUS_API_KEY": "",
            "MANUS_API_TOKEN": "",
            "PUBLIC_BASE_URL": "",
            "RENDER_EXTERNAL_URL": "",
            "MANUS_WEBHOOK_PUBLIC_KEY": "",
        })
        self.env_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            root=ROOT, db_path=Path(self.temp.name) / "server.sqlite3", owner_token=self.owner_token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.env_patch.stop()
        self.temp.cleanup()

    def call_mcp(self, payload: dict, *, authorization: str | None = None):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if authorization:
            headers["Authorization"] = authorization
        request = Request(self.base + "/mcp", data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=4) as response:
                return response.status, json.loads(response.read().decode()), response.headers
        except HTTPError as error:
            return error.code, json.loads(error.read().decode()), error.headers

    def test_streamable_http_initializes_lists_tools_and_writes_to_canonical_task_database(self):
        status, payload, headers = self.call_mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, authorization=f"Bearer {self.token}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["result"]["serverInfo"]["name"], "nada-ai-collaboration")
        self.assertEqual(headers.get("MCP-Protocol-Version"), "2025-03-26")
        status, listing, _ = self.call_mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, authorization=f"Bearer {self.token}")
        self.assertEqual(status, 200)
        self.assertIn("create_work_task", {tool["name"] for tool in listing["result"]["tools"]})
        status, created, _ = self.call_mcp({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "create_work_task", "arguments": {"title": "مهمة من MCP", "description": "اختبار HTTP فعلي"}}}, authorization=f"Bearer {self.token}")
        self.assertEqual(status, 200)
        task = created["result"]["structuredContent"]["task"]
        self.assertEqual(task["title"], "مهمة من MCP")
        # Verify the same record through the authenticated REST view of the existing app.
        request = Request(self.base + "/api/tasks", headers={"X-Owner-Token": self.owner_token})
        with urlopen(request, timeout=4) as response:
            tasks = json.loads(response.read().decode())["tasks"]
        self.assertIn(task["id"], {item["id"] for item in tasks})

    def test_mcp_refuses_missing_or_wrong_bearer(self):
        status, _, _ = self.call_mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(status, 401)
        status, _, _ = self.call_mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, authorization="Bearer incorrect-token")
        self.assertEqual(status, 401)

    def test_health_reports_database_online_and_unconfigured_integrations_without_false_success(self):
        request = Request(self.base + "/api/health")
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode())
        collaboration = payload["checks"]["collaboration"]
        self.assertEqual(collaboration["application_tasks"], "ONLINE")
        self.assertEqual(collaboration["manus_api"], "NOT_CONFIGURED")
        self.assertEqual(collaboration["mcp_endpoint"], "CONFIGURED")
        self.assertEqual(collaboration["public_https"], "NOT_CONFIGURED")

    def test_render_external_url_is_accepted_for_registered_manus_webhook(self):
        origin = "https://nada-ai.onrender.com"
        payload = {"event_id": "render-probe-1", "event_type": "task_created",
                   "task_detail": {"task_id": "unlinked-render-task"}}
        raw = json.dumps(payload, separators=(",", ":")).encode()
        request = Request(self.base + "/api/collaboration/manus/webhook", data=raw, method="POST",
                          headers={"Content-Type": "application/json", "X-Webhook-Signature": "test",
                                   "X-Webhook-Timestamp": str(int(time.time()))})
        service = Collaboration(Store(Path(self.temp.name) / "server.sqlite3"))
        with patch.dict(os.environ, {"PUBLIC_BASE_URL": "", "RENDER_EXTERNAL_URL": origin}):
            self.assertEqual(service.public_origin(), origin)
            self.assertEqual(service._webhook_url(), origin + "/api/collaboration/manus/webhook")
            with patch.object(Collaboration, "verify_webhook", return_value=True) as verify:
                with urlopen(request, timeout=4) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["accepted"])
                self.assertEqual(verify.call_args.args[-1], origin + "/api/collaboration/manus/webhook")


if __name__ == "__main__":
    unittest.main()
