"""Owner-only SMS OTP authentication backed by Twilio Verify and hashed local sessions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

OTP_TTL_SECONDS = 300
RESEND_COOLDOWN_SECONDS = 60
SEND_WINDOW_SECONDS = 15 * 60
SEND_WINDOW_MAX = 3
SEND_DAY_SECONDS = 24 * 60 * 60
SEND_DAY_MAX = 10
VERIFY_ATTEMPT_MAX = 5
LOCKOUT_SECONDS = 15 * 60
SESSION_TTL_SECONDS = 12 * 60 * 60
_PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
_SID_RE = re.compile(r"^AC[0-9a-fA-F]{32}$")
_API_KEY_RE = re.compile(r"^SK[0-9a-fA-F]{32}$")
_VERIFY_SERVICE_RE = re.compile(r"^VA[0-9a-fA-F]{32}$")


class OwnerAuthError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(code)


def _trusted_phones(env: dict[str, str]) -> list[dict[str, str]]:
    primary = env.get("OWNER_PHONE_NUMBER_PRIMARY", "").strip()
    raw_backups = env.get("OWNER_PHONE_NUMBERS_BACKUP", "").strip()
    try:
        backups = json.loads(raw_backups) if raw_backups else []
    except json.JSONDecodeError:
        return []
    if not isinstance(backups, list) or any(not isinstance(item, str) for item in backups):
        return []
    if len(backups) > 5 or not _PHONE_RE.fullmatch(primary):
        return []
    numbers = [primary, *[item.strip() for item in backups]]
    if any(not _PHONE_RE.fullmatch(number) for number in numbers) or len(set(numbers)) != len(numbers):
        return []
    targets = [{"id": "primary", "number": primary, "label": "الرقم الأساسي"}]
    targets.extend(
        {"id": f"backup-{index}", "number": number, "label": f"رقم احتياطي {index}"}
        for index, number in enumerate(numbers[1:], 1)
    )
    return targets


def sms_auth_configured(env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    recovery = env.get("OWNER_RECOVERY_CODE", "")
    hmac_key = env.get("OWNER_RECOVERY_HMAC_KEY", "")
    return bool(
        _trusted_phones(env)
        and len(hmac_key.encode("utf-8")) >= 32
        and re.fullmatch(r"[A-Za-z0-9_-]{32,256}", recovery)
        and _SID_RE.fullmatch(env.get("TWILIO_ACCOUNT_SID", "").strip())
        and _API_KEY_RE.fullmatch(env.get("TWILIO_API_KEY", "").strip())
        and len(env.get("TWILIO_API_SECRET", "")) >= 16
        and _VERIFY_SERVICE_RE.fullmatch(env.get("TWILIO_VERIFY_SERVICE_SID", "").strip())
    )


def _recovery_fingerprint(code: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), f"ai-media-owner-recovery:v1:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _session_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _twilio_request(path: str, fields: dict[str, str], env: dict[str, str]) -> dict[str, Any]:
    account_sid = env["TWILIO_ACCOUNT_SID"].strip()
    api_key = env["TWILIO_API_KEY"].strip()
    api_secret = env["TWILIO_API_SECRET"]
    service_sid = env["TWILIO_VERIFY_SERVICE_SID"].strip()
    url = f"https://verify.twilio.com/v2/Services/{service_sid}/{path}"
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(fields).encode("ascii"),
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read(16_384).decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("sms_verification_provider_failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("sms_verification_provider_invalid_response")
    return payload


def send_twilio_verification(to: str, env: dict[str, str] | None = None) -> None:
    """Ask Twilio Verify to generate and deliver an SMS OTP; the application never sees it."""
    env = env if env is not None else os.environ
    result = _twilio_request("Verifications", {"To": to, "Channel": "sms"}, env)
    if result.get("status") != "pending":
        raise RuntimeError("sms_verification_request_rejected")


def check_twilio_verification(to: str, code: str, env: dict[str, str] | None = None) -> bool:
    """Check the submitted OTP directly with Twilio Verify without persisting the code."""
    env = env if env is not None else os.environ
    result = _twilio_request("VerificationCheck", {"To": to, "Code": code}, env)
    return result.get("status") == "approved" or result.get("valid") is True


class OwnerSmsAuth:
    def __init__(
        self,
        store,
        *,
        env: dict[str, str] | None = None,
        sender: Callable[[str], None] | None = None,
        checker: Callable[[str, str], bool] | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.store = store
        self.env = env if env is not None else os.environ
        self.sender = sender or (lambda phone: send_twilio_verification(phone, self.env))
        self.checker = checker or (lambda phone, code: check_twilio_verification(phone, code, self.env))
        self.clock = clock or time.time

    @property
    def configured(self) -> bool:
        return sms_auth_configured(self.env)

    def _require_configured(self) -> None:
        if not self.configured:
            raise OwnerAuthError(503, "otp_not_configured", "دخول SMS والاسترداد غير مهيأين على الخادم.")

    def targets(self) -> list[dict[str, str]]:
        self._require_configured()
        return [
            {"id": item["id"], "label": item["label"], "masked_number": "••••••••" + item["number"][-2:]}
            for item in _trusted_phones(self.env)
        ]

    @staticmethod
    def _locked(db) -> dict[str, Any]:
        sql = "SELECT * FROM owner_auth_state WHERE id='owner'"
        if getattr(db, "is_mysql", False):
            sql += " FOR UPDATE"
        row = db.execute(sql).fetchone()
        if row is None:
            raise RuntimeError("owner_auth_state_missing")
        return dict(row)

    @staticmethod
    def _begin(db) -> None:
        db.execute("BEGIN IMMEDIATE")

    def request_code(self, target_value: Any) -> dict[str, Any]:
        self._require_configured()
        target_id = target_value if isinstance(target_value, str) else ""
        target = next((item for item in _trusted_phones(self.env) if item["id"] == target_id), None)
        if target is None:
            return {"accepted": True, "expires_in": OTP_TTL_SECONDS, "resend_after": RESEND_COOLDOWN_SECONDS}

        now = int(self.clock())
        error: OwnerAuthError | None = None
        may_send = False
        expires_at = now + OTP_TTL_SECONDS
        with self.store.connect() as db:
            self._begin(db)
            state = self._locked(db)
            if int(state["locked_until"]) > now:
                error = OwnerAuthError(429, "otp_rate_limited", "محاولات كثيرة؛ حاول لاحقاً.")
            elif int(state["resend_after"]) > now:
                error = OwnerAuthError(429, "otp_resend_wait", "انتظر قليلاً قبل طلب رمز جديد.")
            else:
                window_start = int(state["send_window_started"])
                send_count = int(state["send_count"])
                if now - window_start >= SEND_WINDOW_SECONDS:
                    window_start, send_count = now, 0
                day_start = int(state["send_day_started"])
                daily_count = int(state["send_day_count"])
                if now - day_start >= SEND_DAY_SECONDS:
                    day_start, daily_count = now, 0
                if send_count >= SEND_WINDOW_MAX or daily_count >= SEND_DAY_MAX:
                    error = OwnerAuthError(429, "otp_rate_limited", "تم بلوغ حد إرسال الرموز؛ حاول لاحقاً.")
                else:
                    # Twilio Verify can reuse the same active code; do not extend its local 5-minute lifetime on resend.
                    if state["target_id"] == target_id and int(state["expires_at"]) > now:
                        expires_at = int(state["expires_at"])
                    db.execute(
                        "UPDATE owner_auth_state SET target_id=?,expires_at=?,resend_after=?,send_window_started=?,send_count=?,"
                        "send_day_started=?,send_day_count=?,attempt_count=0 WHERE id='owner'",
                        (target_id, expires_at, now + RESEND_COOLDOWN_SECONDS, window_start,
                         send_count + 1, day_start, daily_count + 1),
                    )
                    may_send = True
        if error:
            raise error
        if may_send:
            try:
                self.sender(target["number"])
            except Exception as exc:
                with self.store.connect() as db:
                    db.execute(
                        "UPDATE owner_auth_state SET target_id='',expires_at=0 WHERE id='owner' AND target_id=? AND expires_at=?",
                        (target_id, expires_at),
                    )
                raise OwnerAuthError(503, "otp_delivery_failed", "تعذّر إرسال رمز التحقق؛ حاول لاحقاً.") from exc
        return {
            "accepted": True,
            "expires_in": max(0, expires_at - now),
            "resend_after": RESEND_COOLDOWN_SECONDS,
        }

    def _new_session(self, db, now: int) -> str:
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM owner_sessions WHERE expires_at<=?", (now,))
        db.execute(
            "INSERT INTO owner_sessions(token_hash,created_at,expires_at) VALUES(?,?,?)",
            (_session_digest(token), now, now + SESSION_TTL_SECONDS),
        )
        return token

    def verify_code(self, target_value: Any, code_value: Any) -> dict[str, Any]:
        self._require_configured()
        target_id = target_value if isinstance(target_value, str) else ""
        targets = _trusted_phones(self.env)
        target = next((item for item in targets if item["id"] == target_id), None)
        code = code_value if isinstance(code_value, str) else ""
        if target is None or not re.fullmatch(r"[0-9]{6}", code):
            raise OwnerAuthError(400, "invalid_otp_input", "اختر رقماً موثوقاً وأدخل رمزاً من 6 أرقام.")

        now = int(self.clock())
        error: OwnerAuthError | None = None
        session_token = ""
        with self.store.connect() as db:
            self._begin(db)
            state = self._locked(db)
            if int(state["locked_until"]) > now:
                error = OwnerAuthError(429, "otp_rate_limited", "محاولات كثيرة؛ حاول لاحقاً.")
            elif state["target_id"] != target_id or not int(state["expires_at"]):
                error = OwnerAuthError(401, "otp_invalid", "رمز التحقق غير صالح أو انتهت صلاحيته.")
            elif int(state["expires_at"]) <= now:
                db.execute("UPDATE owner_auth_state SET target_id='',expires_at=0,attempt_count=0 WHERE id='owner'")
                error = OwnerAuthError(401, "otp_expired", "انتهت صلاحية الرمز؛ اطلب رمزاً جديداً.")
            else:
                try:
                    valid = bool(self.checker(target["number"], code))
                except Exception as exc:
                    error = OwnerAuthError(503, "otp_verification_failed", "تعذّر التحقق من الرمز حالياً؛ حاول لاحقاً.")
                else:
                    attempts = int(state["attempt_count"]) + 1
                    if valid:
                        session_token = self._new_session(db, now)
                        db.execute("UPDATE owner_auth_state SET target_id='',expires_at=0,attempt_count=0 WHERE id='owner'")
                    elif attempts >= VERIFY_ATTEMPT_MAX:
                        db.execute(
                            "UPDATE owner_auth_state SET target_id='',expires_at=0,attempt_count=0,locked_until=? WHERE id='owner'",
                            (now + LOCKOUT_SECONDS,),
                        )
                        error = OwnerAuthError(429, "otp_rate_limited", "تم تجاوز عدد المحاولات؛ حاول بعد 15 دقيقة.")
                    else:
                        db.execute("UPDATE owner_auth_state SET attempt_count=? WHERE id='owner'", (attempts,))
                        error = OwnerAuthError(401, "otp_invalid", "رمز التحقق غير صالح أو انتهت صلاحيته.")
        if error:
            raise error
        return {"token": session_token, "expires_in": SESSION_TTL_SECONDS}

    def verify_recovery_code(self, code_value: Any) -> dict[str, Any]:
        self._require_configured()
        supplied = code_value if isinstance(code_value, str) else ""
        configured = self.env["OWNER_RECOVERY_CODE"]
        key = self.env["OWNER_RECOVERY_HMAC_KEY"]
        code_hash = hashlib.sha256(f"ai-media-owner-recovery-id:v1:{configured}".encode("utf-8")).hexdigest()
        fingerprint = _recovery_fingerprint(configured, key)
        valid = 24 <= len(supplied) <= 256 and hmac.compare_digest(supplied.encode("utf-8"), configured.encode("utf-8"))
        now = int(self.clock())
        error: OwnerAuthError | None = None
        session_token = ""
        with self.store.connect() as db:
            self._begin(db)
            state = self._locked(db)
            recovery_used_at = int(state["recovery_used_at"])
            recovery_attempt_count = int(state["recovery_attempt_count"])
            code_changed = not hmac.compare_digest(str(state["recovery_code_hash"]), code_hash)
            if code_changed:
                db.execute(
                    "UPDATE owner_auth_state SET recovery_code_hash=?,recovery_fingerprint=?,recovery_used_at=0,recovery_attempt_count=0 WHERE id='owner'",
                    (code_hash, fingerprint),
                )
                recovery_used_at, recovery_attempt_count = 0, 0
            elif state["recovery_fingerprint"] != fingerprint:
                db.execute("UPDATE owner_auth_state SET recovery_fingerprint=? WHERE id='owner'", (fingerprint,))
            if int(state["locked_until"]) > now:
                error = OwnerAuthError(429, "recovery_rate_limited", "محاولات كثيرة؛ حاول لاحقاً.")
            elif recovery_used_at:
                error = OwnerAuthError(409, "recovery_code_used", "استُخدم رمز الاسترداد؛ حدّثه في إعدادات الأسرار لاستعادة إمكانية استخدامه.")
            elif valid:
                session_token = self._new_session(db, now)
                db.execute(
                    "UPDATE owner_auth_state SET recovery_used_at=?,recovery_attempt_count=0,target_id='',expires_at=0,attempt_count=0 WHERE id='owner'",
                    (now,),
                )
            else:
                attempts = recovery_attempt_count + 1
                if attempts >= VERIFY_ATTEMPT_MAX:
                    db.execute(
                        "UPDATE owner_auth_state SET recovery_attempt_count=0,locked_until=? WHERE id='owner'",
                        (now + LOCKOUT_SECONDS,),
                    )
                    error = OwnerAuthError(429, "recovery_rate_limited", "تم تجاوز عدد المحاولات؛ حاول بعد 15 دقيقة.")
                else:
                    db.execute("UPDATE owner_auth_state SET recovery_attempt_count=? WHERE id='owner'", (attempts,))
                    error = OwnerAuthError(401, "recovery_invalid", "رمز الاسترداد غير صالح.")
        if error:
            raise error
        return {"token": session_token, "expires_in": SESSION_TTL_SECONDS}

    def authenticate(self, token: str) -> bool:
        if not self.configured or not token:
            return False
        digest = _session_digest(token)
        now = int(self.clock())
        with self.store.connect() as db:
            row = db.execute("SELECT expires_at FROM owner_sessions WHERE token_hash=?", (digest,)).fetchone()
            if row is None or int(row["expires_at"]) <= now:
                if row is not None:
                    db.execute("DELETE FROM owner_sessions WHERE token_hash=?", (digest,))
                return False
        return True

    def revoke(self, token: str) -> None:
        if token:
            with self.store.connect() as db:
                db.execute("DELETE FROM owner_sessions WHERE token_hash=?", (_session_digest(token),))
