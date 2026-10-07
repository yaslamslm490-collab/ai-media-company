from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
from backend.integrations import IntegrationStore  # noqa: E402
from backend.server import make_handler  # noqa: E402
from backend.store import Store  # noqa: E402


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size=-1):
        return self.body


class ExternalIntegrationsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "integrations.sqlite3"
        self.owner_token = "owner-test-token-with-more-than-24-chars"
        self.key = Fernet.generate_key().decode("ascii")
        self.env_patch = patch.dict(os.environ, {"AI_MEDIA_VAULT_KEY": self.key})
        self.env_patch.start()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(root=ROOT, db_path=self.db_path, owner_token=self.owner_token),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.integration_store = IntegrationStore(Store(self.db_path))

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.env_patch.stop()
        self.temp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None, *, authenticated: bool = True):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        if authenticated:
            headers["X-Owner-Token"] = self.owner_token
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=3) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if raw else {}

    def create_account(self, label: str, provider: str = "Runway", service: str = "VIDEO", credential: str | None = None):
        return self.request("POST", "/api/external-integrations/accounts", {
            "label": label,
            "provider": provider,
            "service": service,
            "credential": credential or f"TEST_CREDENTIAL_{label}_0123456789abcdef",
        })

    def test_owner_authentication_and_secret_non_disclosure(self):
        status, _ = self.request("GET", "/api/external-integrations", authenticated=False)
        self.assertEqual(status, 401)

        secret = "TEST_SECRET_CREDENTIAL_0123456789abcdef"
        status, result = self.create_account("main", credential=secret)
        self.assertEqual(status, 201)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("credential", result["account"])
        self.assertTrue(result["account"]["secret_configured"])

        with sqlite3.connect(self.db_path) as db:
            ciphertext = db.execute("SELECT secret_ciphertext FROM external_account_secrets").fetchone()[0]
        self.assertNotIn(secret, ciphertext)
        self.assertEqual(self.integration_store._credential_for_dispatch(result["account"]["id"]), secret)

        status, activity = self.request("GET", "/api/activity")
        self.assertEqual(status, 200)
        self.assertNotIn(secret, json.dumps(activity, ensure_ascii=False))

    def test_official_provider_connection_checks_are_read_only_and_hide_responses(self):
        status, kling = self.create_account("video-main", provider="Kling", service="VIDEO")
        self.assertEqual(status, 201)
        status, eleven = self.create_account("voice-main", provider="ElevenLabs", service="AUDIO")
        self.assertEqual(status, 201)
        status, mismatch = self.create_account("wrong-service", provider="Kling", service="AUDIO")
        self.assertEqual(status, 400)
        self.assertEqual(mismatch["error"]["code"], "provider_service_mismatch")

        with patch("backend.integrations.urlopen", side_effect=[
            _FakeResponse({"code": 0, "data": []}),
            _FakeResponse({"user_id": "private-user-id"}),
        ]) as outbound:
            status, kling_result = self.request("POST", f"/api/external-integrations/accounts/{kling['account']['id']}/test", {})
            self.assertEqual(status, 200)
            self.assertEqual(kling_result["connection"]["status"], "ONLINE")
            self.assertNotIn("private-user-id", json.dumps(kling_result))
            status, eleven_result = self.request("POST", f"/api/external-integrations/accounts/{eleven['account']['id']}/test", {})
            self.assertEqual(status, 200)
            self.assertEqual(eleven_result["connection"]["status"], "ONLINE")
            self.assertNotIn("private-user-id", json.dumps(eleven_result))

        requests = [call.args[0] for call in outbound.call_args_list]
        self.assertEqual([request.get_method() for request in requests], ["GET", "GET"])
        self.assertIn("external_task_ids=aimediaos-health-", requests[0].full_url)
        self.assertIn("Bearer ", requests[0].headers.get("Authorization", ""))
        self.assertEqual(requests[1].full_url, "https://api.elevenlabs.io/v1/user")
        self.assertTrue(any(key.lower() == "xi-api-key" for key in requests[1].headers))

    def test_rotation_is_round_robin_per_provider_and_service(self):
        self.assertEqual(self.create_account("video-one")[0], 201)
        self.assertEqual(self.create_account("video-two")[0], 201)
        self.assertEqual(self.create_account("audio-one", provider="Runway", service="AUDIO")[0], 201)

        first = self.request("POST", "/api/external-integrations/rotate", {"provider": "runway", "service": "VIDEO"})[1]["account"]
        second = self.request("POST", "/api/external-integrations/rotate", {"provider": "Runway", "service": "VIDEO"})[1]["account"]
        third = self.request("POST", "/api/external-integrations/rotate", {"provider": "RUNWAY", "service": "VIDEO"})[1]["account"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["id"], third["id"])
        self.assertNotIn("credential", first)

        audio = self.request("POST", "/api/external-integrations/rotate", {"provider": "Runway", "service": "AUDIO"})[1]["account"]
        self.assertEqual(audio["label"], "audio-one")

    def test_both_service_account_is_eligible_for_each_service(self):
        self.assertEqual(self.create_account("shared", provider="OpenAI", service="BOTH")[0], 201)
        for service in ("VIDEO", "AUDIO"):
            status, result = self.request("POST", "/api/external-integrations/rotate", {"provider": "OpenAI", "service": service})
            self.assertEqual(status, 200)
            self.assertEqual(result["account"]["label"], "shared")

    def test_twenty_account_limit_and_five_item_pagination(self):
        for index in range(20):
            status, _ = self.create_account(f"account-{index:02d}")
            self.assertEqual(status, 201)
        status, rejected = self.create_account("account-20")
        self.assertEqual(status, 409)
        self.assertEqual(rejected["error"]["code"], "account_pool_full")
        status, first_page = self.request("GET", "/api/external-integrations")
        self.assertEqual(status, 200)
        self.assertEqual(first_page["summary"]["total_accounts"], 20)
        self.assertEqual(first_page["summary"]["max_accounts"], 20)
        self.assertEqual(len(first_page["accounts"]), 5)
        self.assertTrue(first_page["pagination"]["has_more"])
        status, last_page = self.request("GET", "/api/external-integrations?limit=5&offset=15")
        self.assertEqual(status, 200)
        self.assertEqual(len(last_page["accounts"]), 5)
        self.assertFalse(last_page["pagination"]["has_more"])

    def test_prefix_code_is_unique_searchable_and_customizable(self):
        status, first = self.create_account("first")
        self.assertEqual(status, 201)
        status, second = self.create_account("second")
        self.assertEqual(status, 201)
        self.assertEqual(first["account"]["account_code"], "#RUNWAY-001")
        self.assertEqual(second["account"]["account_code"], "#RUNWAY-002")
        status, custom = self.request("POST", "/api/external-integrations/accounts", {
            "label": "telegram-proxy", "provider": "Runway", "service": "VIDEO",
            "prefix": "TG", "region_code": "EG", "credential": "TEST_CREDENTIAL_TG_0123456789abcdef",
        })
        self.assertEqual(status, 201)
        self.assertEqual(custom["account"]["account_code"], "#TG-001")
        self.assertEqual(custom["account"]["region_code"], "EG")
        status, result = self.request("GET", "/api/external-integrations?q=%23RUNWAY-002")
        self.assertEqual(status, 200)
        self.assertEqual(result["pagination"]["total"], 1)
        self.assertEqual([item["account_code"] for item in result["accounts"]], ["#RUNWAY-002"])
    def test_problem_filter_only_returns_paused_or_unhealthy_accounts(self):
        status, normal = self.create_account("normal")
        self.assertEqual(status, 201)
        status, paused = self.create_account("paused")
        self.assertEqual(status, 201)
        self.assertEqual(self.request("PATCH", f"/api/external-integrations/accounts/{paused['account']['id']}", {"status": "PAUSED"})[0], 200)
        status, result = self.request("GET", "/api/external-integrations?issues=1")
        self.assertEqual(status, 200)
        self.assertEqual([item["account_code"] for item in result["accounts"]], [paused["account"]["account_code"]])

    def test_paused_accounts_are_not_selected_and_deletion_removes_secret(self):
        status, created = self.create_account("pause-me")
        self.assertEqual(status, 201)
        account_id = created["account"]["id"]
        status, _ = self.request("PATCH", f"/api/external-integrations/accounts/{account_id}", {"status": "PAUSED"})
        self.assertEqual(status, 200)
        status, error = self.request("POST", "/api/external-integrations/rotate", {"provider": "Runway", "service": "VIDEO"})
        self.assertEqual(status, 409)
        self.assertEqual(error["error"]["code"], "no_active_account")
        status, result = self.request("DELETE", f"/api/external-integrations/accounts/{account_id}")
        self.assertEqual(status, 200)
        self.assertTrue(result["deleted"])
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM external_account_secrets WHERE account_id=?", (account_id,)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
