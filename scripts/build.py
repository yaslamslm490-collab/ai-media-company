#!/usr/bin/env python3
"""Build a deployable static frontend directory without bundling secrets."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ASSETS = (
    "index.html",
    "styles.css",
    "manus-routes.json",
    "app.js",
    "frontend/app.js",
    "frontend/api.js",
    "frontend/account-browser.js",
    "frontend/status.js",
    "frontend/company-builder.js",
)


def main() -> None:
    for rel in ASSETS:
        source = ROOT / rel
        if not source.is_file() or source.stat().st_size == 0:
            raise SystemExit(f"missing or empty build asset: {rel}")
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    for expected in ("./styles.css", "./frontend/app.js"):
        if expected not in index:
            raise SystemExit(f"index.html does not reference required asset: {expected}")
    routes = json.loads((ROOT / "manus-routes.json").read_text(encoding="utf-8"))
    if not isinstance(routes, (dict, list)):
        raise SystemExit("manus-routes.json must be a JSON object or array")

    if DIST.exists():
        shutil.rmtree(DIST)
    for rel in ASSETS:
        destination = DIST / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, destination)

    built_app = (DIST / "frontend" / "app.js").read_text(encoding="utf-8")
    for expected in ("./company-builder.js", "./account-browser.js"):
        if expected not in built_app:
            raise SystemExit(f"built entry point is missing the {expected} import")
    for rel in ASSETS:
        if not (DIST / rel).is_file():
            raise SystemExit(f"build output missing asset: {rel}")
    print(f"Built {len(ASSETS)} deployable assets in {DIST}")


if __name__ == "__main__":
    main()
