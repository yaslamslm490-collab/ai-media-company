"""Owner-managed external media accounts with encrypted credentials and fair rotation."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken

from backend.database import ensure_migration_table, migration_applied, record_migration, table_columns
from backend.store import Store, new_id, utc_now

SERVICES = {"VIDEO", "AUDIO", "BOTH"}
ACCOUNT_STATUSES = {"ACTIVE", "PAUSED"}
CANONICAL_PROVIDERS = {"kling": "Kling", "elevenlabs": "ElevenLabs"}
PROVIDER_SERVICE = {"kling": "VIDEO", "elevenlabs": "AUDIO"}
PROVIDER_PREFIXES = {"kling": "KL", "elevenlabs": "EL"}
ACCOUNT_REGIONS = {"UN", "US", "EU", "TR", "RU", "EG"}
DEFAULT_ACCOUNT_PAGE_SIZE = 5
MAX_ACCOUNTS = 20


class IntegrationProblem(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class IntegrationStore:
    """SQLite account metadata plus Fernet-encrypted provider credentials."""

    def __init__(self, store: Store):
        self.store = store

    def initialize(self) -> None:
        with self.store.connect() as db:
            ensure_migration_table(db)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS external_accounts (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    provider_key TEXT NOT NULL,
                    services_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','PAUSED')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_used_video TEXT NOT NULL DEFAULT '',
                    last_used_audio TEXT NOT NULL DEFAULT '',
                    rotation_count_video INTEGER NOT NULL DEFAULT 0,
                    rotation_count_audio INTEGER NOT NULL DEFAULT 0,
                    connection_status TEXT NOT NULL DEFAULT 'NOT_CHECKED',
                    connection_message TEXT NOT NULL DEFAULT 'لم يُفحص الاتصال بعد.',
                    last_checked_at TEXT NOT NULL DEFAULT '',
                    pause_reason TEXT NOT NULL DEFAULT '',
                    pause_until TEXT NOT NULL DEFAULT '',
                    account_code TEXT NOT NULL DEFAULT '',
                    region_code TEXT NOT NULL DEFAULT 'UN'
                );
                CREATE INDEX IF NOT EXISTS external_accounts_provider_service_idx
                    ON external_accounts(provider_key, status);
                CREATE TABLE IF NOT EXISTS external_account_secrets (
                    account_id TEXT PRIMARY KEY REFERENCES external_accounts(id) ON DELETE CASCADE,
                    secret_ciphertext TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS external_rotation_cursors (
                    service TEXT NOT NULL CHECK(service IN ('VIDEO','AUDIO')),
                    provider_key TEXT NOT NULL,
                    last_account_id TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(service, provider_key)
                );
                CREATE TABLE IF NOT EXISTS media_generation_jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('AUDIO','VIDEO','PIPELINE')),
                    provider_key TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PROCESSING','COMPLETED','FAILED')),
                    prompt TEXT NOT NULL DEFAULT '',
                    params_json TEXT NOT NULL DEFAULT '{}',
                    account_id TEXT NOT NULL DEFAULT '',
                    audio_account_id TEXT NOT NULL DEFAULT '',
                    video_account_id TEXT NOT NULL DEFAULT '',
                    provider_task_id TEXT NOT NULL DEFAULT '',
                    external_task_id TEXT NOT NULL DEFAULT '',
                    audio_file TEXT NOT NULL DEFAULT '',
                    video_url TEXT NOT NULL DEFAULT '',
                    output_file TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    failover_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS media_generation_jobs_recent_idx
                    ON media_generation_jobs(created_at DESC);
            """)
            columns = table_columns(db, "external_accounts")
            migrations = {
                "connection_status": "TEXT NOT NULL DEFAULT 'NOT_CHECKED'",
                "connection_message": "TEXT NOT NULL DEFAULT 'لم يُفحص الاتصال بعد.'",
                "last_checked_at": "TEXT NOT NULL DEFAULT ''",
                "pause_reason": "TEXT NOT NULL DEFAULT ''",
                "pause_until": "TEXT NOT NULL DEFAULT ''",
                "account_code": "TEXT NOT NULL DEFAULT ''",
                "region_code": "TEXT NOT NULL DEFAULT 'UN'",
            }
            for name, definition in migrations.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE external_accounts ADD COLUMN {name} {definition}")
            record_migration(db, "003-media-integrations-v1", utc_now())

            if not migration_applied(db, "004-account-code-v1"):
                db.execute("CREATE TABLE IF NOT EXISTS account_code_sequences (prefix TEXT PRIMARY KEY, last_number INTEGER NOT NULL DEFAULT 0)")
                sequence_rows = db.execute("SELECT prefix,last_number FROM account_code_sequences").fetchall()
                last_numbers = {str(row["prefix"]): int(row["last_number"]) for row in sequence_rows}
                account_rows = db.execute("SELECT id,provider_key,account_code FROM external_accounts ORDER BY created_at,id").fetchall()
                for row in account_rows:
                    code = str(row["account_code"] or "")
                    match = re.fullmatch(r"#([A-Z0-9]{2,8})-(\d+)", code)
                    if match:
                        prefix, number = match.group(1), int(match.group(2))
                        last_numbers[prefix] = max(last_numbers.get(prefix, 0), number)
                        continue
                    prefix = self._account_prefix(str(row["provider_key"] or ""))
                    number = last_numbers.get(prefix, 0) + 1
                    code = f"#{prefix}-{number:03d}"
                    db.execute("UPDATE external_accounts SET account_code=? WHERE id=?", (code, row["id"]))
                    last_numbers[prefix] = number
                for prefix, number in last_numbers.items():
                    db.execute("INSERT OR IGNORE INTO account_code_sequences(prefix,last_number) VALUES (?,?)", (prefix, number))
                    db.execute("UPDATE account_code_sequences SET last_number=? WHERE prefix=? AND last_number<?", (number, prefix, number))
                db.execute("CREATE UNIQUE INDEX IF NOT EXISTS external_accounts_account_code_uq ON external_accounts(account_code)")
                record_migration(db, "004-account-code-v1", utc_now())

    @staticmethod
    def _account_prefix(provider: str, requested: Any = None) -> str:
        raw = requested.strip() if isinstance(requested, str) and requested.strip() else PROVIDER_PREFIXES.get(provider.casefold(), provider)
        prefix = re.sub(r"[^A-Z0-9]", "", raw.upper())[:8]
        if not 2 <= len(prefix) <= 8:
            raise IntegrationProblem(400, "invalid_account_prefix", "بادئة الحساب يجب أن تتكون من حرفين إلى ثمانية أحرف أو أرقام.")
        return prefix

    @staticmethod
    def _vault() -> Fernet:
        key = os.environ.get("AI_MEDIA_VAULT_KEY", "").strip()
        if not key:
            raise IntegrationProblem(503, "vault_not_configured", "مخزن أسرار الحسابات غير مهيأ على الخادم.")
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError, TypeError) as error:
            raise IntegrationProblem(503, "vault_key_invalid", "مفتاح تشفير مخزن الحسابات غير صالح.") from error

    @staticmethod
    def _text(payload: dict[str, Any], key: str, *, required: bool, maximum: int) -> str:
        value = payload.get(key, "")
        if not isinstance(value, str):
            raise IntegrationProblem(400, "invalid_field", "أحد الحقول النصية غير صالح.")
        value = value.strip()
        if required and not value:
            raise IntegrationProblem(400, "required_field", "أكمل الحقول المطلوبة.")
        if len(value) > maximum or "\x00" in value:
            raise IntegrationProblem(400, "invalid_field", "أحد الحقول أطول من المسموح أو غير صالح.")
        return value

    @staticmethod
    def _services(value: Any) -> list[str]:
        if not isinstance(value, str):
            raise IntegrationProblem(400, "invalid_service", "اختر خدمة فيديو أو صوت أو كلتيهما.")
        service = value.strip().upper()
        if service not in SERVICES:
            raise IntegrationProblem(400, "invalid_service", "اختر خدمة فيديو أو صوت أو كلتيهما.")
        return ["VIDEO", "AUDIO"] if service == "BOTH" else [service]

    @staticmethod
    def _status(value: Any, *, default: str = "ACTIVE") -> str:
        if value is None or value == "":
            value = default
        if not isinstance(value, str) or value.strip().upper() not in ACCOUNT_STATUSES:
            raise IntegrationProblem(400, "invalid_status", "حالة الحساب يجب أن تكون نشطة أو متوقفة.")
        return value.strip().upper()

    @staticmethod
    def _decode_services(value: str) -> list[str]:
        try:
            parsed = json.loads(value)
            return [service for service in parsed if service in {"VIDEO", "AUDIO"}]
        except (TypeError, json.JSONDecodeError):
            return []

    @classmethod
    def _public_account(cls, row: sqlite3.Row) -> dict[str, Any]:
        services = cls._decode_services(row["services_json"])
        return {
            "id": row["id"],
            "account_code": row["account_code"],
            "region_code": row["region_code"],
            "label": row["label"],
            "provider": row["provider"],
            "services": services,
            "status": row["status"],
            "connection_status": row["connection_status"],
            "connection_message": row["connection_message"],
            "last_checked_at": row["last_checked_at"] or None,
            "pause_reason": row["pause_reason"] or None,
            "pause_until": row["pause_until"] or None,
            "secret_configured": bool(row["secret_configured"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "rotation_count": {"VIDEO": row["rotation_count_video"], "AUDIO": row["rotation_count_audio"]},
            "last_used_at": {"VIDEO": row["last_used_video"] or None, "AUDIO": row["last_used_audio"] or None},
        }

    def snapshot(self, *, limit: int = DEFAULT_ACCOUNT_PAGE_SIZE, offset: int = 0, search: str = "", problems: bool = False) -> dict[str, Any]:
        limit = min(max(int(limit), 1), 100)
        offset = min(max(int(offset), 0), 1_000_000)
        search = search.strip()[:120]
        clauses: list[str] = []
        parameters: list[Any] = []
        if search:
            if search.startswith("#"):
                clauses.append("UPPER(a.account_code)=?")
                parameters.append(search.upper())
            else:
                escaped = search.replace("!", "!!").replace("%", "!%").replace("_", "!_")
                like = f"%{escaped}%"
                clauses.append("(a.account_code LIKE ? ESCAPE '!' OR a.label LIKE ? ESCAPE '!' OR a.provider LIKE ? ESCAPE '!' OR a.id=?)")
                parameters.extend((like, like, like, search))
        if problems:
            clauses.append("(a.status='PAUSED' OR a.connection_status NOT IN ('ONLINE','NOT_CHECKED','NOT_CONFIGURED') OR a.pause_reason<>'')")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.store.connect() as db:
            total_accounts = int(db.execute("SELECT COUNT(*) AS total FROM external_accounts").fetchone()["total"])
            total_active = int(db.execute("SELECT COUNT(*) AS total FROM external_accounts WHERE status='ACTIVE'").fetchone()["total"])
            active_by_service = {
                service: int(db.execute("SELECT COUNT(*) AS total FROM external_accounts WHERE status='ACTIVE' AND services_json LIKE ?", (f'%\"{service}\"%',)).fetchone()["total"])
                for service in ("VIDEO", "AUDIO")
            }
            providers = [str(row["provider"]) for row in db.execute("SELECT DISTINCT provider FROM external_accounts ORDER BY provider").fetchall()]
            provider_rows = db.execute("""SELECT provider, COUNT(*) AS total,
                SUM(CASE WHEN status='ACTIVE' AND services_json LIKE ? THEN 1 ELSE 0 END) AS active_video,
                SUM(CASE WHEN status='ACTIVE' AND services_json LIKE ? THEN 1 ELSE 0 END) AS active_audio,
                SUM(CASE WHEN connection_status='ONLINE' THEN 1 ELSE 0 END) AS online_count
                FROM external_accounts GROUP BY provider ORDER BY provider""",
                ('%\"VIDEO\"%', '%\"AUDIO\"%')).fetchall()
            provider_summary = [{
                "provider": str(row["provider"]), "total": int(row["total"]),
                "active_video": int(row["active_video"] or 0), "active_audio": int(row["active_audio"] or 0),
                "online_count": int(row["online_count"] or 0),
            } for row in provider_rows]
            rows = db.execute(f"""
                SELECT a.*, CASE WHEN s.secret_ciphertext IS NULL OR s.secret_ciphertext='' THEN 0 ELSE 1 END AS secret_configured
                FROM external_accounts AS a
                LEFT JOIN external_account_secrets AS s ON s.account_id = a.id
                {where}
                ORDER BY a.created_at, a.id
                LIMIT ? OFFSET ?
            """, (*parameters, limit, offset)).fetchall()
            matched_total = int(db.execute(f"SELECT COUNT(*) AS total FROM external_accounts AS a{where}", parameters).fetchone()["total"])
            adapters = {}
            for service, provider in (("VIDEO", "kling"), ("AUDIO", "elevenlabs")):
                result = db.execute("""SELECT COUNT(*) AS total FROM external_accounts AS a
                    INNER JOIN external_account_secrets AS s ON s.account_id=a.id
                    WHERE a.status='ACTIVE' AND a.provider_key=? AND a.services_json LIKE ? AND s.secret_ciphertext<>''""", (provider, f'%\"{service}\"%')).fetchone()
                adapters[service] = "READY" if int(result["total"]) else "NOT_CONFIGURED"
        accounts = [self._public_account(row) for row in rows]
        return {
            "accounts": accounts,
            "pagination": {"limit": limit, "offset": offset, "total": matched_total, "has_more": offset + len(accounts) < matched_total},
            "summary": {
                "total_accounts": total_accounts,
                "active_accounts": total_active,
                "max_accounts": MAX_ACCOUNTS,
                "active_by_service": active_by_service,
                "providers": providers,
            },
            "provider_summary": provider_summary,
            "generation_adapters": adapters,
            "generations": self.list_generations(limit=12),
        }

    def create_account(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        allowed = {"label", "provider", "service", "status", "credential", "prefix", "region_code"}
        if set(payload) - allowed:
            raise IntegrationProblem(400, "invalid_fields", "تحتوي البيانات على حقول غير مدعومة.")
        label = self._text(payload, "label", required=True, maximum=120)
        provider = self._text(payload, "provider", required=True, maximum=120)
        provider = CANONICAL_PROVIDERS.get(provider.casefold(), provider)
        prefix = self._account_prefix(provider.casefold(), payload.get("prefix"))
        region_code = str(payload.get("region_code") or "UN").strip().upper()
        if region_code not in ACCOUNT_REGIONS:
            raise IntegrationProblem(400, "invalid_region", "منطقة الحساب يجب أن تكون UN أو US أو EU أو TR أو RU أو EG.")
        services = self._services(payload.get("service"))
        expected_service = PROVIDER_SERVICE.get(provider.casefold())
        if expected_service and services != [expected_service]:
            raise IntegrationProblem(400, "provider_service_mismatch", "Kling مخصص للفيديو وElevenLabs مخصص للصوت.")
        status = self._status(payload.get("status"))
        credential = self._text(payload, "credential", required=True, maximum=8192)
        if len(credential) < 8 or any(ch in credential for ch in "\r\n\x00"):
            raise IntegrationProblem(400, "invalid_credential", "قيمة مفتاح API غير صالحة.")
        encrypted = self._vault().encrypt(credential.encode("utf-8")).decode("ascii")
        now = utc_now()
        account_id = new_id()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = int(db.execute("SELECT COUNT(*) AS total FROM external_accounts").fetchone()["total"])
            if count >= MAX_ACCOUNTS:
                raise IntegrationProblem(409, "account_pool_full", f"سعة مخزن الحسابات القصوى هي {MAX_ACCOUNTS} حساباً.")
            db.execute("INSERT OR IGNORE INTO account_code_sequences(prefix,last_number) VALUES (?,0)", (prefix,))
            db.execute("UPDATE account_code_sequences SET last_number=last_number+1 WHERE prefix=?", (prefix,))
            sequence = int(db.execute("SELECT last_number FROM account_code_sequences WHERE prefix=?", (prefix,)).fetchone()["last_number"])
            account_code = f"#{prefix}-{sequence:03d}"
            db.execute("""INSERT INTO external_accounts
                (id,label,provider,provider_key,services_json,status,account_code,region_code,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (account_id, label, provider, provider.casefold(), json.dumps(services), status, account_code, region_code, now, now))
            db.execute("INSERT INTO external_account_secrets(account_id,secret_ciphertext,updated_at) VALUES (?,?,?)",
                       (account_id, encrypted, now))
            self.store.log_activity(db, actor=actor, action="integration.account_created", module="external-integrations",
                                    object_type="external_account", object_id=account_id,
                                    result=json.dumps({"provider": provider, "services": services, "status": status}, ensure_ascii=False))
            row = db.execute("""SELECT a.*, 1 AS secret_configured FROM external_accounts AS a WHERE id=?""",
                             (account_id,)).fetchone()
        return self._public_account(row)

    def update_account(self, account_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any] | None:
        allowed = {"label", "provider", "service", "status", "credential"}
        if set(payload) - allowed or not payload:
            raise IntegrationProblem(400, "invalid_fields", "تحتوي البيانات على حقول غير مدعومة.")
        encrypted = None
        if "credential" in payload:
            credential = self._text(payload, "credential", required=True, maximum=8192)
            if len(credential) < 8 or any(ch in credential for ch in "\r\n\x00"):
                raise IntegrationProblem(400, "invalid_credential", "قيمة مفتاح API غير صالحة.")
            encrypted = self._vault().encrypt(credential.encode("utf-8")).decode("ascii")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM external_accounts WHERE id=?", (account_id,)).fetchone()
            if current is None:
                return None
            label = self._text(payload, "label", required=True, maximum=120) if "label" in payload else current["label"]
            provider = self._text(payload, "provider", required=True, maximum=120) if "provider" in payload else current["provider"]
            provider = CANONICAL_PROVIDERS.get(provider.casefold(), provider)
            services = self._services(payload.get("service")) if "service" in payload else self._decode_services(current["services_json"])
            expected_service = PROVIDER_SERVICE.get(provider.casefold())
            if expected_service and services != [expected_service]:
                raise IntegrationProblem(400, "provider_service_mismatch", "Kling مخصص للفيديو وElevenLabs مخصص للصوت.")
            status = self._status(payload.get("status")) if "status" in payload else current["status"]
            now = utc_now()
            reset_pause = status == "ACTIVE" and current["status"] == "PAUSED"
            db.execute("""UPDATE external_accounts SET label=?,provider=?,provider_key=?,services_json=?,status=?,updated_at=?,
                pause_reason=CASE WHEN ? THEN '' ELSE pause_reason END,
                pause_until=CASE WHEN ? THEN '' ELSE pause_until END,
                connection_status=CASE WHEN ? THEN 'NOT_CHECKED' ELSE connection_status END,
                connection_message=CASE WHEN ? THEN 'أُعيد تفعيل الحساب؛ أجرِ فحص اتصال جديداً.' ELSE connection_message END
                WHERE id=?""",
                       (label, provider, provider.casefold(), json.dumps(services), status, now,
                        reset_pause, reset_pause, reset_pause, reset_pause, account_id))
            if encrypted is not None:
                db.execute("""INSERT INTO external_account_secrets(account_id,secret_ciphertext,updated_at)
                    VALUES (?,?,?) ON CONFLICT(account_id) DO UPDATE SET secret_ciphertext=excluded.secret_ciphertext,updated_at=excluded.updated_at""",
                           (account_id, encrypted, now))
            changed = sorted(set(payload) - {"credential"})
            self.store.log_activity(db, actor=actor, action="integration.account_updated", module="external-integrations",
                                    object_type="external_account", object_id=account_id,
                                    result=json.dumps({"fields": changed, "credential_rotated": encrypted is not None}, ensure_ascii=False))
            row = db.execute("""SELECT a.*, CASE WHEN s.secret_ciphertext IS NULL OR s.secret_ciphertext='' THEN 0 ELSE 1 END AS secret_configured
                FROM external_accounts AS a LEFT JOIN external_account_secrets AS s ON s.account_id=a.id WHERE a.id=?""",
                             (account_id,)).fetchone()
        return self._public_account(row)

    def delete_account(self, account_id: str, actor: str) -> bool:
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id,provider,services_json FROM external_accounts WHERE id=?", (account_id,)).fetchone()
            if row is None:
                return False
            self.store.log_activity(db, actor=actor, action="integration.account_deleted", module="external-integrations",
                                    object_type="external_account", object_id=account_id,
                                    result=json.dumps({"provider": row["provider"]}, ensure_ascii=False))
            db.execute("DELETE FROM external_accounts WHERE id=?", (account_id,))
        return True

    def test_connection(self, account_id: str, actor: str) -> dict[str, Any] | None:
        with self.store.connect() as db:
            row = db.execute("""SELECT a.*, s.secret_ciphertext FROM external_accounts AS a
                LEFT JOIN external_account_secrets AS s ON s.account_id=a.id WHERE a.id=?""", (account_id,)).fetchone()
        if row is None:
            return None

        provider_key = row["provider_key"]
        credential = ""
        if row["secret_ciphertext"]:
            try:
                credential = self._vault().decrypt(row["secret_ciphertext"].encode("ascii")).decode("utf-8")
            except InvalidToken as error:
                raise IntegrationProblem(503, "vault_key_mismatch", "تعذر فك تشفير بيانات الاعتماد؛ تحقق من مفتاح الخزنة.") from error

        if not credential:
            status, message = "NOT_CONFIGURED", "لا يوجد مفتاح API محفوظ لهذا الحساب."
        elif provider_key == "kling":
            external_id = "aimediaos-health-" + uuid.uuid4().hex
            url = "https://api-singapore.klingai.com/tasks?external_task_ids=" + quote(external_id, safe="")
            request = Request(url, headers={"Authorization": f"Bearer {credential}", "Accept": "application/json"}, method="GET")
            status, message = self._probe_json(request, "kling")
        elif provider_key == "elevenlabs":
            request = Request("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": credential, "Accept": "application/json"}, method="GET")
            status, message = self._probe_json(request, "elevenlabs")
        else:
            status, message = "NOT_CONFIGURED", "لا يوجد فاحص رسمي مهيأ لهذا المزود."

        checked_at = utc_now()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE external_accounts SET connection_status=?,connection_message=?,last_checked_at=?,updated_at=? WHERE id=?",
                       (status, message, checked_at, checked_at, account_id))
            self.store.log_activity(db, actor=actor, action="integration.connection_tested", module="external-integrations",
                                    object_type="external_account", object_id=account_id,
                                    result=json.dumps({"provider": row["provider"], "status": status}, ensure_ascii=False))
            updated = db.execute("""SELECT a.*, CASE WHEN s.secret_ciphertext IS NULL OR s.secret_ciphertext='' THEN 0 ELSE 1 END AS secret_configured
                FROM external_accounts AS a LEFT JOIN external_account_secrets AS s ON s.account_id=a.id WHERE a.id=?""",
                                 (account_id,)).fetchone()
        return {"connection": {"status": status, "message": message}, "account": self._public_account(updated)}

    @staticmethod
    def _probe_json(request: Request, provider: str) -> tuple[str, str]:
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    return "UPSTREAM_ERROR", "أعاد المزود استجابة أكبر من الحد المسموح للفحص."
                payload = json.loads(raw.decode("utf-8"))
            if provider == "kling" and payload.get("code") in (0, "0") and isinstance(payload.get("data"), list):
                return "ONLINE", "اتصال Kling صالح؛ فُحصت نقطة قراءة فقط ولم تُنشأ مهمة فيديو."
            if provider == "elevenlabs" and isinstance(payload.get("user_id"), str) and payload["user_id"]:
                return "ONLINE", "اتصال ElevenLabs صالح؛ فُحصت معلومات الحساب دون توليد صوت."
            return "UPSTREAM_ERROR", "وصل رد من المزود لكن صيغة الاستجابة لم تطابق المتوقع."
        except HTTPError as error:
            if error.code in (401, 403):
                return "AUTH_ERROR", "رفض المزود الاعتماد أو صلاحية نقطة القراءة."
            if error.code == 429:
                return "RATE_LIMITED", "قيّد المزود طلب الفحص؛ انتظر وفق سياسة المزود."
            return "UPSTREAM_ERROR", f"أعاد المزود حالة HTTP {error.code}؛ لم يُحفظ نص الرد."
        except (URLError, TimeoutError, OSError):
            return "NETWORK_ERROR", "تعذّر الوصول إلى نقطة فحص المزود من الخادم."
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return "UPSTREAM_ERROR", "تعذّر تفسير استجابة فحص المزود."

    def rotate_next(self, service: str, provider: str, actor: str) -> dict[str, Any]:
        service = service.strip().upper() if isinstance(service, str) else ""
        if service not in {"VIDEO", "AUDIO"}:
            raise IntegrationProblem(400, "invalid_service", "اختر خدمة فيديو أو صوت.")
        if not isinstance(provider, str) or not provider.strip() or len(provider.strip()) > 120:
            raise IntegrationProblem(400, "invalid_provider", "حدد مزود الخدمة.")
        provider_key = provider.strip().casefold()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = utc_now()
            resumed = db.execute("""SELECT id FROM external_accounts WHERE provider_key=? AND status='PAUSED'
                AND pause_until<>'' AND pause_until<=?""", (provider_key, now)).fetchall()
            if resumed:
                db.execute("""UPDATE external_accounts SET status='ACTIVE',pause_reason='',pause_until='',
                    connection_status='NOT_CHECKED',connection_message='انتهت مهلة الإيقاف التلقائي؛ أُعيد الحساب إلى المجموعة.',updated_at=?
                    WHERE provider_key=? AND status='PAUSED' AND pause_until<>'' AND pause_until<=?""",
                           (now, provider_key, now))
                for resumed_row in resumed:
                    self.store.log_activity(db, actor=actor, action="integration.account_auto_resumed", module="external-integrations",
                                            object_type="external_account", object_id=resumed_row["id"],
                                            result=json.dumps({"provider": provider_key}, ensure_ascii=False))
            rows = db.execute("""SELECT a.*, 1 AS secret_configured
                FROM external_accounts AS a JOIN external_account_secrets AS s ON s.account_id=a.id
                WHERE a.provider_key=? AND a.status='ACTIVE' AND s.secret_ciphertext<>'' ORDER BY a.created_at,a.id""",
                              (provider_key,)).fetchall()
            eligible = [row for row in rows if service in self._decode_services(row["services_json"])]
            if not eligible:
                raise IntegrationProblem(409, "no_active_account", "لا يوجد حساب نشط ومهيأ لهذا المزود والخدمة.")
            cursor = db.execute("SELECT last_account_id FROM external_rotation_cursors WHERE service=? AND provider_key=?",
                                (service, provider_key)).fetchone()
            previous = cursor["last_account_id"] if cursor else ""
            ids = [row["id"] for row in eligible]
            try:
                next_index = (ids.index(previous) + 1) % len(ids)
            except ValueError:
                next_index = 0
            selected = eligible[next_index]
            db.execute("""INSERT INTO external_rotation_cursors(service,provider_key,last_account_id,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(service,provider_key) DO UPDATE
                SET last_account_id=excluded.last_account_id,updated_at=excluded.updated_at""",
                       (service, provider_key, selected["id"], now))
            last_column = "last_used_video" if service == "VIDEO" else "last_used_audio"
            count_column = "rotation_count_video" if service == "VIDEO" else "rotation_count_audio"
            db.execute(f"UPDATE external_accounts SET {last_column}=?,{count_column}={count_column}+1,updated_at=? WHERE id=?",
                       (now, now, selected["id"]))
            self.store.log_activity(db, actor=actor, action="integration.account_selected", module="external-integrations",
                                    object_type="external_account", object_id=selected["id"],
                                    result=json.dumps({"provider": selected["provider"], "service": service}, ensure_ascii=False))
            row = db.execute("""SELECT a.*, 1 AS secret_configured FROM external_accounts AS a WHERE id=?""",
                             (selected["id"],)).fetchone()
        return self._public_account(row)

    def pause_for_failover(self, account_id: str, *, reason: str, pause_seconds: int | None, actor: str) -> dict[str, Any] | None:
        reason = reason if reason in {"RATE_LIMITED", "CREDITS_EXHAUSTED", "AUTH_ERROR"} else "RATE_LIMITED"
        now = datetime.now(timezone.utc)
        until = ""
        if reason == "RATE_LIMITED":
            delay = max(1, min(int(pause_seconds or 60), 86400))
            until = (now + timedelta(seconds=delay)).isoformat(timespec="seconds").replace("+00:00", "Z")
        now_text = now.isoformat(timespec="seconds").replace("+00:00", "Z")
        messages = {
            "RATE_LIMITED": "أوقف النظام الحساب مؤقتاً بعد 429، وسيُعاد تلقائياً عند انتهاء مهلة المزود.",
            "CREDITS_EXHAUSTED": "أوقف النظام الحساب بعد استجابة نفاد الرصيد/الحزمة؛ أعد تفعيله بعد تحديث الرصيد.",
            "AUTH_ERROR": "أوقف النظام الحساب بعد رفض الاعتماد أو مشكلة صلاحية/سياسة مزود؛ راجع الإعدادات ثم أعد تفعيله.",
        }
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT provider,label FROM external_accounts WHERE id=?", (account_id,)).fetchone()
            if row is None:
                return None
            db.execute("""UPDATE external_accounts SET status='PAUSED',pause_reason=?,pause_until=?,
                connection_status=?,connection_message=?,updated_at=? WHERE id=?""",
                       (reason, until, reason, messages[reason], now_text, account_id))
            self.store.log_activity(db, actor=actor, action="integration.account_auto_paused", module="external-integrations",
                                    object_type="external_account", object_id=account_id,
                                    result=json.dumps({"provider": row["provider"], "reason": reason, "pause_until": until or None}, ensure_ascii=False))
            updated = db.execute("""SELECT a.*,1 AS secret_configured FROM external_accounts AS a WHERE id=?""",
                                 (account_id,)).fetchone()
        return self._public_account(updated)

    @staticmethod
    def _public_generation(row: sqlite3.Row) -> dict[str, Any]:
        try:
            params = json.loads(row["params_json"] or "{}")
        except json.JSONDecodeError:
            params = {}
        try:
            failover = json.loads(row["failover_json"] or "[]")
        except json.JSONDecodeError:
            failover = []
        return {
            "id": row["id"], "kind": row["kind"], "provider": row["provider_key"], "status": row["status"],
            "prompt": row["prompt"], "params": params, "account_id": row["account_id"] or None,
            "audio_account_id": row["audio_account_id"] or None, "video_account_id": row["video_account_id"] or None,
            "provider_task_id": row["provider_task_id"] or None, "audio_url": f"/api/external-integrations/generations/{row['id']}/audio" if row["audio_file"] else None,
            "video_url": row["video_url"] or None, "output_url": f"/api/external-integrations/generations/{row['id']}/media" if row["output_file"] else None,
            "error_message": row["error_message"] or None, "paused_accounts": failover,
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def create_generation(self, *, kind: str, provider: str, prompt: str, params: dict[str, Any], actor: str) -> dict[str, Any]:
        if kind not in {"AUDIO", "VIDEO", "PIPELINE"}:
            raise IntegrationProblem(400, "invalid_generation_kind", "نوع التوليد غير صالح.")
        now = utc_now()
        job = {"id": new_id(), "kind": kind, "provider_key": provider, "status": "PROCESSING", "prompt": prompt,
               "params_json": json.dumps(params, ensure_ascii=False), "created_at": now, "updated_at": now}
        with self.store.connect() as db:
            db.execute("""INSERT INTO media_generation_jobs(id,kind,provider_key,status,prompt,params_json,created_at,updated_at)
                VALUES (:id,:kind,:provider_key,:status,:prompt,:params_json,:created_at,:updated_at)""", job)
            self.store.log_activity(db, actor=actor, action="media.generation_started", module="external-integrations",
                                    object_type="media_generation", object_id=job["id"],
                                    result=json.dumps({"kind": kind, "provider": provider}, ensure_ascii=False))
        created = self.get_generation(job["id"])
        if created is None:
            raise RuntimeError("Generation record disappeared after insertion.")
        return created

    def update_generation(self, generation_id: str, *, actor: str = "owner", **fields: Any) -> dict[str, Any] | None:
        allowed = {"status", "account_id", "audio_account_id", "video_account_id", "provider_task_id", "external_task_id",
                   "audio_file", "video_url", "output_file", "error_message", "failover_json"}
        if set(fields) - allowed:
            raise IntegrationProblem(400, "invalid_generation_update", "تحديث مهمة التوليد يحتوي حقولاً غير مدعومة.")
        fields["updated_at"] = utc_now()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM media_generation_jobs WHERE id=?", (generation_id,)).fetchone() is None:
                return None
            assignment = ",".join(f"{key}=?" for key in fields)
            db.execute(f"UPDATE media_generation_jobs SET {assignment} WHERE id=?", (*fields.values(), generation_id))
            if "status" in fields and fields["status"] in {"COMPLETED", "FAILED"}:
                self.store.log_activity(db, actor=actor, action=f"media.generation_{fields['status'].lower()}", module="external-integrations",
                                        object_type="media_generation", object_id=generation_id,
                                        result=json.dumps({"status": fields["status"]}, ensure_ascii=False),
                                        status="SUCCESS" if fields["status"] == "COMPLETED" else "FAILURE",
                                        error=str(fields.get("error_message", ""))[:300])
        return self.get_generation(generation_id)

    def get_generation(self, generation_id: str) -> dict[str, Any] | None:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM media_generation_jobs WHERE id=?", (generation_id,)).fetchone()
        return self._public_generation(row) if row else None

    def list_generations(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM media_generation_jobs ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
        return [self._public_generation(row) for row in rows]

    def _credential_for_dispatch(self, account_id: str) -> str:
        """Internal adapter hook; never expose this method through an HTTP response."""
        with self.store.connect() as db:
            row = db.execute("SELECT secret_ciphertext FROM external_account_secrets WHERE account_id=?", (account_id,)).fetchone()
        if row is None:
            raise IntegrationProblem(404, "credential_not_found", "بيانات اعتماد الحساب غير موجودة.")
        if not row["secret_ciphertext"]:
            raise IntegrationProblem(404, "credential_not_found", "لا يوجد مفتاح API أساسي محفوظ لهذا النوع من الحساب.")
        try:
            return self._vault().decrypt(row["secret_ciphertext"].encode("ascii")).decode("utf-8")
        except InvalidToken as error:
            raise IntegrationProblem(503, "vault_key_mismatch", "تعذر فك تشفير بيانات الاعتماد؛ تحقق من مفتاح الخزنة.") from error
