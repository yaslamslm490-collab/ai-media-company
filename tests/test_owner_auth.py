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

from backend.owner_auth import OwnerAuthError, OwnerSmsAuth
from backend.server import make_handler
from backend.store import Store

ROOT = Path(__file__).resolve().parents[1]
TEST_OTP = "123456"


def configured_env() -> dict[str, str]:
    return {
        "OWNER_PHONE_NUMBER_PRIMARY": "+1" + "5" * 10,
        "OWNER_PHONE_NUMBERS_BACKUP": json.dumps(["+44" + "7" * 10]),
        "OWNER_RECOVERY_HMAC_KEY": "h" * 48,
        "OWNER_RECOVERY_CODE": "r" * 48,
        "TWILIO_ACCOUNT_SID": "AC" + "a" * 32,
        "TWILIO_API_KEY": "SK" + "b" * 32,
        "TWILIO_API_SECRET": "secret-value-for-tests-32-characters",
        "TWILIO_VERIFY_SERVICE_SID": "VA" + "c" * 32,
    }


class MutableClock:
    def __init__(self, value: int = 1_800_000_000):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += seconds


class OwnerAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "auth.sqlite3")
        self.store.initialize()
        self.env = configured_env()
        self.clock = MutableClock()
        self.sent: list[str] = []
        self.checks: list[tuple[str, str]] = []
        self.auth = OwnerSmsAuth(
            self.store,
            env=self.env,
            sender=self._send,
            checker=self._check,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _send(self, phone: str) -> None:
        self.sent.append(phone)

    def _check(self, phone: str, code: str) -> bool:
        self.checks.append((phone, code))
        return code == TEST_OTP

    def test_targets_include_primary_and_backup_but_only_mask_numbers(self):
        targets = self.auth.targets()
        self.assertEqual([item["id"] for item in targets], ["primary", "backup-1"])
        rendered = json.dumps(targets, ensure_ascii=False)
        for secret_number in [self.env["OWNER_PHONE_NUMBER_PRIMARY"], "+44" + "7" * 10]:
            self.assertNotIn(secret_number, rendered)
        self.assertTrue(all("masked_number" in item for item in targets))

    def test_otp_is_never_stored_and_success_issues_expiring_revocable_session(self):
        target = self.auth.targets()[0]
        self.auth.request_code(target["id"])
        self.assertEqual(self.sent[-1], self.env["OWNER_PHONE_NUMBER_PRIMARY"])
        with self.store.connect() as db:
            state = dict(db.execute("SELECT * FROM owner_auth_state WHERE id='owner'").fetchone())
            self.assertEqual(state["target_id"], "primary")
            self.assertEqual(state["expires_at"], int(self.clock()) + 300)
            self.assertNotIn("otp_hash", state)
            self.assertNotIn(TEST_OTP, json.dumps(state))
        result = self.auth.verify_code("primary", TEST_OTP)
        token = result["token"]
        self.assertTrue(self.auth.authenticate(token))
        self.assertEqual(self.checks[-1][1], TEST_OTP)
        with self.store.connect() as db:
            stored = db.execute("SELECT token_hash FROM owner_sessions").fetchone()["token_hash"]
        self.assertNotEqual(stored, token)
        self.clock.advance(result["expires_in"] + 1)
        self.assertFalse(self.auth.authenticate(token))

    def test_target_must_match_the_active_challenge(self):
        self.auth.request_code("primary")
        with self.assertRaises(OwnerAuthError) as raised:
            self.auth.verify_code("backup-1", TEST_OTP)
        self.assertEqual(raised.exception.code, "otp_invalid")
        self.assertTrue(self.auth.verify_code("primary", TEST_OTP)["token"])

    def test_send_cooldown_and_window_limit_are_shared_across_trusted_numbers(self):
        self.auth.request_code("primary")
        with self.assertRaises(OwnerAuthError) as raised:
            self.auth.request_code("backup-1")
        self.assertEqual(raised.exception.code, "otp_resend_wait")
        self.clock.advance(60)
        self.auth.request_code("backup-1")
        self.clock.advance(60)
        self.auth.request_code("primary")
        self.clock.advance(60)
        with self.assertRaises(OwnerAuthError) as limited:
            self.auth.request_code("backup-1")
        self.assertEqual(limited.exception.code, "otp_rate_limited")
        self.assertEqual(len(self.sent), 3)

    def test_ten_sms_per_day_cap_cannot_be_reset_by_waiting_out_the_window(self):
        for index in range(10):
            if index in {3, 6, 9}:
                self.clock.advance(15 * 60)
            self.auth.request_code("primary")
            if index < 9:
                self.clock.advance(60)
        self.clock.advance(60)
        with self.assertRaises(OwnerAuthError) as limited:
            self.auth.request_code("primary")
        self.assertEqual(limited.exception.code, "otp_rate_limited")
        self.assertEqual(len(self.sent), 10)

    def test_five_wrong_otp_attempts_lock_the_account_for_fifteen_minutes(self):
        self.auth.request_code("primary")
        for attempt in range(4):
            with self.assertRaises(OwnerAuthError) as raised:
                self.auth.verify_code("primary", f"{attempt + 1:06d}")
            self.assertEqual(raised.exception.status, 401)
        with self.assertRaises(OwnerAuthError) as fifth:
            self.auth.verify_code("primary", "999999")
        self.assertEqual(fifth.exception.status, 429)
        with self.assertRaises(OwnerAuthError) as locked:
            self.auth.request_code("primary")
        self.assertEqual(locked.exception.status, 429)
        self.clock.advance(15 * 60)
        self.auth.request_code("primary")
        self.assertEqual(len(self.sent), 2)

    def test_expired_otp_is_refused_before_checking_with_provider(self):
        self.auth.request_code("primary")
        self.clock.advance(301)
        with self.assertRaises(OwnerAuthError) as raised:
            self.auth.verify_code("primary", TEST_OTP)
        self.assertEqual(raised.exception.code, "otp_expired")
        self.assertEqual(self.checks, [])

    def test_recovery_code_is_single_use_and_secret_rotation_reenables_new_code(self):
        self.auth.request_code("primary")
        recovery = self.env["OWNER_RECOVERY_CODE"]
        session = self.auth.verify_recovery_code(recovery)["token"]
        self.assertTrue(self.auth.authenticate(session))
        with self.assertRaises(OwnerAuthError) as invalidated:
            self.auth.verify_code("primary", TEST_OTP)
        self.assertEqual(invalidated.exception.code, "otp_invalid")
        with self.store.connect() as db:
            state = dict(db.execute("SELECT * FROM owner_auth_state WHERE id='owner'").fetchone())
            self.assertNotEqual(state["recovery_fingerprint"], recovery)
            self.assertNotEqual(state["recovery_code_hash"], recovery)
            self.assertGreater(state["recovery_used_at"], 0)
        self.env["OWNER_RECOVERY_HMAC_KEY"] = "z" * 48
        with self.assertRaises(OwnerAuthError) as key_rotation:
            self.auth.verify_recovery_code(recovery)
        self.assertEqual(key_rotation.exception.code, "recovery_code_used")
        with self.assertRaises(OwnerAuthError) as used:
            self.auth.verify_recovery_code(recovery)
        self.assertEqual(used.exception.code, "recovery_code_used")
        self.env["OWNER_RECOVERY_CODE"] = "n" * 48
        rotated = self.auth.verify_recovery_code(self.env["OWNER_RECOVERY_CODE"])
        self.assertTrue(self.auth.authenticate(rotated["token"]))

    def test_recovery_attempts_are_limited_including_malformed_values(self):
        for _ in range(4):
            with self.assertRaises(OwnerAuthError) as raised:
                self.auth.verify_recovery_code("x")
            self.assertEqual(raised.exception.status, 401)
        with self.assertRaises(OwnerAuthError) as fifth:
            self.auth.verify_recovery_code("x")
        self.assertEqual(fifth.exception.status, 429)

    def test_public_auth_endpoints_return_masked_targets_and_issue_revoke_session(self):
        sent: list[str] = []
        env_patch = patch.dict(os.environ, configured_env(), clear=True)
        env_patch.start()
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(
                root=ROOT,
                db_path=Path(self.temp.name) / "api.sqlite3",
                sms_sender=lambda phone: sent.append(phone),
                sms_checker=lambda phone, code: code == TEST_OTP,
            ),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"

        def request(method: str, path: str, body: dict | None = None, token: str | None = None):
            headers = {"Accept": "application/json"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            if token:
                headers["X-Owner-Token"] = token
            req = Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
            try:
                with urlopen(req, timeout=3) as response:
                    return response.status, json.loads(response.read())
            except HTTPError as error:
                return error.code, json.loads(error.read())

        try:
            status, listed = request("GET", "/api/auth/otp/targets")
            self.assertEqual(status, 200)
            serialized = json.dumps(listed, ensure_ascii=False)
            self.assertNotIn(configured_env()["OWNER_PHONE_NUMBER_PRIMARY"], serialized)
            self.assertEqual(len(listed["targets"]), 2)
            status, _ = request("POST", "/api/auth/otp/request", {"target_id": "primary"})
            self.assertEqual(status, 200)
            self.assertEqual(sent, [configured_env()["OWNER_PHONE_NUMBER_PRIMARY"]])
            status, logged_in = request("POST", "/api/auth/otp/verify", {"target_id": "primary", "code": TEST_OTP})
            self.assertEqual(status, 200)
            token = logged_in["token"]
            status, _ = request("GET", "/api/dashboard", token=token)
            self.assertEqual(status, 200)
            status, _ = request("POST", "/api/auth/logout", {}, token=token)
            self.assertEqual(status, 200)
            status, _ = request("GET", "/api/dashboard", token=token)
            self.assertEqual(status, 401)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            env_patch.stop()


if __name__ == "__main__":
    unittest.main()
