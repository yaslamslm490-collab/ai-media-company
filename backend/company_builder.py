"""Database-backed Company Builder entities and operations.

This module extends the existing SQLite store; it never replaces Phase 1 tables.
Secrets are intentionally not represented by any schema field here.
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from backend.modules import MODULES
from backend.store import Store, new_id, utc_now


EMPLOYEE_TYPES = {"MANAGER", "EMPLOYEE", "WORKER"}
EMPLOYEE_STATUSES = {"ACTIVE", "PAUSED", "INACTIVE"}
PRIORITIES = {"LOW", "NORMAL", "HIGH", "URGENT"}
TOOL_STATUSES = {"ACTIVE", "INACTIVE"}
WORKFLOW_STATUSES = {"DRAFT", "ACTIVE", "PAUSED", "ARCHIVED"}
EMPLOYEE_MODULE_IDS = {"tasks", "projects", "ai-team", "characters", "character-bibles", "localization", "content", "production", "media-vault", "publishing", "analytics"}

PERMISSIONS = [
    ("VIEW_DATA", "عرض البيانات", 0),
    ("CREATE_TASK", "إنشاء المهام", 0),
    ("EDIT_TASK", "تعديل المهام", 0),
    ("CREATE_CONTENT", "إنشاء المحتوى", 0),
    ("EDIT_CONTENT", "تعديل المحتوى", 0),
    ("REVIEW_CONTENT", "مراجعة المحتوى", 0),
    ("ACCESS_CHARACTER", "الوصول إلى الشخصيات", 0),
    ("ACCESS_PROJECT", "الوصول إلى المشاريع", 0),
    ("USE_AI_MODEL", "استخدام نموذج ذكاء اصطناعي", 0),
    ("USE_TOOL", "استخدام الأدوات", 0),
    ("REQUEST_PUBLISH", "طلب النشر", 1),
    ("PUBLISH", "النشر الخارجي", 1),
    ("MANAGE_EMPLOYEES", "إدارة الموظفين", 1),
    ("MANAGE_DEPARTMENTS", "إدارة الأقسام", 1),
    ("MANAGE_SETTINGS", "إدارة الإعدادات", 1),
]
ROLE_SEEDS = [
    ("role-ai-manager", "AI_MANAGER", "مدير AI", "إدارة فريق وقسم مع صلاحيات محدودة."),
    ("role-ai-employee", "AI_EMPLOYEE", "موظف AI", "موظف ذكاء اصطناعي بصلاحيات تنفيذية محدودة."),
    ("role-ai-worker", "AI_WORKER", "عامل AI", "عامل متخصص بصلاحيات أساسية."),
]
ROLE_PERMISSION_SEEDS = {
    "AI_MANAGER": {"VIEW_DATA", "CREATE_TASK", "EDIT_TASK", "CREATE_CONTENT", "EDIT_CONTENT",
                   "REVIEW_CONTENT", "ACCESS_CHARACTER", "ACCESS_PROJECT", "USE_AI_MODEL", "USE_TOOL",
                   "MANAGE_EMPLOYEES"},
    "AI_EMPLOYEE": {"VIEW_DATA", "CREATE_TASK", "CREATE_CONTENT", "ACCESS_CHARACTER", "ACCESS_PROJECT", "USE_AI_MODEL"},
    "AI_WORKER": {"VIEW_DATA", "CREATE_TASK", "CREATE_CONTENT", "USE_AI_MODEL"},
}
DEFAULT_ROLE_FOR_TYPE = {"MANAGER": "AI_MANAGER", "EMPLOYEE": "AI_EMPLOYEE", "WORKER": "AI_WORKER"}
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{24,}"),
)


def _reject_secret_material(*values: Any) -> None:
    for value in values:
        if isinstance(value, (list, tuple)):
            _reject_secret_material(*value)
            continue
        if isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
            raise ValueError("secret_material_rejected")


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [part.strip() for part in stripped.splitlines() if part.strip()]
    return []


def _decode_json(value: str | None, fallback: Any = None) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return [] if fallback is None else fallback


class CompanyBuilderStore:
    """Company entities sharing the original Store connection and activity log."""

    def __init__(self, store: Store):
        self.store = store

    def initialize(self) -> None:
        with self.store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS roles (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    is_system INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS permissions (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    sensitive INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS role_permissions (
                    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                    permission_code TEXT NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
                    PRIMARY KEY (role_id, permission_code)
                );
                CREATE TABLE IF NOT EXISTS tools (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    tool_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    endpoint_ref TEXT NOT NULL DEFAULT '',
                    required_permission TEXT REFERENCES permissions(code),
                    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','ACTIVE','PAUSED','ARCHIVED')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'READY',
                    config_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(workflow_id, position)
                );
            """)
            self._add_columns(db, "departments", {
                "code": "TEXT NOT NULL DEFAULT ''",
                "goals_json": "TEXT NOT NULL DEFAULT '[]'",
                "kpis_json": "TEXT NOT NULL DEFAULT '[]'",
                "priority": "TEXT NOT NULL DEFAULT 'NORMAL'",
                "allowed_tools_json": "TEXT NOT NULL DEFAULT '[]'",
                "knowledge_source_ids_json": "TEXT NOT NULL DEFAULT '[]'",
                "manager_employee_id": "TEXT REFERENCES ai_employees(id) ON DELETE SET NULL",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
            })
            self._add_columns(db, "ai_employees", {
                "role_id": "TEXT REFERENCES roles(id) ON DELETE SET NULL",
                "employee_type": "TEXT NOT NULL DEFAULT 'EMPLOYEE' CHECK(employee_type IN ('MANAGER','EMPLOYEE','WORKER'))",
                "employee_code": "TEXT NOT NULL DEFAULT ''",
                "job_description": "TEXT NOT NULL DEFAULT ''",
                "responsibilities_json": "TEXT NOT NULL DEFAULT '[]'",
                "goals_json": "TEXT NOT NULL DEFAULT '[]'",
                "kpis_json": "TEXT NOT NULL DEFAULT '[]'",
                "system_prompt": "TEXT NOT NULL DEFAULT ''",
                "personality": "TEXT NOT NULL DEFAULT ''",
                "skills_json": "TEXT NOT NULL DEFAULT '[]'",
                "preferred_model": "TEXT NOT NULL DEFAULT ''",
                "fallback_model": "TEXT NOT NULL DEFAULT ''",
                "priority": "TEXT NOT NULL DEFAULT 'NORMAL'",
                "memory_enabled": "INTEGER NOT NULL DEFAULT 1",
                "lifecycle_status": "TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(lifecycle_status IN ('ACTIVE','PAUSED','INACTIVE'))",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
            })
            self._add_columns(db, "tasks", {
                "assigned_employee_id": "TEXT REFERENCES ai_employees(id) ON DELETE SET NULL",
                "project_id": "TEXT REFERENCES projects(id) ON DELETE SET NULL",
                "deadline": "TEXT",
                "approval_required": "INTEGER NOT NULL DEFAULT 0",
            })
            db.executescript("""
                CREATE UNIQUE INDEX IF NOT EXISTS departments_code_unique_idx ON departments(code) WHERE code <> '';
                CREATE INDEX IF NOT EXISTS departments_status_idx ON departments(status, name);
                CREATE UNIQUE INDEX IF NOT EXISTS ai_employee_code_unique_idx ON ai_employees(employee_code) WHERE employee_code <> '';
                CREATE INDEX IF NOT EXISTS ai_employee_type_status_idx ON ai_employees(employee_type, lifecycle_status, name);
                CREATE INDEX IF NOT EXISTS ai_employee_department_idx ON ai_employees(department_id, name);
                CREATE INDEX IF NOT EXISTS tasks_assigned_employee_idx ON tasks(assigned_employee_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS organization_relationships (
                    employee_id TEXT PRIMARY KEY REFERENCES ai_employees(id) ON DELETE CASCADE,
                    manager_employee_id TEXT REFERENCES ai_employees(id) ON DELETE SET NULL,
                    parent_employee_id TEXT REFERENCES ai_employees(id) ON DELETE SET NULL,
                    updated_at TEXT NOT NULL,
                    CHECK(manager_employee_id IS NULL OR manager_employee_id <> employee_id),
                    CHECK(parent_employee_id IS NULL OR parent_employee_id <> employee_id)
                );
                CREATE INDEX IF NOT EXISTS organization_manager_idx ON organization_relationships(manager_employee_id);
                CREATE INDEX IF NOT EXISTS organization_parent_idx ON organization_relationships(parent_employee_id);
                CREATE TABLE IF NOT EXISTS employee_permissions (
                    employee_id TEXT NOT NULL REFERENCES ai_employees(id) ON DELETE CASCADE,
                    permission_code TEXT NOT NULL REFERENCES permissions(code) ON DELETE CASCADE,
                    granted_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(employee_id, permission_code)
                );
                CREATE TABLE IF NOT EXISTS employee_tools (
                    employee_id TEXT NOT NULL REFERENCES ai_employees(id) ON DELETE CASCADE,
                    tool_id TEXT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
                    granted_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(employee_id, tool_id)
                );
                CREATE TABLE IF NOT EXISTS employee_knowledge_access (
                    employee_id TEXT NOT NULL REFERENCES ai_employees(id) ON DELETE CASCADE,
                    knowledge_source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
                    granted_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(employee_id, knowledge_source_id)
                );
                CREATE TABLE IF NOT EXISTS product_modules (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    employee_assignable INTEGER NOT NULL DEFAULT 0 CHECK(employee_assignable IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS employee_modules (
                    employee_id TEXT NOT NULL REFERENCES ai_employees(id) ON DELETE CASCADE,
                    module_id TEXT NOT NULL REFERENCES product_modules(id) ON DELETE CASCADE,
                    granted_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(employee_id,module_id)
                );
                CREATE INDEX IF NOT EXISTS employee_modules_module_idx ON employee_modules(module_id,employee_id);
                CREATE TABLE IF NOT EXISTS department_tools (
                    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
                    tool_id TEXT NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
                    PRIMARY KEY(department_id, tool_id)
                );
                CREATE TABLE IF NOT EXISTS department_knowledge_access (
                    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
                    knowledge_source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
                    PRIMARY KEY(department_id, knowledge_source_id)
                );
            """)
            self._seed_roles_permissions(db)
            db.executemany("INSERT INTO product_modules(id,title,employee_assignable) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,employee_assignable=excluded.employee_assignable",
                           [(item["id"],item["title"],1 if item["id"] in EMPLOYEE_MODULE_IDS else 0) for item in MODULES])
            self._backfill_existing_records(db)

    @staticmethod
    def _add_columns(db: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, declaration in columns.items():
            if name not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

    def _seed_roles_permissions(self, db: sqlite3.Connection) -> None:
        now = utc_now()
        for code, name, sensitive in PERMISSIONS:
            db.execute("INSERT OR IGNORE INTO permissions(code,name,sensitive,created_at) VALUES (?,?,?,?)",
                       (code, name, sensitive, now))
        for role_id, code, name, description in ROLE_SEEDS:
            db.execute("INSERT OR IGNORE INTO roles(id,code,name,description,is_system,created_at) VALUES (?,?,?,?,1,?)",
                       (role_id, code, name, description, now))
        role_rows = {row["code"]: row["id"] for row in db.execute("SELECT id,code FROM roles")}
        for role_code, codes in ROLE_PERMISSION_SEEDS.items():
            role_id = role_rows.get(role_code)
            if not role_id:
                continue
            for permission_code in codes:
                db.execute("INSERT OR IGNORE INTO role_permissions(role_id,permission_code) VALUES (?,?)",
                           (role_id, permission_code))

    def _backfill_existing_records(self, db: sqlite3.Connection) -> None:
        now = utc_now()
        db.execute("UPDATE departments SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL")
        db.execute("UPDATE ai_employees SET lifecycle_status=CASE WHEN status='ACTIVE' THEN 'ACTIVE' ELSE 'INACTIVE' END WHERE updated_at='' OR updated_at IS NULL")
        db.execute("UPDATE ai_employees SET updated_at=created_at WHERE updated_at='' OR updated_at IS NULL")
        db.execute("UPDATE ai_employees SET employee_code='AI-' || upper(substr(id,1,8)) WHERE employee_code='' OR employee_code IS NULL")
        role_rows = {row["code"]: row["id"] for row in db.execute("SELECT id,code FROM roles")}
        employee_rows = db.execute("SELECT id,employee_type,role_id FROM ai_employees").fetchall()
        for row in employee_rows:
            role_id = row["role_id"] or role_rows.get(DEFAULT_ROLE_FOR_TYPE.get(row["employee_type"], "AI_EMPLOYEE"))
            if role_id:
                db.execute("UPDATE ai_employees SET role_id=? WHERE id=? AND role_id IS NULL", (role_id, row["id"]))
                permissions = db.execute("SELECT permission_code FROM role_permissions WHERE role_id=?", (role_id,)).fetchall()
                for permission in permissions:
                    db.execute("INSERT OR IGNORE INTO employee_permissions(employee_id,permission_code,granted_by,created_at) VALUES (?,?,?,?)",
                               (row["id"], permission["permission_code"], "system", now))
            db.execute("INSERT OR IGNORE INTO organization_relationships(employee_id,updated_at) VALUES (?,?)", (row["id"], now))
        db.execute("""UPDATE tasks SET assigned_employee_id=(
                SELECT id FROM ai_employees WHERE ai_employees.name=tasks.assigned_employee LIMIT 1)
                WHERE assigned_employee_id IS NULL AND assigned_employee<>''""")
        db.execute("""UPDATE departments SET manager_employee_id=(
                SELECT id FROM ai_employees WHERE department_id=departments.id AND employee_type='MANAGER' AND lifecycle_status='ACTIVE' ORDER BY created_at LIMIT 1)
                WHERE manager_employee_id IS NULL""")

    @staticmethod
    def _parse_entity(row: sqlite3.Row | dict[str, Any], json_columns: tuple[str, ...] = ()) -> dict[str, Any]:
        item = dict(row)
        for column in json_columns:
            item[column.removesuffix("_json")] = _decode_json(item.pop(column, "[]"), [])
        return item

    @staticmethod
    def _log(db: sqlite3.Connection, store: Store, actor: str, action: str, object_type: str,
             object_id: str, result: str = "", status: str = "SUCCESS", error: str = "") -> None:
        store.log_activity(db, actor=actor, action=action, module="company-builder", object_type=object_type,
                           object_id=object_id, status=status, result=result[:500], error=error[:500])

    @staticmethod
    def _ensure_ids(db: sqlite3.Connection, table: str, column: str, ids: list[str]) -> None:
        clean = list(dict.fromkeys(str(value) for value in ids if str(value).strip()))
        if not clean:
            return
        allowed = {"tools": "tools", "knowledge_sources": "knowledge_sources", "permissions": "permissions", "product_modules": "product_modules"}
        if table not in allowed:
            raise ValueError("invalid_reference_table")
        placeholders = ",".join("?" for _ in clean)
        found = {row[0] for row in db.execute(f"SELECT {column} FROM {allowed[table]} WHERE {column} IN ({placeholders})", clean)}
        if found != set(clean):
            raise ValueError("invalid_reference")

    def list_departments(self) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows = db.execute("""SELECT d.*, e.name AS manager_name FROM departments d
                LEFT JOIN ai_employees e ON e.id=d.manager_employee_id ORDER BY d.name""").fetchall()
            result = []
            for row in rows:
                item = self._parse_entity(row, ("goals_json", "kpis_json", "allowed_tools_json", "knowledge_source_ids_json"))
                item["allowed_tools"] = [r[0] for r in db.execute("SELECT tool_id FROM department_tools WHERE department_id=? ORDER BY tool_id", (item["id"],))]
                item["knowledge_source_ids"] = [r[0] for r in db.execute("SELECT knowledge_source_id FROM department_knowledge_access WHERE department_id=? ORDER BY knowledge_source_id", (item["id"],))]
                result.append(item)
        return result

    def get_department(self, department_id: str) -> dict[str, Any] | None:
        return next((item for item in self.list_departments() if item["id"] == department_id), None)

    def create_department(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        _reject_secret_material(*payload.values())
        now, item_id = utc_now(), new_id()
        code = payload.get("code", "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{2,32}", code):
            raise ValueError("invalid_department_code")
        tools = _json_list(payload.get("allowed_tools"))
        knowledge = _json_list(payload.get("knowledge_source_ids"))
        with self.store.connect() as db:
            if payload.get("manager_employee_id"):
                manager = db.execute("SELECT employee_type,lifecycle_status,department_id FROM ai_employees WHERE id=?", (payload["manager_employee_id"],)).fetchone()
                if not manager or manager["employee_type"] != "MANAGER" or manager["lifecycle_status"] != "ACTIVE":
                    raise ValueError("invalid_department_manager")
                if manager["department_id"] != item_id: raise ValueError("department_manager_mismatch")
            self._ensure_ids(db, "tools", "id", tools)
            self._ensure_ids(db, "knowledge_sources", "id", knowledge)
            db.execute("""INSERT INTO departments
                (id,name,description,status,created_at,code,goals_json,kpis_json,priority,allowed_tools_json,knowledge_source_ids_json,manager_employee_id,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item_id,payload["name"],payload.get("description",""),payload.get("status","ACTIVE"),now,code,
                 json.dumps(_json_list(payload.get("goals")),ensure_ascii=False),json.dumps(_json_list(payload.get("kpis")),ensure_ascii=False),
                 payload.get("priority","NORMAL"),json.dumps(tools),json.dumps(knowledge),payload.get("manager_employee_id") or None,now))
            self._replace_department_links(db, item_id, tools, knowledge)
            self._log(db,self.store,actor,"department.created","department",item_id,payload["name"])
        return self.get_department(item_id) or {}

    @staticmethod
    def _replace_department_links(db: sqlite3.Connection, department_id: str, tools: list[str], knowledge: list[str]) -> None:
        db.execute("DELETE FROM department_tools WHERE department_id=?", (department_id,))
        db.execute("DELETE FROM department_knowledge_access WHERE department_id=?", (department_id,))
        db.executemany("INSERT INTO department_tools(department_id,tool_id) VALUES (?,?)", [(department_id, value) for value in tools])
        db.executemany("INSERT INTO department_knowledge_access(department_id,knowledge_source_id) VALUES (?,?)", [(department_id, value) for value in knowledge])

    def update_department(self, department_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any] | None:
        _reject_secret_material(*payload.values())
        allowed = {"name","code","description","status","goals","kpis","priority","manager_employee_id","allowed_tools","knowledge_source_ids"}
        fields = {key:value for key,value in payload.items() if key in allowed}
        if not fields:
            raise ValueError("empty_update")
        with self.store.connect() as db:
            current = db.execute("SELECT * FROM departments WHERE id=?", (department_id,)).fetchone()
            if not current:
                return None
            values: dict[str, Any] = {}
            for key, value in fields.items():
                if key == "code":
                    value = str(value).strip().upper()
                    if not re.fullmatch(r"[A-Z0-9_-]{2,32}", value): raise ValueError("invalid_department_code")
                if key in {"goals","kpis"}: value = json.dumps(_json_list(value),ensure_ascii=False)
                if key == "priority" and value not in PRIORITIES: raise ValueError("invalid_priority")
                if key == "status" and value not in {"ACTIVE","INACTIVE"}: raise ValueError("invalid_status")
                if key == "manager_employee_id" and value:
                    manager = db.execute("SELECT employee_type,lifecycle_status,department_id FROM ai_employees WHERE id=?", (value,)).fetchone()
                    if not manager or manager["employee_type"] != "MANAGER" or manager["lifecycle_status"] != "ACTIVE": raise ValueError("invalid_department_manager")
                    if manager["department_id"] != department_id: raise ValueError("department_manager_mismatch")
                if key == "allowed_tools": self._ensure_ids(db,"tools","id",_json_list(value)); values["allowed_tools_json"] = json.dumps(_json_list(value))
                elif key == "knowledge_source_ids": self._ensure_ids(db,"knowledge_sources","id",_json_list(value)); values["knowledge_source_ids_json"] = json.dumps(_json_list(value))
                elif key == "manager_employee_id": values[key] = value or None
                else: values[key] = value
            if "name" in values and not str(values["name"]).strip(): raise ValueError("required_field")
            values["updated_at"] = utc_now()
            db.execute("UPDATE departments SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?", (*values.values(),department_id))
            if "allowed_tools" in fields or "knowledge_source_ids" in fields:
                old_tools=[r[0] for r in db.execute("SELECT tool_id FROM department_tools WHERE department_id=?",(department_id,))] if "allowed_tools" not in fields else _json_list(fields["allowed_tools"])
                old_knowledge=[r[0] for r in db.execute("SELECT knowledge_source_id FROM department_knowledge_access WHERE department_id=?",(department_id,))] if "knowledge_source_ids" not in fields else _json_list(fields["knowledge_source_ids"])
                self._replace_department_links(db,department_id,old_tools,old_knowledge)
            self._log(db,self.store,actor,"department.updated","department",department_id,",".join(sorted(fields)))
        return self.get_department(department_id)

    def delete_department(self, department_id: str, actor: str) -> bool:
        with self.store.connect() as db:
            row=db.execute("SELECT name FROM departments WHERE id=?",(department_id,)).fetchone()
            if not row: return False
            if db.execute("SELECT 1 FROM ai_employees WHERE department_id=? LIMIT 1",(department_id,)).fetchone(): raise ValueError("department_has_employees")
            if db.execute("SELECT 1 FROM tasks WHERE department=? LIMIT 1",(row["name"],)).fetchone(): raise ValueError("department_has_tasks")
            db.execute("DELETE FROM departments WHERE id=?",(department_id,))
            self._log(db,self.store,actor,"department.deleted","department",department_id,row["name"])
        return True

    def list_employees(self, *, employee_type: str = "", status: str = "", search: str = "") -> list[dict[str, Any]]:
        clauses=[]; params: list[Any]=[]
        if employee_type: clauses.append("e.employee_type=?"); params.append(employee_type)
        if status: clauses.append("e.lifecycle_status=?"); params.append(status)
        if search: clauses.append("(e.name LIKE ? OR e.role LIKE ? OR e.employee_code LIKE ? OR d.name LIKE ?)"); params.extend([f"%{search}%"]*4)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        with self.store.connect() as db:
            rows=db.execute("""SELECT e.*,d.name AS department_name,r.name AS role_name,
                rel.manager_employee_id,manager.name AS manager_name,rel.parent_employee_id,parent.name AS parent_employee_name
                FROM ai_employees e LEFT JOIN departments d ON d.id=e.department_id
                LEFT JOIN roles r ON r.id=e.role_id
                LEFT JOIN organization_relationships rel ON rel.employee_id=e.id
                LEFT JOIN ai_employees manager ON manager.id=rel.manager_employee_id
                LEFT JOIN ai_employees parent ON parent.id=rel.parent_employee_id"""+where+" ORDER BY e.employee_type,e.name",params).fetchall()
        output=[]
        for row in rows:
            item=self._parse_entity(row,("responsibilities_json","goals_json","kpis_json","skills_json"))
            item["status"]=item.get("lifecycle_status") or item.get("status")
            item["department"]=item.get("department_name") or ""
            item["memory_enabled"]=bool(item["memory_enabled"])
            output.append(item)
        return output

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        item=next((row for row in self.list_employees() if row["id"]==employee_id),None)
        if item is None: return None
        with self.store.connect() as db:
            item["permissions"]=[r[0] for r in db.execute("SELECT permission_code FROM employee_permissions WHERE employee_id=? ORDER BY permission_code",(employee_id,))]
            item["tools"]=[dict(r) for r in db.execute("SELECT t.id,t.code,t.name,t.tool_type,t.status FROM employee_tools et JOIN tools t ON t.id=et.tool_id WHERE et.employee_id=? ORDER BY t.name",(employee_id,))]
            item["knowledge_sources"]=[dict(r) for r in db.execute("SELECT k.id,k.name,k.source_type,k.description,k.status FROM employee_knowledge_access ea JOIN knowledge_sources k ON k.id=ea.knowledge_source_id WHERE ea.employee_id=? ORDER BY k.name",(employee_id,))]
            item["modules"]=[r[0] for r in db.execute("SELECT module_id FROM employee_modules WHERE employee_id=? ORDER BY module_id",(employee_id,))]
        return item

    def create_employee(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        now, employee_id = utc_now(), new_id()
        employee_type=payload.get("employee_type","EMPLOYEE").upper()
        status=payload.get("status","ACTIVE").upper()
        priority=payload.get("priority","NORMAL").upper()
        if employee_type not in EMPLOYEE_TYPES: raise ValueError("invalid_employee_type")
        if status not in EMPLOYEE_STATUSES: raise ValueError("invalid_employee_status")
        if priority not in PRIORITIES: raise ValueError("invalid_priority")
        _reject_secret_material(*payload.values())
        department_id=payload.get("department_id") or None
        role_id=payload.get("role_id") or None
        tools=_json_list(payload.get("tools")); knowledge=_json_list(payload.get("knowledge_source_ids")); modules=_json_list(payload.get("modules")); permissions=_json_list(payload.get("permissions"))
        with self.store.connect() as db:
            if department_id and not db.execute("SELECT 1 FROM departments WHERE id=?",(department_id,)).fetchone(): raise ValueError("invalid_department")
            if not department_id: raise ValueError("department_required")
            role=db.execute("SELECT * FROM roles WHERE id=? OR code=?",(role_id,role_id)).fetchone() if role_id else None
            if role is None:
                role_code=DEFAULT_ROLE_FOR_TYPE[employee_type]
                role=db.execute("SELECT * FROM roles WHERE code=?",(role_code,)).fetchone()
            role_id=role["id"] if role else None
            manager_id=payload.get("manager_employee_id") or None
            parent_id=payload.get("parent_employee_id") or None
            self._validate_relationships(db,employee_id,manager_id,parent_id,department_id)
            self._ensure_ids(db,"tools","id",tools); self._ensure_ids(db,"knowledge_sources","id",knowledge); self._ensure_ids(db,"permissions","code",permissions)
            self._validate_employee_modules(db,modules)
            employee_code=(payload.get("employee_code") or f"AI-{employee_id[:8].upper()}").strip().upper()
            if not re.fullmatch(r"[A-Z0-9_-]{2,32}",employee_code): raise ValueError("invalid_employee_code")
            role_text=(payload.get("role") or (role["name"] if role else employee_type)).strip()
            values=(employee_id,payload["name"],role_text,payload.get("description","").strip(),department_id,"INACTIVE" if status!="ACTIVE" else "ACTIVE",now,
                role_id,employee_type,employee_code,payload.get("job_description","").strip(),json.dumps(_json_list(payload.get("responsibilities")),ensure_ascii=False),
                json.dumps(_json_list(payload.get("goals")),ensure_ascii=False),json.dumps(_json_list(payload.get("kpis")),ensure_ascii=False),
                payload.get("system_prompt","").strip(),payload.get("personality","").strip(),json.dumps(_json_list(payload.get("skills")),ensure_ascii=False),
                payload.get("preferred_model","").strip(),payload.get("fallback_model","").strip(),priority,1 if payload.get("memory_enabled",True) else 0,status,now)
            db.execute("""INSERT INTO ai_employees
                (id,name,role,description,department_id,status,created_at,role_id,employee_type,employee_code,job_description,responsibilities_json,goals_json,kpis_json,system_prompt,personality,skills_json,preferred_model,fallback_model,priority,memory_enabled,lifecycle_status,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",values)
            db.execute("INSERT INTO organization_relationships(employee_id,manager_employee_id,parent_employee_id,updated_at) VALUES (?,?,?,?)",(employee_id,manager_id,parent_id,now))
            if employee_type=="MANAGER":
                db.execute("UPDATE departments SET manager_employee_id=COALESCE(manager_employee_id,?),updated_at=? WHERE id=?",(employee_id,now,department_id))
            defaults=[r[0] for r in db.execute("SELECT permission_code FROM role_permissions WHERE role_id=?",(role_id,))] if role_id else []
            grants=permissions if "permissions" in payload else defaults
            for code in set(grants):
                db.execute("INSERT OR IGNORE INTO employee_permissions(employee_id,permission_code,granted_by,created_at) VALUES (?,?,?,?)",(employee_id,code,actor,now))
            self._replace_employee_links(db,employee_id,tools,knowledge,modules,actor)
            self._log(db,self.store,actor,f"{employee_type.lower()}.created","ai_employee",employee_id,payload["name"])
        return self.get_employee(employee_id) or {}

    @staticmethod
    def _validate_relationships(db: sqlite3.Connection, employee_id: str, manager_id: str | None,
                                parent_id: str | None, department_id: str | None) -> None:
        for candidate in (manager_id,parent_id):
            if candidate and not db.execute("SELECT 1 FROM ai_employees WHERE id=?",(candidate,)).fetchone(): raise ValueError("invalid_relationship")
            if candidate==employee_id: raise ValueError("organization_cycle")
        if manager_id:
            row=db.execute("SELECT employee_type,lifecycle_status,department_id FROM ai_employees WHERE id=?",(manager_id,)).fetchone()
            if row["employee_type"]!="MANAGER" or row["lifecycle_status"]!="ACTIVE": raise ValueError("manager_must_be_active_manager")
            if row["department_id"] != department_id: raise ValueError("manager_department_mismatch")
        if parent_id:
            parent=db.execute("SELECT department_id FROM ai_employees WHERE id=?",(parent_id,)).fetchone()
            if parent["department_id"] != department_id: raise ValueError("parent_department_mismatch")
        for start, column in ((manager_id,"manager_employee_id"),(parent_id,"parent_employee_id")):
            current=start; seen=set()
            while current:
                if current==employee_id or current in seen: raise ValueError("organization_cycle")
                seen.add(current)
                row=db.execute(f"SELECT {column} FROM organization_relationships WHERE employee_id=?",(current,)).fetchone()
                current=row[0] if row else None

    @staticmethod
    def _validate_employee_modules(db: sqlite3.Connection, modules: list[str]) -> None:
        allowed=set(EMPLOYEE_MODULE_IDS)
        if not set(modules).issubset(allowed): raise ValueError("invalid_employee_module")
        CompanyBuilderStore._ensure_ids(db,"product_modules","id",modules)

    @staticmethod
    def _replace_employee_links(db: sqlite3.Connection, employee_id: str, tools: list[str], knowledge: list[str], modules: list[str], actor: str) -> None:
        now=utc_now()
        db.execute("DELETE FROM employee_tools WHERE employee_id=?",(employee_id,))
        db.execute("DELETE FROM employee_knowledge_access WHERE employee_id=?",(employee_id,))
        db.execute("DELETE FROM employee_modules WHERE employee_id=?",(employee_id,))
        db.executemany("INSERT INTO employee_tools(employee_id,tool_id,granted_by,created_at) VALUES (?,?,?,?)",[(employee_id,item,actor,now) for item in tools])
        db.executemany("INSERT INTO employee_knowledge_access(employee_id,knowledge_source_id,granted_by,created_at) VALUES (?,?,?,?)",[(employee_id,item,actor,now) for item in knowledge])
        db.executemany("INSERT INTO employee_modules(employee_id,module_id,granted_by,created_at) VALUES (?,?,?,?)",[(employee_id,item,actor,now) for item in modules])

    def update_employee(self, employee_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any] | None:
        allowed={"name","role","description","department_id","employee_code","job_description","responsibilities","goals","kpis","system_prompt","personality","skills","preferred_model","fallback_model","priority","memory_enabled","status","manager_employee_id","parent_employee_id","role_id","tools","knowledge_source_ids","modules","permissions"}
        fields={key:value for key,value in payload.items() if key in allowed}
        if not fields: raise ValueError("empty_update")
        _reject_secret_material(*fields.values())
        with self.store.connect() as db:
            current=db.execute("SELECT * FROM ai_employees WHERE id=?",(employee_id,)).fetchone()
            if not current: return None
            values={}; now=utc_now()
            for key,value in fields.items():
                if key in {"responsibilities","goals","kpis","skills"}: values[key+"_json"]=json.dumps(_json_list(value),ensure_ascii=False)
                elif key=="memory_enabled": values[key]=1 if bool(value) else 0
                elif key=="status":
                    status=str(value).upper()
                    if status not in EMPLOYEE_STATUSES: raise ValueError("invalid_employee_status")
                    values["lifecycle_status"]=status; values["status"]="ACTIVE" if status=="ACTIVE" else "INACTIVE"
                elif key=="employee_code":
                    code=str(value).strip().upper()
                    if not re.fullmatch(r"[A-Z0-9_-]{2,32}",code): raise ValueError("invalid_employee_code")
                    values[key]=code
                elif key=="priority":
                    priority=str(value).upper()
                    if priority not in PRIORITIES: raise ValueError("invalid_priority")
                    values[key]=priority
                elif key=="department_id":
                    if value and not db.execute("SELECT 1 FROM departments WHERE id=?",(value,)).fetchone(): raise ValueError("invalid_department")
                    values[key]=value or None
                elif key=="role_id":
                    role=db.execute("SELECT name FROM roles WHERE id=?",(value,)).fetchone() if value else None
                    if value and not role: raise ValueError("invalid_role")
                    values[key]=value or None
                    if role and "role" not in fields: values["role"]=role["name"]
                elif key in {"manager_employee_id","parent_employee_id"}:
                    pass
                elif key in {"tools","knowledge_source_ids","modules"}:
                    refs=_json_list(value)
                    if key=="tools": self._ensure_ids(db,"tools","id",refs)
                    elif key=="knowledge_source_ids": self._ensure_ids(db,"knowledge_sources","id",refs)
                    else: self._validate_employee_modules(db,refs)
                elif key=="permissions":
                    refs=_json_list(value)
                    self._ensure_ids(db,"permissions","code",refs)
                elif isinstance(value,str): values[key]=value.strip()
            manager_id=fields.get("manager_employee_id")
            parent_id=fields.get("parent_employee_id")
            if "manager_employee_id" in fields or "parent_employee_id" in fields or "department_id" in fields:
                rel=db.execute("SELECT manager_employee_id,parent_employee_id FROM organization_relationships WHERE employee_id=?",(employee_id,)).fetchone()
                manager_id=manager_id if "manager_employee_id" in fields else (rel["manager_employee_id"] if rel else None)
                parent_id=parent_id if "parent_employee_id" in fields else (rel["parent_employee_id"] if rel else None)
                department_id=values.get("department_id",current["department_id"])
                self._validate_relationships(db,employee_id,manager_id or None,parent_id or None,department_id)
                db.execute("INSERT INTO organization_relationships(employee_id,manager_employee_id,parent_employee_id,updated_at) VALUES (?,?,?,?) ON CONFLICT(employee_id) DO UPDATE SET manager_employee_id=excluded.manager_employee_id,parent_employee_id=excluded.parent_employee_id,updated_at=excluded.updated_at",(employee_id,manager_id or None,parent_id or None,now))
            if "name" in values and not values["name"]: raise ValueError("required_field")
            if values:
                values["updated_at"]=now
                db.execute("UPDATE ai_employees SET "+",".join(f"{key}=?" for key in values)+" WHERE id=?",(*values.values(),employee_id))
            if "tools" in fields or "knowledge_source_ids" in fields or "modules" in fields:
                old_tools=[r[0] for r in db.execute("SELECT tool_id FROM employee_tools WHERE employee_id=?",(employee_id,))] if "tools" not in fields else _json_list(fields["tools"])
                old_knowledge=[r[0] for r in db.execute("SELECT knowledge_source_id FROM employee_knowledge_access WHERE employee_id=?",(employee_id,))] if "knowledge_source_ids" not in fields else _json_list(fields["knowledge_source_ids"])
                old_modules=[r[0] for r in db.execute("SELECT module_id FROM employee_modules WHERE employee_id=?",(employee_id,))] if "modules" not in fields else _json_list(fields["modules"])
                self._replace_employee_links(db,employee_id,old_tools,old_knowledge,old_modules,actor)
            if "permissions" in fields:
                permissions=list(dict.fromkeys(_json_list(fields["permissions"])))
                db.execute("DELETE FROM employee_permissions WHERE employee_id=?",(employee_id,))
                db.executemany("INSERT INTO employee_permissions(employee_id,permission_code,granted_by,created_at) VALUES (?,?,?,?)",[(employee_id,code,actor,now) for code in permissions])
            action=("employee.paused" if fields.get("status")=="PAUSED" else "employee.activated" if fields.get("status")=="ACTIVE" else
                    "employee.manager_changed" if {"manager_employee_id","parent_employee_id"}.intersection(fields) else
                    "employee.permissions_changed" if "permissions" in fields else "employee.updated")
            self._log(db,self.store,actor,action,"ai_employee",employee_id,",".join(sorted(fields)))
        return self.get_employee(employee_id)

    def set_employee_permissions(self, employee_id: str, permissions: list[str], actor: str) -> dict[str, Any] | None:
        codes=list(dict.fromkeys(str(x).strip().upper() for x in permissions if str(x).strip()))
        with self.store.connect() as db:
            if not db.execute("SELECT 1 FROM ai_employees WHERE id=?",(employee_id,)).fetchone(): return None
            self._ensure_ids(db,"permissions","code",codes)
            db.execute("DELETE FROM employee_permissions WHERE employee_id=?",(employee_id,))
            now=utc_now()
            db.executemany("INSERT INTO employee_permissions(employee_id,permission_code,granted_by,created_at) VALUES (?,?,?,?)",[(employee_id,code,actor,now) for code in codes])
            self._log(db,self.store,actor,"employee.permissions_changed","ai_employee",employee_id,",".join(codes))
        return self.get_employee(employee_id)

    def delete_employee(self, employee_id: str, actor: str) -> bool:
        with self.store.connect() as db:
            row=db.execute("SELECT name FROM ai_employees WHERE id=?",(employee_id,)).fetchone()
            if not row: return False
            refs=(
                db.execute("SELECT 1 FROM tasks WHERE assigned_employee_id=? LIMIT 1",(employee_id,)).fetchone(),
                db.execute("SELECT 1 FROM organization_relationships WHERE manager_employee_id=? OR parent_employee_id=? LIMIT 1",(employee_id,employee_id)).fetchone(),
                db.execute("SELECT 1 FROM departments WHERE manager_employee_id=? LIMIT 1",(employee_id,)).fetchone(),
            )
            if any(refs): raise ValueError("employee_has_dependents")
            db.execute("DELETE FROM ai_employees WHERE id=?",(employee_id,))
            self._log(db,self.store,actor,"employee.deleted","ai_employee",employee_id,row["name"])
        return True

    def list_roles(self) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows=db.execute("SELECT * FROM roles ORDER BY is_system DESC,name").fetchall()
            result=[]
            for row in rows:
                item=dict(row); item["is_system"]=bool(item["is_system"])
                item["permissions"]=[r[0] for r in db.execute("SELECT permission_code FROM role_permissions WHERE role_id=? ORDER BY permission_code",(item["id"],))]
                result.append(item)
        return result

    def list_permissions(self) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows=db.execute("SELECT * FROM permissions ORDER BY sensitive,name").fetchall()
        return [{**dict(row),"sensitive":bool(row["sensitive"])} for row in rows]

    def create_role(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        _reject_secret_material(*payload.values())
        role_id=new_id(); now=utc_now(); code=str(payload.get("code","")).strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{2,32}",code): raise ValueError("invalid_role_code")
        permissions=list(dict.fromkeys(str(value).strip().upper() for value in payload.get("permissions",[]) if str(value).strip()))
        with self.store.connect() as db:
            self._ensure_ids(db,"permissions","code",permissions)
            db.execute("INSERT INTO roles(id,code,name,description,is_system,created_at) VALUES (?,?,?,?,0,?)",
                       (role_id,code,payload["name"],payload.get("description",""),now))
            db.executemany("INSERT INTO role_permissions(role_id,permission_code) VALUES (?,?)",[(role_id,value) for value in permissions])
            self._log(db,self.store,actor,"role.created","role",role_id,code)
        return next(item for item in self.list_roles() if item["id"]==role_id)

    def update_role(self, role_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any] | None:
        _reject_secret_material(*payload.values())
        with self.store.connect() as db:
            role=db.execute("SELECT * FROM roles WHERE id=?",(role_id,)).fetchone()
            if not role: return None
            fields={key:value for key,value in payload.items() if key in {"name","description","permissions"}}
            if not fields: raise ValueError("empty_update")
            if "name" in fields:
                fields["name"]=str(fields["name"]).strip()
                if not fields["name"]: raise ValueError("required_field")
            if "description" in fields: fields["description"]=str(fields["description"]).strip()
            if "name" in fields or "description" in fields:
                db.execute("UPDATE roles SET "+",".join(f"{key}=?" for key in fields if key!="permissions")+" WHERE id=?",
                           (*(fields[key] for key in fields if key!="permissions"),role_id))
            if "permissions" in fields:
                permissions=list(dict.fromkeys(str(value).strip().upper() for value in fields["permissions"] if str(value).strip()))
                self._ensure_ids(db,"permissions","code",permissions)
                db.execute("DELETE FROM role_permissions WHERE role_id=?",(role_id,))
                db.executemany("INSERT INTO role_permissions(role_id,permission_code) VALUES (?,?)",[(role_id,value) for value in permissions])
            self._log(db,self.store,actor,"role.updated","role",role_id,",".join(sorted(fields)))
        return next(item for item in self.list_roles() if item["id"]==role_id)

    def delete_role(self, role_id: str, actor: str) -> bool:
        with self.store.connect() as db:
            role=db.execute("SELECT * FROM roles WHERE id=?",(role_id,)).fetchone()
            if not role: return False
            if role["is_system"]: raise ValueError("system_role_protected")
            if db.execute("SELECT 1 FROM ai_employees WHERE role_id=? LIMIT 1",(role_id,)).fetchone(): raise ValueError("role_has_employees")
            db.execute("DELETE FROM roles WHERE id=?",(role_id,))
            self._log(db,self.store,actor,"role.deleted","role",role_id,role["code"])
        return True

    def list_tools(self) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM tools ORDER BY name").fetchall()]

    def create_tool(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        endpoint=str(payload.get("endpoint_ref","")).strip()
        _reject_secret_material(*payload.values())
        if re.search(r"(?:api[_-]?key|token|secret|password)\s*[=:]\s*[^&\s]+",endpoint,re.I) or re.search(r"https?://[^/\s:@]+:[^/\s@]+@",endpoint,re.I):
            raise ValueError("secret_in_tool_reference")
        tool_id=new_id(); now=utc_now(); code=str(payload.get("code") or re.sub(r"[^A-Z0-9_-]","-",payload["name"].upper())[:32]).strip("-").upper()
        if not code: code=f"TOOL-{tool_id[:8].upper()}"
        if not re.fullmatch(r"[A-Z0-9_-]{2,32}",code): raise ValueError("invalid_tool_code")
        with self.store.connect() as db:
            permission=payload.get("required_permission") or None
            if permission and not db.execute("SELECT 1 FROM permissions WHERE code=?",(permission,)).fetchone(): raise ValueError("invalid_permission")
            db.execute("INSERT INTO tools(id,code,name,tool_type,description,endpoint_ref,required_permission,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (tool_id,code,payload["name"],payload["tool_type"],payload.get("description",""),endpoint,permission,payload.get("status","ACTIVE"),now,now))
            self._log(db,self.store,actor,"tool.created","tool",tool_id,payload["name"])
            return dict(db.execute("SELECT * FROM tools WHERE id=?",(tool_id,)).fetchone())

    def list_knowledge_sources(self, *, include_content: bool = False) -> list[dict[str, Any]]:
        columns="*" if include_content else "id,name,source_type,description,source_ref,status,created_at,updated_at"
        with self.store.connect() as db:
            rows=db.execute(f"SELECT {columns} FROM knowledge_sources ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def create_knowledge_source(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        source_id=new_id(); now=utc_now()
        _reject_secret_material(*payload.values())
        with self.store.connect() as db:
            db.execute("INSERT INTO knowledge_sources(id,name,source_type,description,source_ref,content,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (source_id,payload["name"],payload["source_type"],payload.get("description",""),payload.get("source_ref",""),payload.get("content",""),payload.get("status","ACTIVE"),now,now))
            self._log(db,self.store,actor,"knowledge_source.created","knowledge_source",source_id,payload["name"])
        return next(item for item in self.list_knowledge_sources(include_content=False) if item["id"]==source_id)

    def list_workflows(self) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            rows=db.execute("SELECT * FROM workflows ORDER BY updated_at DESC").fetchall()
            result=[]
            for row in rows:
                item=dict(row); item["steps"]=[dict(step) for step in db.execute("SELECT id,name,position,status,config_json FROM workflow_steps WHERE workflow_id=? ORDER BY position",(item["id"],))]
                for step in item["steps"]: step["config"]=_decode_json(step.pop("config_json"),{})
                result.append(item)
        return result

    def authorized_knowledge_context(self, employee_id: str, max_chars: int = 40000) -> list[dict[str, str]]:
        with self.store.connect() as db:
            rows=db.execute("""SELECT k.name,k.description,k.content FROM employee_knowledge_access a
                JOIN knowledge_sources k ON k.id=a.knowledge_source_id
                WHERE a.employee_id=? AND k.status='ACTIVE' ORDER BY k.name""",(employee_id,)).fetchall()
        result=[]; used=0
        for row in rows:
            content=(row["content"] or "").strip()
            if not content: continue
            remaining=max_chars-used
            if remaining<=0: break
            content=content[:remaining]
            result.append({"name":row["name"],"description":row["description"],"content":content})
            used+=len(content)
        return result

    def create_workflow(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        _reject_secret_material(*payload.values())
        workflow_id=new_id(); now=utc_now(); steps=_json_list(payload.get("steps"))
        if not steps: raise ValueError("workflow_steps_required")
        with self.store.connect() as db:
            db.execute("INSERT INTO workflows(id,name,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                       (workflow_id,payload["name"],payload.get("description",""),payload.get("status","DRAFT"),now,now))
            for position,step in enumerate(steps,1):
                name=str(step.get("name","")).strip() if isinstance(step,dict) else str(step).strip()
                if not name: raise ValueError("invalid_workflow_step")
                config=step.get("config",{}) if isinstance(step,dict) else {}
                db.execute("INSERT INTO workflow_steps(id,workflow_id,name,position,status,config_json,created_at) VALUES (?,?,?,?,?,?,?)",
                           (new_id(),workflow_id,name,position,"READY",json.dumps(config,ensure_ascii=False),now))
            self._log(db,self.store,actor,"workflow.created","workflow",workflow_id,payload["name"])
        return next(item for item in self.list_workflows() if item["id"]==workflow_id)

    def create_employee_task(self, employee_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any] | None:
        _reject_secret_material(*payload.values())
        employee=self.get_employee(employee_id)
        if not employee: return None
        if employee["status"]!="ACTIVE": raise ValueError("employee_not_active")
        if "CREATE_TASK" not in employee["permissions"]: raise ValueError("employee_cannot_create_task")
        if payload.get("project_id"):
            with self.store.connect() as db:
                if not db.execute("SELECT 1 FROM projects WHERE id=?",(payload["project_id"],)).fetchone(): raise ValueError("invalid_project")
        task=self.store.create_task({
            "title":payload["title"],"description":payload.get("description",""),"owner":actor,
            "assigned_employee":employee["name"],"department":employee.get("department_name") or "",
            "priority":payload.get("priority","NORMAL"),"status":"TODO",
            "assigned_employee_id":employee_id,"project_id":payload.get("project_id") or None,
            "deadline":payload.get("deadline") or None,"approval_required":bool(payload.get("approval_required")),
        },actor)
        task["approval_required"]=bool(task.get("approval_required"))
        return task

    def employee_profile(self, employee_id: str) -> dict[str, Any] | None:
        employee=self.get_employee(employee_id)
        if not employee: return None
        with self.store.connect() as db:
            tasks=[dict(row) for row in db.execute("SELECT * FROM tasks WHERE assigned_employee_id=? OR (assigned_employee_id IS NULL AND assigned_employee=?) ORDER BY created_at DESC LIMIT 100",(employee_id,employee["name"]))]
            activity=[dict(row) for row in db.execute("""SELECT * FROM activity_logs
                WHERE object_id=? OR object_id IN (SELECT id FROM tasks WHERE assigned_employee_id=? OR (assigned_employee_id IS NULL AND assigned_employee=?))
                ORDER BY timestamp DESC LIMIT 100""",(employee_id,employee_id,employee["name"])).fetchall()]
            # Knowledge content is deliberately excluded from profile responses.
        return {"employee":employee,"tasks":tasks,"activity":activity}

    def company_structure(self) -> dict[str, Any]:
        departments=self.list_departments(); employees=self.list_employees()
        by_id={row["id"]:row for row in employees}; children: dict[str|None,list[dict[str,Any]]]={}
        for employee in employees:
            parent_id=employee.get("manager_employee_id") or employee.get("parent_employee_id")
            children.setdefault(parent_id,[]).append(employee)
        def node(employee: dict[str,Any], seen: set[str]) -> dict[str,Any]:
            if employee["id"] in seen: return {"id":employee["id"],"name":employee["name"],"type":employee["employee_type"],"status":employee["status"],"children":[]}
            next_seen=set(seen); next_seen.add(employee["id"])
            return {"id":employee["id"],"name":employee["name"],"type":employee["employee_type"],"role":employee["role"],"status":employee["status"],"employee_code":employee["employee_code"],"children":[node(child,next_seen) for child in children.get(employee["id"],[]) if child.get("department_id")==employee.get("department_id")]}
        department_nodes=[]
        for department in departments:
            items=[employee for employee in employees if employee.get("department_id")==department["id"]]
            roots=[employee for employee in items if not (employee.get("manager_employee_id") or employee.get("parent_employee_id")) or (employee.get("manager_employee_id") or employee.get("parent_employee_id")) not in by_id]
            department_nodes.append({"id":department["id"],"name":department["name"],"code":department["code"],"status":department["status"],"manager_employee_id":department.get("manager_employee_id"),"manager_name":department.get("manager_name"),"employees":[node(employee,set()) for employee in roots]})
        return {"owner":{"name":"المالك","type":"OWNER"},"departments":department_nodes}

    def summary(self) -> dict[str, int]:
        with self.store.connect() as db:
            return {
                "total_departments":db.execute("SELECT COUNT(*) FROM departments").fetchone()[0],
                "active_departments":db.execute("SELECT COUNT(*) FROM departments WHERE status='ACTIVE'").fetchone()[0],
                "total_managers":db.execute("SELECT COUNT(*) FROM ai_employees WHERE employee_type='MANAGER'").fetchone()[0],
                "total_ai_employees":db.execute("SELECT COUNT(*) FROM ai_employees WHERE employee_type='EMPLOYEE'").fetchone()[0],
                "active_employees":db.execute("SELECT COUNT(*) FROM ai_employees WHERE employee_type IN ('MANAGER','EMPLOYEE') AND lifecycle_status='ACTIVE'").fetchone()[0],
                "paused_employees":db.execute("SELECT COUNT(*) FROM ai_employees WHERE lifecycle_status='PAUSED'").fetchone()[0],
                "total_workers":db.execute("SELECT COUNT(*) FROM ai_employees WHERE employee_type='WORKER'").fetchone()[0],
                "active_workflows":db.execute("SELECT COUNT(*) FROM workflows WHERE status='ACTIVE'").fetchone()[0],
                "registered_tools":db.execute("SELECT COUNT(*) FROM tools").fetchone()[0],
                "knowledge_sources":db.execute("SELECT COUNT(*) FROM knowledge_sources").fetchone()[0],
            }
