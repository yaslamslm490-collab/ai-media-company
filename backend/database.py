"""Database adapters for local SQLite and managed MySQL."""
from __future__ import annotations

import re
import ssl
from collections import defaultdict
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

import pymysql
from pymysql.cursors import DictCursor

IntegrityError = pymysql.err.IntegrityError

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INDEX_RE = re.compile(
    r"^CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s+ON\s+"
    r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*\((.*?)\)",
    re.IGNORECASE | re.DOTALL,
)
_PARTIAL_UNIQUE_RE = re.compile(
    r"^CREATE\s+UNIQUE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+"
    r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s+ON\s+"
    r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*\(\s*"
    r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*\)\s+WHERE\s+"
    r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*<>\s*''\s*;?$",
    re.IGNORECASE | re.DOTALL,
)
_GLOBAL_INDEX_COLUMNS = {
    "tasks": {"id", "status", "created_at", "updated_at", "assigned_employee_id", "project_id"},
    "approvals": {"id", "status", "created_at", "updated_at"},
    "approval_decisions": {"id", "approval_id", "created_at"},
    "activity_logs": {"id", "timestamp", "status", "module", "actor", "action", "object_type", "object_id"},
    "departments": {"id", "name", "code", "status", "manager_employee_id", "updated_at"},
    "ai_employees": {"id", "name", "role_id", "employee_code", "department_id", "status", "employee_type", "lifecycle_status", "created_at", "updated_at"},
    "characters": {"id", "name"},
    "projects": {"id", "name", "created_at", "updated_at"},
    "roles": {"id", "code"},
    "permissions": {"code"},
    "tools": {"id", "code", "required_permission", "status"},
    "knowledge_sources": {"id", "status"},
    "workflows": {"id", "status"},
    "workflow_steps": {"id", "workflow_id"},
    "external_accounts": {"id", "provider_key", "status", "created_at", "updated_at", "account_code"},
    "external_account_secrets": {"account_id"},
    "external_rotation_cursors": {"service", "provider_key"},
    "media_generation_jobs": {"id", "created_at", "status"},
    "organization_relationships": {"employee_id", "manager_employee_id", "parent_employee_id"},
    "employee_permissions": {"employee_id", "permission_code"},
    "employee_tools": {"employee_id", "tool_id"},
    "employee_knowledge_access": {"employee_id", "knowledge_source_id"},
    "product_modules": {"id"},
    "employee_modules": {"employee_id", "module_id"},
    "department_tools": {"department_id", "tool_id"},
    "department_knowledge_access": {"department_id", "knowledge_source_id"},
    "workspace_pages": {"id", "slug", "updated_at"},
    "execution_reports": {"id", "started_at"},
}
_LONG_TEXT_DEFAULT_COLUMNS = {
    "body", "description", "decision_note", "note", "result", "error", "content",
    "source_ref", "endpoint_ref", "prompt", "params_json", "job_description", "system_prompt",
    "personality", "responsibilities_json", "goals_json", "kpis_json", "skills_json", "config_json",
    "steps_json", "tests_json", "changes_json", "snapshot_json",
}
_DEFAULT_VARCHAR_LENGTHS = {
    "connection_message": 512,
    "audio_file": 2048,
    "video_url": 2048,
    "output_file": 2048,
    "error_message": 2048,
    "failover_json": 4096,
}


class CompatRow(dict):
    """Mapping row that also supports SQLite-style integer column access."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> int | None:
        return self._cursor.lastrowid

    def fetchone(self) -> CompatRow | None:
        row = self._cursor.fetchone()
        return CompatRow(row) if row is not None else None

    def fetchall(self) -> list[CompatRow]:
        return [CompatRow(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        return self

    def __next__(self) -> CompatRow:
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class MySQLConnection:
    """Small DB-API facade for the SQLite-flavoured SQL used by this application."""

    is_mysql = True

    def __init__(self, database_url: str):
        parsed = urlsplit(database_url)
        if parsed.scheme not in {"mysql", "mysql+pymysql"} or not parsed.hostname or not parsed.path.strip("/"):
            raise ValueError("DATABASE_URL must be a mysql:// or mysql+pymysql:// URL with a database name.")
        options = parse_qs(parsed.query)
        ssl_mode = (options.get("ssl-mode") or options.get("sslmode") or ["REQUIRED"])[0].upper()
        if ssl_mode in {"DISABLED", "PREFERRED"}:
            raise ValueError("Managed MySQL connections must use verified TLS.")
        tls: dict[str, Any] = {"check_hostname": True, "verify_mode": ssl.CERT_REQUIRED}
        for query_name, driver_name in (("ssl-ca", "ca"), ("ssl_cert", "cert"), ("ssl_key", "key"), ("ssl-cipher", "cipher")):
            value = (options.get(query_name) or [None])[0]
            if value:
                tls[driver_name] = value
        self._raw = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            database=unquote(parsed.path.lstrip("/")),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=10,
            read_timeout=45,
            write_timeout=45,
            ssl=tls,
        )
        self._active_index_columns: dict[str, set[str]] = {}
        self._closed = False

    def __enter__(self) -> "MySQLConnection":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        finally:
            self.close()
        return False

    def close(self) -> None:
        if not self._closed:
            self._raw.close()
            self._closed = True

    def execute(self, sql: str, parameters: Any = ()) -> CompatCursor:
        statement = sql.strip()
        if not statement:
            return CompatCursor(self._raw.cursor())
        if statement.upper().startswith("PRAGMA "):
            return CompatCursor(self._raw.cursor())
        if re.fullmatch(r"BEGIN(?:\s+IMMEDIATE)?", statement, re.IGNORECASE):
            self._raw.begin()
            return CompatCursor(self._raw.cursor())

        partial = _PARTIAL_UNIQUE_RE.match(statement)
        if partial:
            return self._create_partial_unique_index(*partial.groups())

        create_index = _INDEX_RE.match(statement)
        if create_index and re.search(r"\bIF\s+NOT\s+EXISTS\b", statement, re.IGNORECASE):
            index_name, table_name, _columns = create_index.groups()
            if self._index_exists(table_name, index_name):
                return CompatCursor(self._raw.cursor())
            statement = re.sub(r"\bIF\s+NOT\s+EXISTS\b", "", statement, count=1, flags=re.IGNORECASE)

        if re.match(r"^CREATE\s+TABLE\b", statement, re.IGNORECASE):
            statement = _translate_create_table(statement, self._active_index_columns)
        elif re.match(r"^ALTER\s+TABLE\b.*\bADD\s+COLUMN\b", statement, re.IGNORECASE):
            statement = _translate_alter_add_column(statement)
        deferred_constraint = None
        constraint_marker = re.search(r",\s*(ADD\s+CONSTRAINT\b.*)$", statement, re.IGNORECASE | re.DOTALL)
        if constraint_marker:
            deferred_constraint = constraint_marker.group(1)
            statement = statement[:constraint_marker.start()]

        statement = _translate_sql(statement)
        cursor = self._raw.cursor()
        cursor.execute(statement, parameters if parameters is not None else ())
        if deferred_constraint:
            table_match = re.match(r"^ALTER\s+TABLE\s+(`[A-Za-z_][A-Za-z0-9_]*`?|[A-Za-z_][A-Za-z0-9_]*)", statement, re.IGNORECASE)
            if not table_match:
                raise ValueError("invalid_alter_table_name")
            constraint_sql = f"ALTER TABLE {table_match.group(1)} {deferred_constraint}"
            self._raw.cursor().execute(constraint_sql)
        return CompatCursor(cursor)

    def executemany(self, sql: str, parameters: Iterable[Any]) -> CompatCursor:
        statement = _translate_sql(sql.strip())
        cursor = self._raw.cursor()
        cursor.executemany(statement, list(parameters))
        return CompatCursor(cursor)

    def executescript(self, sql_script: str) -> CompatCursor:
        statements = _split_statements(sql_script)
        index_columns = _index_columns(statements)
        previous = self._active_index_columns
        self._active_index_columns = index_columns
        cursor = CompatCursor(self._raw.cursor())
        try:
            for statement in statements:
                if statement.strip():
                    cursor = self.execute(statement)
        finally:
            self._active_index_columns = previous
        return cursor

    def table_columns(self, table: str) -> set[str]:
        if not _IDENTIFIER.fullmatch(table):
            raise ValueError("invalid_table_name")
        rows = self.execute(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name=%s",
            (table,),
        ).fetchall()
        return {str(row["name"]) for row in rows}

    def _index_exists(self, table: str, index: str) -> bool:
        row = self.execute(
            "SELECT 1 AS present FROM information_schema.statistics "
            "WHERE table_schema=DATABASE() AND table_name=%s AND index_name=%s LIMIT 1",
            (table, index),
        ).fetchone()
        return row is not None

    def _create_partial_unique_index(self, index: str, table: str, column: str, predicate_column: str) -> CompatCursor:
        if not all(_IDENTIFIER.fullmatch(value) for value in (index, table, column, predicate_column)) or column != predicate_column:
            raise ValueError("unsupported_partial_unique_index")
        generated = f"_manus_unique_{column}"
        if generated not in self.table_columns(table):
            cursor = self._raw.cursor()
            cursor.execute(
                f"ALTER TABLE `{table}` ADD COLUMN `{generated}` VARCHAR(191) "
                f"GENERATED ALWAYS AS (CASE WHEN `{column}` = '' THEN NULL ELSE `{column}` END) STORED"
            )
        if self._index_exists(table, index):
            return CompatCursor(self._raw.cursor())
        cursor = self._raw.cursor()
        cursor.execute(f"CREATE UNIQUE INDEX `{index}` ON `{table}` (`{generated}`)")
        return CompatCursor(cursor)


def is_mysql_url(value: str | None) -> bool:
    return bool(value and value.startswith(("mysql://", "mysql+pymysql://")))


def connect_mysql(database_url: str) -> MySQLConnection:
    return MySQLConnection(database_url)


def table_columns(db: Any, table: str) -> set[str]:
    """Return table columns for either the MySQL adapter or a native SQLite connection."""
    if getattr(db, "is_mysql", False):
        return db.table_columns(table)
    if not _IDENTIFIER.fullmatch(table):
        raise ValueError("invalid_table_name")
    return {str(row["name"]) for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_migration_table(db: Any) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")


def migration_applied(db: Any, version: str) -> bool:
    return db.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone() is not None


def record_migration(db: Any, version: str, applied_at: str) -> None:
    db.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES (?,?)", (version, applied_at))


def _translate_sql(sql: str) -> str:
    sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT IGNORE INTO", sql, flags=re.IGNORECASE)
    sql = re.sub(
        r"\bON\s+CONFLICT(?:\s*\([^)]*\))?\s+DO\s+UPDATE\s+SET\b",
        "ON DUPLICATE KEY UPDATE",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"\bexcluded\.([A-Za-z_][A-Za-z0-9_]*)", r"VALUES(\1)", sql, flags=re.IGNORECASE)
    return _translate_placeholders(sql)


def _translate_placeholders(sql: str) -> str:
    out: list[str] = []
    quote = ""
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            out.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    out.append(sql[index + 1])
                    index += 1
                else:
                    quote = ""
            elif char == "\\" and index + 1 < len(sql):
                out.append(sql[index + 1])
                index += 1
        elif char in {"'", '"', "`"}:
            quote = char
            out.append(char)
        elif char == "?":
            out.append("%s")
        elif char == ":" and index + 1 < len(sql) and (sql[index + 1].isalpha() or sql[index + 1] == "_"):
            end = index + 2
            while end < len(sql) and (sql[end].isalnum() or sql[end] == "_"):
                end += 1
            out.append("%(" + sql[index + 1:end] + ")s")
            index = end - 1
        else:
            out.append(char)
        index += 1
    return "".join(out)


def _split_statements(script: str) -> list[str]:
    statements: list[str] = []
    start = 0
    quote = ""
    depth = 0
    index = 0
    while index < len(script):
        char = script[index]
        if quote:
            if char == quote:
                if index + 1 < len(script) and script[index + 1] == quote:
                    index += 1
                else:
                    quote = ""
            elif char == "\\":
                index += 1
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == ";" and depth == 0:
            statements.append(script[start:index].strip())
            start = index + 1
        index += 1
    tail = script[start:].strip()
    if tail:
        statements.append(tail)
    return [statement for statement in statements if statement]


def _split_top_level(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote = ""
    depth = 0
    index = 0
    while index < len(value):
        char = value[index]
        if quote:
            if char == quote:
                if index + 1 < len(value) and value[index + 1] == quote:
                    index += 1
                else:
                    quote = ""
            elif char == "\\":
                index += 1
        elif char in {"'", '"', "`"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
        index += 1
    parts.append(value[start:].strip())
    return parts


def _index_columns(statements: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for statement in statements:
        match = _INDEX_RE.match(statement.strip())
        if not match:
            continue
        _name, table, columns = match.groups()
        for part in _split_top_level(columns):
            column = re.match(r"[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?", part.strip())
            if column:
                result[table].add(column.group(1))
    return dict(result)


def _translate_create_table(statement: str, indexed: dict[str, set[str]]) -> str:
    match = re.match(
        r"^(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)([`]?[A-Za-z_][A-Za-z0-9_]*[`]?)\s*\((.*)\)\s*;?$",
        statement.strip(),
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return statement
    prefix, raw_table, body = match.groups()
    table = raw_table.strip("`")
    pieces = _split_top_level(body)
    key_columns = set(indexed.get(table, set())) | _GLOBAL_INDEX_COLUMNS.get(table, set())
    for piece in pieces:
        for constraint in re.finditer(r"\b(?:PRIMARY\s+KEY|UNIQUE|FOREIGN\s+KEY)\s*\(([^)]*)\)", piece, re.IGNORECASE):
            for column_part in constraint.group(1).split(","):
                column = re.match(r"\s*`?([A-Za-z_][A-Za-z0-9_]*)`?", column_part)
                if column:
                    key_columns.add(column.group(1))
        column_match = re.match(r"\s*[`]?(\w+)[`]?\s+(.*)$", piece, re.DOTALL)
        if column_match and not re.match(r"\s*(?:PRIMARY|UNIQUE|FOREIGN|CHECK|CONSTRAINT)\b", piece, re.IGNORECASE):
            name, declaration = column_match.groups()
            if re.search(r"\b(?:PRIMARY\s+KEY|UNIQUE|REFERENCES)\b", declaration, re.IGNORECASE):
                key_columns.add(name)
    translated: list[str] = []
    foreign_keys: list[str] = []
    for piece in pieces:
        column_match = re.match(r"(\s*[`]?(\w+)[`]?\s+)(.*)$", piece, re.DOTALL)
        if not column_match or re.match(r"\s*(?:PRIMARY|UNIQUE|FOREIGN|CHECK|CONSTRAINT)\b", piece, re.IGNORECASE):
            translated.append(piece)
            continue
        head, name, declaration = column_match.groups()
        reference = re.search(
            r"\s+REFERENCES\s+[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*\(\s*[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*\)"
            r"(?:\s+ON\s+DELETE\s+(CASCADE|RESTRICT|SET\s+NULL|NO\s+ACTION))?",
            declaration,
            re.IGNORECASE,
        )
        if reference:
            parent_table, parent_column, on_delete = reference.groups()
            constraint = f"CONSTRAINT `fk_{table}_{name}` FOREIGN KEY (`{name}`) REFERENCES `{parent_table}` (`{parent_column}`)"
            if on_delete:
                constraint += f" ON DELETE {on_delete.upper()}"
            foreign_keys.append(constraint)
            declaration = declaration[:reference.start()] + declaration[reference.end():]
        declaration = _translate_text_type(declaration, name in key_columns or bool(re.search(r"\bREFERENCES\b", declaration, re.IGNORECASE)), name)
        translated.append(head + declaration)
    return prefix + raw_table + " (" + ",\n".join(translated + foreign_keys) + ")"


def _translate_alter_add_column(statement: str) -> str:
    match = re.match(r"^(ALTER\s+TABLE\s+[`]?\w+[`]?\s+ADD\s+COLUMN\s+[`]?(\w+)[`]?\s+)(.*)$", statement.strip(), re.IGNORECASE | re.DOTALL)
    if not match:
        return statement
    prefix, name, declaration = match.groups()
    indexed_names = {
        "code", "employee_code", "status", "employee_type", "lifecycle_status", "name", "updated_at",
        "created_at", "assigned_employee_id", "manager_employee_id", "parent_employee_id", "role_id",
        "department_id", "project_id", "service", "provider_key", "module_id", "permission_code", "tool_id",
        "knowledge_source_id", "employee_id", "workflow_id", "approval_id", "account_id",
    }
    table_match = re.match(r"^ALTER\s+TABLE\s+[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?", statement.strip(), re.IGNORECASE)
    table = table_match.group(1) if table_match else ""
    indexed_or_referenced = name in indexed_names or name in _GLOBAL_INDEX_COLUMNS.get(table, set())
    reference = re.search(
        r"\s+REFERENCES\s+[`]?([A-Za-z_][A-Za-z0-9_]*)[`]?\s*\(\s*[`]?(\w+)[`]?\s*\)"
        r"(?:\s+ON\s+DELETE\s+(CASCADE|RESTRICT|SET\s+NULL|NO\s+ACTION))?",
        declaration,
        re.IGNORECASE,
    )
    foreign_key = ""
    if reference:
        parent_table, parent_column, on_delete = reference.groups()
        foreign_key = f", ADD CONSTRAINT `fk_{table}_{name}` FOREIGN KEY (`{name}`) REFERENCES `{parent_table}` (`{parent_column}`)"
        if on_delete:
            foreign_key += f" ON DELETE {on_delete.upper()}"
        declaration = declaration[:reference.start()] + declaration[reference.end():]
    declaration = _translate_text_type(declaration, indexed_or_referenced, name)
    return prefix + declaration + foreign_key


def _translate_text_type(declaration: str, indexed_or_referenced: bool, column_name: str = "") -> str:
    if not re.search(r"\bTEXT\b", declaration, re.IGNORECASE):
        return declaration
    has_default = bool(re.search(r"\bDEFAULT\b", declaration, re.IGNORECASE))
    if indexed_or_referenced:
        replacement = "VARCHAR(191)"
    elif column_name in _LONG_TEXT_DEFAULT_COLUMNS:
        replacement = "LONGTEXT"
        declaration = re.sub(
            r"\s+DEFAULT\s+(?:\(\s*'(?:''|[^'])*'\s*\)|'(?:''|[^'])*')",
            "",
            declaration,
            count=1,
            flags=re.IGNORECASE,
        )
    elif has_default:
        replacement = f"VARCHAR({_DEFAULT_VARCHAR_LENGTHS.get(column_name, 191)})"
    else:
        replacement = "LONGTEXT"
    declaration = re.sub(r"\bTEXT\b", replacement, declaration, count=1, flags=re.IGNORECASE)
    return declaration
