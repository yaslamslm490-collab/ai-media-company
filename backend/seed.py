"""Idempotently seed the minimal AI Media OS starter workspace."""
from __future__ import annotations

import json
import os
from pathlib import Path

from backend.server import ROOT, load_local_env
from backend.company_builder import CompanyBuilderStore
from backend.store import Store


def main() -> None:
    load_local_env()
    db_path = Path(os.environ.get("AI_MEDIA_DB_PATH", ROOT / "data" / "dashboard.sqlite3"))
    store = Store(db_path)
    store.initialize()
    CompanyBuilderStore(store).initialize()
    result = store.seed_initial_data()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
