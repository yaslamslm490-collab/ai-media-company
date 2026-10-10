from __future__ import annotations

import base64
import hashlib
import html.parser
import json
import os
import re
import secrets
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]
from backend.server import make_handler  # noqa: E402
from backend.oauth import OAuthProvider  # noqa: E402


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class OAuthHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.owner_token = secrets.token_urlsafe(32)
        self.env_patch = patch.dict(os.environ, {
            "NADA_MCP_TOKEN": "",
            "MANUS_API_KEY": "",
            "MANUS_API_TOKEN": "",
            "PUBLIC_BASE_URL": "https://nada.example.test",
            "MANUS_WEBHOOK_PUBLIC_KEY": "",
        })
        self.env_patch.start()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            root=ROOT, db_path=Path(self.temp.name) / "oauth.sqlite3", owner_token=self.owner_token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.env_patch.stop()
        self.temp.cleanup()

    def request(self, path: str, *, method: str = "GET", body: bytes | None = None,
                content_type: str | None = None, headers: dict[str, str] | None = None,
                no_redirect: bool = False):
        request_headers = dict(headers or {})
        if content_type:
            request_headers["Content-Type"] = content_type
        request = Request(self.base + path, data=body, method=method, headers=request_headers)
        try:
            opener = build_opener(_NoRedirect()) if no_redirect else None
            response_context = opener.open(request, timeout=5) if opener else urlopen(request, timeout=5)
            with response_context as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def json_request(self, path: str, payload: dict, method: str = "POST"):
        return self.request(path, method=method, body=json.dumps(payload).encode(), content_type="application/json")

    def form_request(self, path: str, payload: dict[str, str], *, no_redirect: bool = False):
        request = Request(self.base + path, data=urlencode(payload).encode(), method="POST",
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
        opener = build_opener(_NoRedirect()) if no_redirect else build_opener()
        try:
            with opener.open(request, timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def register(self, scope: str = "tasks:read tasks:write offline_access") -> tuple[str, str, str]:
        redirect_uri = "https://chatgpt.com/connector_platform_oauth_redirect"
        status, body, _ = self.json_request("/oauth/register", {
            "client_name": "ChatGPT test client", "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"], "token_endpoint_auth_method": "none",
        })
        self.assertEqual(status, 201, body.decode())
        client_id = json.loads(body)["client_id"]
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        query = urlencode({"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri,
                           "code_challenge": challenge, "code_challenge_method": "S256",
                           "resource": "https://nada.example.test/mcp", "scope": scope, "state": "state-test-1"})
        status, page, _ = self.request("/oauth/authorize?" + query)
        self.assertEqual(status, 200, page.decode(errors="replace"))
        session_id = re.search(rb'name="session_id" value="([^"]+)"', page).group(1).decode()
        csrf = re.search(rb'name="csrf" value="([^"]+)"', page).group(1).decode()
        status, _, headers = self.form_request("/oauth/authorize", {
            "session_id": session_id, "csrf": csrf, "owner_token": self.owner_token, "decision": "approve",
        }, no_redirect=True)
        self.assertEqual(status, 302)
        location = headers["Location"]
        from urllib.parse import parse_qs, urlsplit
        code = parse_qs(urlsplit(location).query)["code"][0]
        self.assertEqual(parse_qs(urlsplit(location).query)["state"], ["state-test-1"])
        self.assertEqual(parse_qs(urlsplit(location).query)["iss"], ["https://nada.example.test"])
        return client_id, verifier, code

    def exchange(self, client_id: str, verifier: str, code: str):
        return self.form_request("/oauth/token", {
            "grant_type": "authorization_code", "client_id": client_id,
            "code": code, "redirect_uri": "https://chatgpt.com/connector_platform_oauth_redirect",
            "code_verifier": verifier, "resource": "https://nada.example.test/mcp",
        })

    def mcp(self, payload: dict, token: str):
        return self.json_request("/mcp", payload) if token == "" else self.request(
            "/mcp", method="POST", body=json.dumps(payload).encode(), content_type="application/json",
            headers={"Authorization": "Bearer " + token})

    def test_oauth_metadata_follows_mcp_discovery_contract(self):
        status, body, _ = self.request("/.well-known/oauth-protected-resource")
        self.assertEqual(status, 200)
        resource = json.loads(body)
        self.assertEqual(resource["resource"], "https://nada.example.test/mcp")
        self.assertEqual(resource["authorization_servers"], ["https://nada.example.test"])
        status, body, _ = self.request("/.well-known/oauth-authorization-server")
        self.assertEqual(status, 200)
        metadata = json.loads(body)
        self.assertEqual(metadata["issuer"], "https://nada.example.test")
        self.assertIn("S256", metadata["code_challenge_methods_supported"])
        self.assertEqual(metadata["token_endpoint_auth_methods_supported"], ["none"])
        self.assertEqual(metadata["registration_endpoint"], "https://nada.example.test/oauth/register")
        self.assertIn("offline_access", metadata["scopes_supported"])
        self.assertEqual(resource["scopes_supported"], ["tasks:read"])

    def test_render_external_url_is_the_default_origin_but_custom_origin_wins(self):
        with patch.dict(os.environ, {"PUBLIC_BASE_URL": "", "RENDER_EXTERNAL_URL": "https://nada-ai.onrender.com"}):
            self.assertEqual(OAuthProvider._base_url(), "https://nada-ai.onrender.com")
        with patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://nada.example.test", "RENDER_EXTERNAL_URL": "https://nada-ai.onrender.com"}):
            self.assertEqual(OAuthProvider._base_url(), "https://nada.example.test")

    def test_authorization_pkce_code_exchange_refresh_and_mcp_write_are_real_http_flows(self):
        client_id, verifier, code = self.register()
        status, body, _ = self.exchange(client_id, verifier, code)
        self.assertEqual(status, 200, body.decode())
        token_payload = json.loads(body)
        access = token_payload["access_token"]
        self.assertEqual(token_payload["token_type"], "Bearer")
        status, body, _ = self.mcp({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, access)
        self.assertEqual(status, 200, body.decode())
        status, body, _ = self.mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "create_work_task", "arguments": {"title": "مهمة OAuth داخل NADA AI"}}}, access)
        self.assertEqual(status, 200, body.decode())
        created = json.loads(body)["result"]["structuredContent"]["task"]
        self.assertEqual(created["title"], "مهمة OAuth داخل NADA AI")
        status, body, _ = self.request("/api/health")
        self.assertEqual(status, 200)
        collaboration = json.loads(body)["checks"]["collaboration"]
        self.assertEqual(collaboration["mcp_client_activity"], "ONLINE")
        self.assertEqual(collaboration["chatgpt_connection"], "NOT_CHECKED")
        status, body, _ = self.form_request("/oauth/token", {
            "grant_type": "refresh_token", "client_id": client_id,
            "refresh_token": token_payload["refresh_token"], "resource": "https://nada.example.test/mcp",
        })
        self.assertEqual(status, 200, body.decode())
        refreshed = json.loads(body)
        self.assertNotEqual(refreshed["access_token"], access)
        # The original authorization code and rotated refresh token cannot be reused.
        status, body, _ = self.exchange(client_id, verifier, code)
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid_grant")
        status, body, _ = self.form_request("/oauth/revoke", {
            "client_id": client_id, "token": refreshed["access_token"], "token_type_hint": "access_token",
        })
        self.assertEqual(status, 200, body.decode())
        status, _, _ = self.mcp({"jsonrpc": "2.0", "id": 4, "method": "initialize"}, refreshed["access_token"])
        self.assertEqual(status, 401)

    def test_scope_restrictions_and_unauthenticated_resource_challenge(self):
        client_id, verifier, code = self.register(scope="tasks:read")
        status, body, _ = self.exchange(client_id, verifier, code)
        self.assertEqual(status, 200, body.decode())
        access = json.loads(body)["access_token"]
        status, body, _ = self.mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, access)
        self.assertEqual(status, 200)
        tool_names = {item["name"] for item in json.loads(body)["result"]["tools"]}
        self.assertIn("list_work_tasks", tool_names)
        self.assertIn("create_work_task", tool_names)
        status, body, headers = self.mcp({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "create_work_task", "arguments": {"title": "محاولة كتابة ممنوعة"}}}, access)
        self.assertEqual(status, 403)
        self.assertIn("insufficient_scope", headers.get("WWW-Authenticate", ""))
        self.assertIn('scope="tasks:write"', headers.get("WWW-Authenticate", ""))
        status, _, headers = self.mcp({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}, "")
        self.assertEqual(status, 401)
        self.assertIn("oauth-protected-resource", headers.get("WWW-Authenticate", ""))
        self.assertIn('scope="tasks:read"', headers.get("WWW-Authenticate", ""))

    def test_oauth_authorization_error_redirect_includes_issuer_and_state(self):
        status, body, _ = self.json_request("/oauth/register", {
            "client_name": "ChatGPT error test", "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
        })
        self.assertEqual(status, 201)
        client_id = json.loads(body)["client_id"]
        query = urlencode({
            "response_type": "code", "client_id": client_id,
            "redirect_uri": "https://chatgpt.com/connector_platform_oauth_redirect",
            "resource": "https://nada.example.test/mcp", "scope": "tasks:read", "state": "error-state-1",
        })
        status, _, headers = self.request("/oauth/authorize?" + query, no_redirect=True)
        self.assertEqual(status, 302)
        redirect = urlsplit(headers["Location"])
        response = parse_qs(redirect.query)
        self.assertEqual(redirect.netloc, "chatgpt.com")
        self.assertEqual(response["error"], ["invalid_request"])
        self.assertEqual(response["state"], ["error-state-1"])
        self.assertEqual(response["iss"], ["https://nada.example.test"])

    def test_manus_scope_is_required_for_external_actions_and_health_never_claims_chatgpt_connected(self):
        client_id, verifier, code = self.register(scope="tasks:read tasks:write")
        status, body, _ = self.exchange(client_id, verifier, code)
        self.assertEqual(status, 200)
        access = json.loads(body)["access_token"]
        status, body, headers = self.mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "send_task_to_manus", "arguments": {"task_id": "not-a-task"}}}, access)
        self.assertEqual(status, 403)
        self.assertIn("insufficient_scope", headers.get("WWW-Authenticate", ""))
        self.assertIn('scope="manus:execute"', headers.get("WWW-Authenticate", ""))
        status, body, _ = self.request("/api/health")
        self.assertEqual(status, 200)
        checks = json.loads(body)["checks"]["collaboration"]
        self.assertEqual(checks["mcp_oauth"], "READY")
        self.assertEqual(checks["chatgpt_connection"], "NOT_CHECKED")
        self.assertEqual(checks["mcp_client_activity"], "NOT_CHECKED")

    def test_dcr_rejects_http_remote_redirects_and_token_exchange_checks_pkce(self):
        status, body, _ = self.json_request("/oauth/register", {"client_name": "bad", "redirect_uris": ["http://example.com/callback"]})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid_redirect_uri")
        client_id, verifier, code = self.register()
        status, body, _ = self.form_request("/oauth/token", {
            "grant_type": "authorization_code", "client_id": client_id,
            "code": code, "redirect_uri": "https://chatgpt.com/connector_platform_oauth_redirect",
            "code_verifier": "z" * 48, "resource": "https://nada.example.test/mcp",
        })
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid_grant")


if __name__ == "__main__":
    unittest.main()
