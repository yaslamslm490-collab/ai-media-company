"""Create or validate AI_MEDIA_VAULT_KEY in the ignored local .env file."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
KEY_NAME = "AI_MEDIA_VAULT_KEY"


def ensure_vault_key(path: Path = ENV_PATH) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    current = ""
    for line in lines:
        if line.strip().startswith(f"{KEY_NAME}="):
            current = line.split("=", 1)[1].strip().strip('"\'')
            break
    if current:
        try:
            Fernet(current.encode("ascii"))
            os.chmod(path, 0o600)
            return False
        except (ValueError, UnicodeEncodeError, TypeError):
            pass

    generated = Fernet.generate_key().decode("ascii")
    replaced = False
    updated = []
    for line in lines:
        if line.strip().startswith(f"{KEY_NAME}="):
            if not replaced:
                updated.append(f"{KEY_NAME}={generated}")
                replaced = True
        else:
            updated.append(line)
    if not replaced:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(f"{KEY_NAME}={generated}")
    content = "\n".join(updated) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".env.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


if __name__ == "__main__":
    created = ensure_vault_key()
    print("تم إنشاء مفتاح خزنة الحسابات محلياً." if created else "مفتاح خزنة الحسابات موجود وصالح؛ لم يُعرض.")
