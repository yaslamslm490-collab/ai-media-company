"""Minimal, database-backed OAuth 2.1 authorization server for the embedded NADA AI MCP endpoint.

Implements authorization-code + PKCE (S256), public-client registration, resource indicators,
RFC 8414 authorization-server metadata, RFC 9728 protected-resource metadata, and rotating
refresh tokens. Raw authorization codes and bearer tokens are never stored.
"""
from __future__ import annotations

import hashlib
import html
import hmac
import json
import re
import secrets
import threading
import time
import urllib.parse
from typing import Any

from backend.store import Store

SCOPES = {"tasks:read", "tasks:write", "manus:execute", "offline_access"}
_ALL_SCOPES = "tasks:read tasks:write manus:execute offline_access"
_ACCESS_LIFETIME = 3600
_REFRESH_LIFETIME = 30 * 24 * 60 * 60
_AUTH_CODE_LIFETIME = 300
_AUTH_SESSION_LIFETIME = 600


class OAuthError(ValueError):
    def __init__(self, error: str, description: str = "", status: int = 400):
        self.error = error
        self.description = description
        self.status = status
        super().__init__(error)


class OAuthProvider:
    """OAuth state is persisted beside NADA AI tasks in its existing database."""

    def __init__(self, store: Store, owner_token_getter):
        self.store = store
        self._owner_token_getter = owner_token_getter
        self._attempts: dict[str, list[float]] = {}
        self._attempts_lock = threading.Lock()
        self.initialize()

    def initialize(self) -> None:
        with self.store.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS oauth_clients (
                client_id TEXT PRIMARY KEY,
                client_name TEXT NOT NULL,
                redirect_uris TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oauth_authorization_sessions (
                session_id TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                code_challenge TEXT NOT NULL,
                resource TEXT NOT NULL,
                scope TEXT NOT NULL,
                state TEXT NOT NULL,
                csrf_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
                code_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                code_challenge TEXT NOT NULL,
                resource TEXT NOT NULL,
                scope TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS oauth_access_tokens (
                token_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                scope TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked_at INTEGER NOT NULL DEFAULT 0,
                last_used_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                scope TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER NOT NULL DEFAULT 0,
                revoked_at INTEGER NOT NULL DEFAULT 0
            );
            """)

    @staticmethod
    def _base_url() -> str:
        import os
        value = (os.environ.get("PUBLIC_BASE_URL", "").strip() or os.environ.get("RENDER_EXTERNAL_URL", "").strip()).rstrip("/")
        parsed = urllib.parse.urlsplit(value)
        local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme != "https" and not local_http) or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if parsed.path or parsed.query or parsed.fragment:
            return ""
        return value

    @property
    def issuer(self) -> str:
        return self._base_url()

    @property
    def resource(self) -> str:
        base = self._base_url()
        return base + "/mcp" if base else ""

    @property
    def ready(self) -> bool:
        owner_token = str(self._owner_token_getter() or "")
        return bool(self.issuer and len(owner_token) >= 32)

    def protected_resource_metadata(self) -> dict[str, Any]:
        if not self.issuer:
            raise OAuthError("server_configuration_error", "PUBLIC_BASE_URL must be a canonical HTTPS origin.", 503)
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "scopes_supported": ["tasks:read"],
            "bearer_methods_supported": ["header"],
            "resource_documentation": self.issuer + "/docs/collaboration",
        }

    def authorization_server_metadata(self) -> dict[str, Any]:
        if not self.issuer:
            raise OAuthError("server_configuration_error", "PUBLIC_BASE_URL must be a canonical HTTPS origin.", 503)
        return {
            "issuer": self.issuer,
            "authorization_response_iss_parameter_supported": True,
            "authorization_endpoint": self.issuer + "/oauth/authorize",
            "token_endpoint": self.issuer + "/oauth/token",
            "revocation_endpoint": self.issuer + "/oauth/revoke",
            "registration_endpoint": self.issuer + "/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": sorted(SCOPES),
            "client_id_metadata_document_supported": False,
        }

    def register_client(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.ready:
            raise OAuthError("server_error", "Owner authentication or HTTPS origin is not configured.", 503)
        redirects = payload.get("redirect_uris")
        if not isinstance(redirects, list) or not redirects or len(redirects) > 10:
            raise OAuthError("invalid_client_metadata", "redirect_uris must contain 1–10 valid HTTPS URLs.")
        clean_redirects: list[str] = []
        for uri in redirects:
            if not isinstance(uri, str) or len(uri) > 2048 or not self._valid_redirect_uri(uri):
                raise OAuthError("invalid_redirect_uri", "Only exact HTTPS redirect URIs are accepted.")
            if uri not in clean_redirects:
                clean_redirects.append(uri)
        grant_types = payload.get("grant_types", ["authorization_code", "refresh_token"])
        response_types = payload.get("response_types", ["code"])
        auth_method = payload.get("token_endpoint_auth_method", "none")
        if (not isinstance(grant_types, list) or any(not isinstance(item, str) for item in grant_types)
                or "authorization_code" not in grant_types
                or not set(grant_types).issubset({"authorization_code", "refresh_token"})):
            raise OAuthError("invalid_client_metadata", "Only authorization_code and refresh_token grants are supported.")
        if (not isinstance(response_types, list) or any(not isinstance(item, str) for item in response_types)
                or "code" not in response_types or not set(response_types).issubset({"code"}) or auth_method != "none"):
            raise OAuthError("invalid_client_metadata", "This server accepts public clients using authorization code and PKCE.")
        name = payload.get("client_name", "MCP client")
        if not isinstance(name, str):
            name = "MCP client"
        name = name.strip()[:100] or "MCP client"
        client_id = secrets.token_urlsafe(24)
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO oauth_clients(client_id,client_name,redirect_uris,created_at) VALUES(?,?,?,?)",
                (client_id, name, json.dumps(clean_redirects, separators=(",", ":")), int(time.time())),
            )
        return {
            "client_id": client_id,
            "client_name": name,
            "redirect_uris": clean_redirects,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }

    @staticmethod
    def _valid_redirect_uri(uri: str) -> bool:
        try:
            parsed = urllib.parse.urlsplit(uri)
            local = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            return bool((parsed.scheme == "https" or local) and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment)
        except ValueError:
            return False

    def _client(self, client_id: str) -> dict[str, Any] | None:
        with self.store.connect() as db:
            row = db.execute("SELECT client_id,client_name,redirect_uris FROM oauth_clients WHERE client_id=?", (client_id,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _parse_scopes(value: str) -> set[str]:
        scopes = set(value.split()) if value else {"tasks:read"}
        if not scopes or not scopes.issubset(SCOPES):
            raise OAuthError("invalid_scope", "One or more requested scopes are unsupported.")
        return scopes

    def authorization_form(self, query: dict[str, str]) -> str:
        if not self.ready:
            raise OAuthError("server_configuration_error", "Owner authentication or the HTTPS origin is not configured.", 503)
        client_id = query.get("client_id", "")
        client = self._client(client_id)
        redirect_uri = query.get("redirect_uri", "")
        if not client:
            raise OAuthError("invalid_client", "The OAuth client is not registered.")
        allowed = json.loads(client["redirect_uris"])
        if redirect_uri not in allowed:
            raise OAuthError("invalid_request", "The redirect URI does not exactly match a registered URI.")
        if query.get("response_type") != "code":
            raise OAuthError("unsupported_response_type", "Only authorization-code flow is supported.")
        if query.get("code_challenge_method") != "S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", query.get("code_challenge", "")):
            raise OAuthError("invalid_request", "A valid PKCE S256 code challenge is required.")
        if query.get("resource") != self.resource:
            raise OAuthError("invalid_target", "The resource parameter must exactly match this MCP server.")
        state = query.get("state", "")
        if len(state) > 1024:
            raise OAuthError("invalid_request", "state is too long.")
        requested = self._parse_scopes(query.get("scope", ""))
        session_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.store.connect() as db:
            db.execute("DELETE FROM oauth_authorization_sessions WHERE expires_at < ?", (now,))
            db.execute(
                "INSERT INTO oauth_authorization_sessions(session_id,client_id,redirect_uri,code_challenge,resource,scope,state,csrf_hash,expires_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (session_id, client_id, redirect_uri, query["code_challenge"], self.resource,
                 " ".join(sorted(requested)), state, self._hash(csrf), now + _AUTH_SESSION_LIFETIME),
            )
        labels = {
            "tasks:read": "قراءة المهام ونتائج التعاون",
            "tasks:write": "إنشاء المهام وتعديل حالتها وحفظ الملاحظات",
            "manus:execute": "إرسال مهام إلى Manus ومزامنة النتائج (قد تستهلك حصة Manus)",
            "offline_access": "تجديد الاتصال تلقائيًا دون إعادة التفويض باستمرار",
        }
        scope_html = "".join(f"<li>{html.escape(labels[item])}</li>" for item in sorted(requested))
        action = html.escape(client["client_name"])
        return f"""<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>السماح لـ NADA AI</title><style>body{{font:16px system-ui;background:#f4f6fa;color:#142137;margin:0;display:grid;min-height:100vh;place-items:center}}main{{box-sizing:border-box;background:white;padding:32px;border-radius:16px;max-width:560px;width:calc(100% - 32px);box-shadow:0 12px 40px #14213718}}h1{{font-size:24px}}li{{margin:10px 0}}input{{box-sizing:border-box;width:100%;padding:12px;margin:8px 0 16px;border:1px solid #bdc8d8;border-radius:8px}}button{{padding:11px 18px;border:0;border-radius:8px;background:#1768d2;color:white;font-weight:700;margin-left:8px;cursor:pointer}}button.deny{{background:#e9edf3;color:#243348}}.note{{color:#526176;font-size:14px}}</style><main><h1>ربط {html.escape('NADA AI / AI Media OS')}</h1><p>يطلب <strong>{action}</strong> الوصول إلى مساحة العمل المشتركة.</p><ul>{scope_html}</ul><p class="note">لن تُمنح الصلاحية إلا بعد إدخال رمز المالك والموافقة. يمكنك إلغاء العملية.</p><form method="post" action="/oauth/authorize"><input type="hidden" name="session_id" value="{html.escape(session_id)}"><input type="hidden" name="csrf" value="{html.escape(csrf)}"><label for="owner">رمز دخول المالك</label><input id="owner" name="owner_token" type="password" autocomplete="current-password" required><button name="decision" value="approve" type="submit">موافقة وربط</button><button class="deny" name="decision" value="deny" type="submit" formnovalidate>رفض</button></form></main></html>"""

    def authorization_request_error_redirect(self, query: dict[str, str], error: OAuthError) -> str:
        """Redirect protocol errors only when the client and exact redirect URI are trusted."""
        client_id = query.get("client_id", "")
        redirect_uri = query.get("redirect_uri", "")
        client = self._client(client_id) if client_id else None
        if not client or redirect_uri not in json.loads(client["redirect_uris"]):
            return ""
        params = {
            "error": error.error,
            "error_description": error.description[:500],
            "iss": self.issuer,
        }
        state = query.get("state", "")
        if len(state) <= 1024 and state:
            params["state"] = state
        parts = urllib.parse.urlsplit(redirect_uri)
        existing = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                       urllib.parse.urlencode(existing + list(params.items())), parts.fragment))

    def complete_authorization(self, form: dict[str, str], remote_ip: str) -> str:
        session_id = form.get("session_id", "")
        csrf = form.get("csrf", "")
        if not session_id or len(session_id) > 100 or not csrf:
            raise OAuthError("invalid_request", "The authorization session is invalid.")
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM oauth_authorization_sessions WHERE session_id=?", (session_id,)).fetchone()
            if not row or int(row["expires_at"]) < int(time.time()) or not hmac.compare_digest(str(row["csrf_hash"]), self._hash(csrf)):
                raise OAuthError("invalid_request", "The authorization session expired or its CSRF token is invalid.")
            data = dict(row)
            decision = form.get("decision", "")
            if decision not in {"approve", "deny"}:
                raise OAuthError("invalid_request", "Invalid consent decision.")
            if decision == "approve" and not self._verify_owner(form.get("owner_token", ""), remote_ip):
                raise OAuthError("access_denied", "رمز المالك غير صحيح أو تجاوزت محاولات الدخول الحد المؤقت.", 401)
            db.execute("DELETE FROM oauth_authorization_sessions WHERE session_id=?", (session_id,))
            if decision == "approve":
                raw_code = secrets.token_urlsafe(32)
                db.execute(
                    "INSERT INTO oauth_authorization_codes(code_hash,client_id,redirect_uri,code_challenge,resource,scope,expires_at,used_at) VALUES(?,?,?,?,?,?,?,0)",
                    (self._hash(raw_code), data["client_id"], data["redirect_uri"], data["code_challenge"], data["resource"], data["scope"], int(time.time()) + _AUTH_CODE_LIFETIME),
                )
            else:
                raw_code = ""
        params = {"iss": self.issuer}
        if decision == "approve":
            params["code"] = raw_code
        else:
            params["error"] = "access_denied"
            params["error_description"] = "The resource owner denied the request."
        if data["state"]:
            params["state"] = data["state"]
        parts = urllib.parse.urlsplit(data["redirect_uri"])
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True) + list(params.items())
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ""))

    def _verify_owner(self, supplied: str, remote_ip: str) -> bool:
        now = time.time()
        with self._attempts_lock:
            attempts = [stamp for stamp in self._attempts.get(remote_ip, []) if now - stamp < 600]
            if len(attempts) >= 5:
                self._attempts[remote_ip] = attempts
                return False
            attempts.append(now)
            self._attempts[remote_ip] = attempts
        expected = str(self._owner_token_getter() or "")
        valid = bool(expected and supplied and hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")))
        if valid:
            with self._attempts_lock:
                self._attempts.pop(remote_ip, None)
        return valid

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _form_encode(body: dict[str, Any]) -> dict[str, Any]:
        return body

    def token(self, form: dict[str, str]) -> dict[str, Any]:
        if not self.ready:
            raise OAuthError("server_error", "Owner authentication or HTTPS origin is not configured.", 503)
        client_id = form.get("client_id", "")
        if not client_id or not self._client(client_id):
            raise OAuthError("invalid_client", "The OAuth client is invalid.")
        grant_type = form.get("grant_type", "")
        if grant_type == "authorization_code":
            return self._exchange_code(form, client_id)
        if grant_type == "refresh_token":
            return self._exchange_refresh(form, client_id)
        raise OAuthError("unsupported_grant_type", "Only authorization_code and refresh_token grants are supported.")

    def _exchange_code(self, form: dict[str, str], client_id: str) -> dict[str, Any]:
        raw_code = form.get("code", "")
        redirect_uri = form.get("redirect_uri", "")
        verifier = form.get("code_verifier", "")
        resource = form.get("resource", "")
        if not raw_code or not 43 <= len(verifier) <= 128 or not re.fullmatch(r"[A-Za-z0-9._~-]+", verifier):
            raise OAuthError("invalid_grant", "The authorization code or PKCE verifier is invalid.")
        challenge = __import__("base64").urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        now = int(time.time())
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM oauth_authorization_codes WHERE code_hash=?", (self._hash(raw_code),)).fetchone()
            if (not row or row["client_id"] != client_id or row["redirect_uri"] != redirect_uri
                    or row["resource"] != resource or resource != self.resource
                    or int(row["expires_at"]) < now or int(row["used_at"]) != 0
                    or not hmac.compare_digest(str(row["code_challenge"]), challenge)):
                raise OAuthError("invalid_grant", "The authorization code is invalid, expired, or already used.")
            updated = db.execute("UPDATE oauth_authorization_codes SET used_at=? WHERE code_hash=? AND used_at=0", (now, self._hash(raw_code)))
            if updated.rowcount != 1:
                raise OAuthError("invalid_grant", "The authorization code has already been used.")
            return self._new_tokens(db, client_id, resource, str(row["scope"]), now)

    def _exchange_refresh(self, form: dict[str, str], client_id: str) -> dict[str, Any]:
        raw_refresh = form.get("refresh_token", "")
        resource = form.get("resource", "")
        now = int(time.time())
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM oauth_refresh_tokens WHERE token_hash=?", (self._hash(raw_refresh),)).fetchone()
            if (not row or row["client_id"] != client_id or row["resource"] != resource
                    or resource != self.resource or int(row["expires_at"]) < now
                    or int(row["used_at"]) != 0 or int(row["revoked_at"]) != 0):
                raise OAuthError("invalid_grant", "The refresh token is invalid or expired.")
            updated = db.execute("UPDATE oauth_refresh_tokens SET used_at=? WHERE token_hash=? AND used_at=0", (now, self._hash(raw_refresh)))
            if updated.rowcount != 1:
                raise OAuthError("invalid_grant", "The refresh token has already been used.")
            return self._new_tokens(db, client_id, resource, str(row["scope"]), now)

    @staticmethod
    def _new_tokens(db, client_id: str, resource: str, scope: str, now: int) -> dict[str, Any]:
        access = secrets.token_urlsafe(32)
        db.execute("INSERT INTO oauth_access_tokens(token_hash,client_id,resource,scope,expires_at,revoked_at) VALUES(?,?,?,?,?,0)",
                   (hashlib.sha256(access.encode()).hexdigest(), client_id, resource, scope, now + _ACCESS_LIFETIME))
        result = {"access_token": access, "token_type": "Bearer", "expires_in": _ACCESS_LIFETIME, "scope": scope}
        if "offline_access" in scope.split():
            refresh = secrets.token_urlsafe(48)
            db.execute("INSERT INTO oauth_refresh_tokens(token_hash,client_id,resource,scope,expires_at,used_at) VALUES(?,?,?,?,?,0)",
                       (hashlib.sha256(refresh.encode()).hexdigest(), client_id, resource, scope, now + _REFRESH_LIFETIME))
            result["refresh_token"] = refresh
        return result

    def validate_access_token(self, raw_token: str) -> set[str] | None:
        if not raw_token or len(raw_token) > 256:
            return None
        with self.store.connect() as db:
            row = db.execute("SELECT resource,scope,expires_at,revoked_at FROM oauth_access_tokens WHERE token_hash=?",
                             (self._hash(raw_token),)).fetchone()
        if not row or row["resource"] != self.resource or int(row["expires_at"]) < int(time.time()) or int(row["revoked_at"]) != 0:
            return None
        try:
            scopes = set(str(row["scope"]).split())
        except Exception:
            return None
        return scopes if scopes.issubset(SCOPES) and scopes else None

    def mark_access_token_used(self, raw_token: str) -> None:
        if not raw_token or len(raw_token) > 256:
            return
        with self.store.connect() as db:
            db.execute("UPDATE oauth_access_tokens SET last_used_at=? WHERE token_hash=? AND revoked_at=0 AND expires_at>=?",
                       (int(time.time()), self._hash(raw_token), int(time.time())))

    def mcp_client_used(self) -> bool:
        """Report real OAuth-authenticated MCP use without inferring the caller's identity."""
        now = int(time.time())
        with self.store.connect() as db:
            row = db.execute(
                "SELECT 1 AS used FROM oauth_access_tokens t "
                "WHERE t.resource=? AND t.expires_at>=? "
                "AND t.revoked_at=0 AND t.last_used_at>=? LIMIT 1",
                (self.resource, now, now - 7 * 24 * 60 * 60),
            ).fetchone()
        return row is not None

    def revoke(self, client_id: str, raw_token: str) -> None:
        if not client_id or not self._client(client_id):
            raise OAuthError("invalid_client", "The OAuth client is invalid.")
        if not raw_token or len(raw_token) > 256:
            return
        digest = self._hash(raw_token)
        now = int(time.time())
        with self.store.connect() as db:
            db.execute("UPDATE oauth_access_tokens SET revoked_at=? WHERE token_hash=? AND client_id=? AND revoked_at=0",
                       (now, digest, client_id))
            db.execute("UPDATE oauth_refresh_tokens SET revoked_at=? WHERE token_hash=? AND client_id=? AND revoked_at=0",
                       (now, digest, client_id))

    def authorization_error_redirect(self, form: dict[str, str], error: OAuthError, remote_ip: str) -> str:
        """Send a safe OAuth denial back only after validating the stored request and CSRF token."""
        session_id = form.get("session_id", "")
        csrf = form.get("csrf", "")
        if not session_id or not csrf:
            raise error
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM oauth_authorization_sessions WHERE session_id=?", (session_id,)).fetchone()
            if not row or int(row["expires_at"]) < int(time.time()) or not hmac.compare_digest(str(row["csrf_hash"]), self._hash(csrf)):
                raise error
            data = dict(row)
            db.execute("DELETE FROM oauth_authorization_sessions WHERE session_id=?", (session_id,))
        params = {"error": "access_denied", "error_description": error.error, "iss": self.issuer}
        if data["state"]:
            params["state"] = data["state"]
        parts = urllib.parse.urlsplit(data["redirect_uri"])
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True) + list(params.items())
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ""))


def required_scopes(tool_name: str) -> set[str]:
    if tool_name in {"list_work_tasks", "get_work_updates"}:
        return {"tasks:read"}
    if tool_name in {"create_work_task", "update_work_task", "add_work_update"}:
        return {"tasks:write"}
    if tool_name in {"send_task_to_manus", "create_and_send_task_to_manus", "sync_manus_result", "reply_to_manus", "register_manus_webhook"}:
        return {"tasks:write", "manus:execute"} if tool_name == "create_and_send_task_to_manus" else {"manus:execute"}
    return set()
