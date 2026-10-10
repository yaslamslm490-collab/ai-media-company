from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from bridge import server as bridge


class ManusBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "bridge.sqlite3")
        self.env_patch = patch.dict(os.environ, {
            "BRIDGE_DB_PATH": self.db_path,
            "BRIDGE_API_TOKEN": "bridge-test-token-0123456789abcdef",
            "MANUS_API_KEY": "test-manus-key-never-real",
            "BRIDGE_PUBLIC_URL": "https://bridge.test.example",
            "MANUS_CONNECTOR_IDS": "github-connector-test",
        }, clear=False)
        self.env_patch.start()
        bridge.initialize_db()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), bridge.BridgeHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        self.env_patch.stop()
        self.temp.cleanup()

    def request(self, method: str, path: str, payload: dict | None = None, *, token: str | None = None):
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except Exception as error:
            if hasattr(error, "code"):
                return error.code, json.loads(error.read().decode("utf-8"))
            raise

    def test_health_is_public_and_does_not_return_secret_values(self):
        status, result = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(result["database_ready"])
        encoded = json.dumps(result)
        self.assertNotIn("test-manus-key", encoded)
        self.assertNotIn("bridge-test-token", encoded)

    def test_private_routes_require_bearer_token(self):
        status, result = self.request("POST", "/v1/tasks", {"prompt": "test"})
        self.assertEqual(status, 401)
        self.assertEqual(result["error"]["code"], "unauthorized")

    def test_submit_task_uses_private_visibility_and_stores_task(self):
        expected = {"ok": True, "task_id": "task_test123", "task_title": "NADA test", "task_url": "https://manus.im/app/task_test123"}
        with patch.object(bridge, "manus_request", return_value=expected) as call:
            status, result = self.request("POST", "/v1/tasks", {"title": "NADA test", "prompt": "Review NADA AI safely."}, token="bridge-test-token-0123456789abcdef")
        self.assertEqual(status, 202)
        self.assertEqual(result["task_id"], "task_test123")
        request_body = call.call_args.args[2]
        self.assertEqual(request_body["share_visibility"], "private")
        self.assertEqual(request_body["message"]["connectors"], ["github-connector-test"])
        self.assertEqual(bridge.get_task("task_test123")["status"], "running")

    def test_early_stopped_webhook_is_not_overwritten_by_create_response(self):
        event = {
            "event_id": "early-stop-1",
            "event_type": "task_stopped",
            "task_detail": {"task_id": "task_race1", "message": "Done", "stop_reason": "finish"},
        }
        self.assertTrue(bridge.record_webhook_event(event))
        with patch.object(bridge, "manus_request", return_value={"ok": True, "task_id": "task_race1"}):
            result = bridge.submit_task({"prompt": "Quick task"})
        self.assertEqual(result["status"], "stopped_unverified")

    def test_followup_cannot_target_a_task_outside_the_bridge(self):
        with patch.object(bridge, "manus_request") as call:
            status, result = self.request(
                "POST", "/v1/tasks/not_registered/messages", {"content": "continue"},
                token="bridge-test-token-0123456789abcdef",
            )
        self.assertEqual(status, 404)
        self.assertEqual(result["error"]["code"], "task_not_found")
        call.assert_not_called()

    def test_webhook_event_is_idempotent_and_waiting_question_is_recorded(self):
        event = {
            "event_id": "event-1",
            "event_type": "task_stopped",
            "task_detail": {
                "task_id": "task_wait1",
                "task_title": "Need an answer",
                "task_url": "https://manus.im/app/task_wait1",
                "message": "Which option do you prefer?",
                "stop_reason": "ask",
                "attachments": [],
                "question_expectation": {"options": ["A", "B"]},
            },
        }
        self.assertTrue(bridge.record_webhook_event(event))
        self.assertFalse(bridge.record_webhook_event(event))
        task = bridge.get_task("task_wait1")
        self.assertEqual(task["status"], "waiting_for_input")
        self.assertEqual(task["message"], "Which option do you prefer?")

    def test_stopped_task_is_complete_only_after_detail_confirms_no_background_jobs(self):
        event = {
            "event_id": "finish-1", "event_type": "task_stopped",
            "task_detail": {"task_id": "task_finish1", "message": "Final report", "stop_reason": "finish"},
        }
        bridge.record_webhook_event(event)
        with patch.object(bridge, "manus_request", return_value={"task": {"status": "stopped", "has_running_background_jobs": False}}):
            completed = bridge.get_task("task_finish1")
        self.assertEqual(completed["status"], "completed")

        event["event_id"] = "finish-2"
        event["task_detail"]["task_id"] = "task_bg1"
        bridge.record_webhook_event(event)
        with patch.object(bridge, "manus_request", return_value={"task": {"status": "stopped", "has_running_background_jobs": True}}):
            still_running = bridge.get_task("task_bg1")
        self.assertEqual(still_running["status"], "running_background")

    def test_webhook_signature_checks_url_body_and_five_minute_window(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        url = "https://bridge.test.example/webhooks/manus"
        body = b'{"event_id":"e1"}'
        timestamp = str(int(time.time()))
        digest = hashlib.sha256(body).hexdigest()
        signed = f"{timestamp}.{url}.{digest}".encode("utf-8")
        signature = base64.b64encode(private_key.sign(signed, padding.PKCS1v15(), hashes.SHA256())).decode("ascii")
        self.assertTrue(bridge.verify_webhook_signature(public_pem, url, body, signature, timestamp))
        self.assertFalse(bridge.verify_webhook_signature(public_pem, url + "/changed", body, signature, timestamp))
        self.assertFalse(bridge.verify_webhook_signature(public_pem, url, body, signature, str(int(timestamp) - 301)))

    def test_webhook_route_rejects_unsigned_request(self):
        payload = {"event_id": "e1", "event_type": "task_created", "task_detail": {"task_id": "task_1"}}
        status, result = self.request("POST", "/webhooks/manus", payload)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "missing_signature")

    def test_signed_webhook_route_stores_event_and_acks_setup_probe(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        def post_signed(payload: dict):
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            timestamp = str(int(time.time()))
            url = bridge.webhook_url()
            digest = hashlib.sha256(body).hexdigest()
            signed = f"{timestamp}.{url}.{digest}".encode("utf-8")
            signature = base64.b64encode(private_key.sign(signed, padding.PKCS1v15(), hashes.SHA256())).decode("ascii")
            request = Request(
                self.base + "/webhooks/manus",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                    "X-Webhook-Timestamp": timestamp,
                },
                method="POST",
            )
            with patch.object(bridge, "_manus_webhook_public_key", return_value=public_pem):
                try:
                    with urlopen(request, timeout=3) as response:
                        return response.status, json.loads(response.read().decode("utf-8"))
                except Exception as error:
                    if hasattr(error, "code"):
                        return error.code, json.loads(error.read().decode("utf-8"))
                    raise

        status, result = post_signed({
            "event_id": "event-signed-1",
            "event_type": "task_created",
            "task_detail": {"task_id": "task_signed1", "task_title": "Signed task"},
        })
        self.assertEqual(status, 200)
        self.assertFalse(result["duplicate"])
        self.assertEqual(bridge.get_task("task_signed1")["status"], "running")

        status, result = post_signed({"event_type": "webhook_test"})
        self.assertEqual(status, 200)
        self.assertTrue(result["ignored"])

    def test_invalid_prompts_are_rejected_without_calling_manus(self):
        with patch.object(bridge, "manus_request") as call:
            status, result = self.request("POST", "/v1/tasks", {"prompt": " "}, token="bridge-test-token-0123456789abcdef")
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "invalid_prompt")
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
