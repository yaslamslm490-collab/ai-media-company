"""Register the Manus callback once a public HTTPS bridge URL is deployed."""
from __future__ import annotations

import sys

from bridge.server import BridgeProblem, load_environment, manus_request, webhook_url


def main() -> int:
    load_environment()
    try:
        callback = webhook_url()
        existing = manus_request("GET", "/v2/webhook.list")
        hooks = existing.get("data") if isinstance(existing.get("data"), list) else []
        for hook in hooks:
            if isinstance(hook, dict) and hook.get("url") == callback:
                print(f"Webhook already registered (id={hook.get('id', 'unknown')}).")
                return 0
        result = manus_request("POST", "/v2/webhook.create", {"url": callback})
        hook = result.get("webhook") if isinstance(result.get("webhook"), dict) else {}
        print(f"Webhook registered (id={hook.get('id', 'unknown')}).")
        print("Manus sent its verification request; confirm /health reports database_ready=true and the callback returns 2xx.")
        return 0
    except BridgeProblem as problem:
        print(f"Registration failed: {problem.code}: {problem.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
