#!/usr/bin/env python3
"""Build the unified React frontend while preserving the Python API server."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REACT_ROOT = ROOT / "frontend-react"
DIST = ROOT / "dist"


def main() -> None:
    package_json = REACT_ROOT / "package.json"
    if not package_json.is_file():
        raise SystemExit("frontend-react/package.json is missing")
    node_modules = REACT_ROOT / "node_modules"
    if not (node_modules / ".bin" / "vite").exists():
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=REACT_ROOT, check=True)
    subprocess.run(["npm", "run", "build"], cwd=REACT_ROOT, check=True)
    routes_source = ROOT / "manus-routes.json"
    if routes_source.is_file():
        shutil.copy2(routes_source, DIST / "manus-routes.json")
    routes = json.loads(routes_source.read_text(encoding="utf-8"))
    if not isinstance(routes, (dict, list)):
        raise SystemExit("manus-routes.json must be a JSON object or array")
    if not (DIST / "index.html").is_file() or not any((DIST / "assets").glob("*.js")):
        raise SystemExit("React build output is incomplete")
    print(f"Built unified React frontend in {DIST}")


if __name__ == "__main__":
    main()
