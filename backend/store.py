"""SQLite persistence for the AI Media OS control center."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TASK_STATUSES = {"TODO", "IN_PROGRESS", "WAITING_APPROVAL", "COMPLETED", "CANCELLED", "FAILED"}
TASK_PRIORITIES = {"LOW", "NORMAL", "HIGH", "URGENT"}
APPROVAL_DECISIONS = {"APPROVE", "REJECT", "REQUEST_CHANGES"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id() -> str:
    return uuid.uuid4().hex


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL,
                    assigned_employee TEXT NOT NULL DEFAULT '',
                    department TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL CHECK(priority IN ('LOW','NORMAL','HIGH','URGENT')),
                    status TEXT NOT NULL CHECK(status IN ('TODO','IN_PROGRESS','WAITING_APPROVAL','COMPLETED','CANCELLED','FAILED')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS tasks_status_idx ON tasks(status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    submitted_by TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('WAITING_APPROVAL','APPROVED','REJECTED','CHANGES_REQUESTED')),
                    decision_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS approvals_status_idx ON approvals(status, created_at DESC);

                CREATE TABLE IF NOT EXISTS approval_decisions (
                    id TEXT PRIMARY KEY,
                    approval_id TEXT NOT NULL REFERENCES approvals(id),
                    decision TEXT NOT NULL CHECK(decision IN ('APPROVE','REJECT','REQUEST_CHANGES')),
                    actor TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS approval_decisions_item_idx ON approval_decisions(approval_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS activity_logs (
                    id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    module TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS activity_timestamp_idx ON activity_logs(timestamp DESC);

                CREATE TABLE IF NOT EXISTS departments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ai_employees (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    department_id TEXT REFERENCES departments(id),
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')),
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ai_employees_status_idx ON ai_employees(status, created_at DESC);

                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','INACTIVE')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','ON_HOLD','COMPLETED')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

    def ping(self) -> bool:
        with self.connect() as db:
            return db.execute("SELECT 1").fetchone()[0] == 1

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def log_activity(self, db: sqlite3.Connection, *, actor: str, action: str, module: str,
                     object_type: str, object_id: str, status: str = "SUCCESS",
                     result: str = "", error: str = "") -> dict[str, Any]:
        record = {
            "id": new_id(), "actor": actor, "action": action, "module": module,
            "object_type": object_type, "object_id": object_id, "timestamp": utc_now(),
            "status": status, "result": result, "error": error,
        }
        db.execute("""INSERT INTO activity_logs
            (id,actor,action,module,object_type,object_id,timestamp,status,result,error)
            VALUES (:id,:actor,:action,:module,:object_type,:object_id,:timestamp,:status,:result,:error)""", record)
        return record

    def create_task(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utc_now()
        item = {
            "id": new_id(), "title": payload["title"], "description": payload.get("description", ""),
            "owner": payload.get("owner", actor), "assigned_employee": payload.get("assigned_employee", ""),
            "department": payload.get("department", ""), "priority": payload.get("priority", "NORMAL"),
            "status": payload.get("status", "TODO"), "created_at": now, "updated_at": now,
            "assigned_employee_id": payload.get("assigned_employee_id") or None,
            "project_id": payload.get("project_id") or None,
            "deadline": payload.get("deadline") or None,
            "approval_required": 1 if payload.get("approval_required") else 0,
        }
        with self.connect() as db:
            db.execute("""INSERT INTO tasks
                (id,title,description,owner,assigned_employee,department,priority,status,created_at,updated_at,
                 assigned_employee_id,project_id,deadline,approval_required)
                VALUES (:id,:title,:description,:owner,:assigned_employee,:department,:priority,:status,:created_at,:updated_at,
                        :assigned_employee_id,:project_id,:deadline,:approval_required)""", item)
            self.log_activity(db, actor=actor, action="task.created", module="tasks", object_type="task",
                              object_id=item["id"], result=json.dumps({"title": item["title"]}, ensure_ascii=False))
        return item

    def list_tasks(self, *, status: str = "", search: str = "", limit: int = 200) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(title LIKE ? OR description LIKE ? OR owner LIKE ? OR assigned_employee LIKE ? OR department LIKE ?)")
            params.extend([f"%{search}%"] * 5)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM tasks{where} ORDER BY created_at DESC LIMIT ?", (*params, limit)).fetchall()
        return [dict(row) for row in rows]

    def count_tasks(self) -> dict[str, int]:
        counts = {status: 0 for status in sorted(TASK_STATUSES)}
        with self.connect() as db:
            rows = db.execute("SELECT status, COUNT(*) AS amount FROM tasks GROUP BY status").fetchall()
        counts.update({row["status"]: row["amount"] for row in rows})
        counts["TOTAL"] = sum(counts.values())
        return counts

    def update_task_status(self, task_id: str, status: str, actor: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                return None
            previous = row["status"]
            now = utc_now()
            db.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, now, task_id))
            self.log_activity(db, actor=actor, action="task.status_changed", module="tasks", object_type="task",
                              object_id=task_id, result=json.dumps({"from": previous, "to": status}))
            updated = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(updated)

    def create_approval(self, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        now = utc_now()
        item = {"id": new_id(), "title": payload["title"], "description": payload.get("description", ""),
                "submitted_by": payload.get("submitted_by", actor), "status": "WAITING_APPROVAL",
                "decision_note": "", "created_at": now, "updated_at": now}
        with self.connect() as db:
            db.execute("""INSERT INTO approvals
                (id,title,description,submitted_by,status,decision_note,created_at,updated_at)
                VALUES (:id,:title,:description,:submitted_by,:status,:decision_note,:created_at,:updated_at)""", item)
            self.log_activity(db, actor=actor, action="approval.created", module="approvals", object_type="approval",
                              object_id=item["id"], result=json.dumps({"title": item["title"]}, ensure_ascii=False))
        return item

    def list_approvals(self, *, status: str = "", search: str = "", limit: int = 200) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(title LIKE ? OR description LIKE ? OR submitted_by LIKE ?)")
            params.extend([f"%{search}%"] * 3)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM approvals{where} ORDER BY created_at DESC LIMIT ?", (*params, limit)).fetchall()
        return [dict(row) for row in rows]

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return self._dict(row)

    def count_pending_approvals(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM approvals WHERE status='WAITING_APPROVAL'").fetchone()[0]

    def list_approval_decisions(self, approval_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM approval_decisions WHERE approval_id=? ORDER BY created_at DESC", (approval_id,)).fetchall()
        return [dict(row) for row in rows]

    def decide_approval(self, approval_id: str, decision: str, note: str, actor: str) -> dict[str, Any] | None:
        status_for = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_CHANGES": "CHANGES_REQUESTED"}
        now = utc_now()
        with self.connect() as db:
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                return None
            if row["status"] != "WAITING_APPROVAL":
                raise ValueError("approval_already_decided")
            db.execute("INSERT INTO approval_decisions (id,approval_id,decision,actor,note,created_at) VALUES (?,?,?,?,?,?)",
                       (new_id(), approval_id, decision, actor, note, now))
            db.execute("UPDATE approvals SET status=?, decision_note=?, updated_at=? WHERE id=?",
                       (status_for[decision], note, now, approval_id))
            self.log_activity(db, actor=actor, action=f"approval.{decision.lower()}", module="approvals",
                              object_type="approval", object_id=approval_id,
                              result=json.dumps({"decision": decision, "note": note}, ensure_ascii=False))
            updated = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return dict(updated)

    def list_activity(self, *, search: str = "", status: str = "", limit: int = 200) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(actor LIKE ? OR action LIKE ? OR module LIKE ? OR object_type LIKE ? OR object_id LIKE ? OR result LIKE ? OR error LIKE ?)")
            params.extend([f"%{search}%"] * 7)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM activity_logs{where} ORDER BY timestamp DESC LIMIT ?", (*params, limit)).fetchall()
        return [dict(row) for row in rows]

    def activity_count(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT COUNT(*) FROM activity_logs").fetchone()[0]

    def list_departments(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def list_ai_employees(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("""SELECT e.*, d.name AS department
                FROM ai_employees e LEFT JOIN departments d ON d.id=e.department_id
                ORDER BY e.name""").fetchall()
        return [dict(row) for row in rows]

    def list_characters(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM characters ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def count_active(self, table: str) -> int:
        if table not in {"departments", "ai_employees", "characters", "projects"}:
            raise ValueError("invalid_entity_table")
        with self.connect() as db:
            return db.execute(f"SELECT COUNT(*) FROM {table} WHERE status='ACTIVE'").fetchone()[0]

    def seed_initial_data(self) -> dict[str, Any]:
        """Insert stable starter rows once; never overwrite owner-created records."""
        now = utc_now()
        inserted: dict[str, bool] = {}
        audit: list[tuple[str, str, str, str]] = []
        with self.connect() as db:
            department_id = "seed-dept-content-production"
            employee_id = "seed-ai-employee-content-editor"
            character_id = "seed-character-layan"
            project_id = "seed-project-content-pilot"
            task_id = "seed-task-first-content-brief"
            approval_id = "seed-approval-first-content-review"

            cursor = db.execute("""INSERT OR IGNORE INTO departments
                (id,name,description,status,created_at) VALUES (?,?,?,?,?)""",
                (department_id, "إنتاج المحتوى", "تخطيط وإعداد أصول المحتوى الرقمي.", "ACTIVE", now))
            inserted["department"] = cursor.rowcount == 1
            if inserted["department"]:
                audit.append(("company-builder", "department", department_id, "إنتاج المحتوى"))
            department_row = db.execute("SELECT id FROM departments WHERE id=?", (department_id,)).fetchone()
            if department_row is None:
                department_row = db.execute("SELECT id FROM departments WHERE name=?", ("إنتاج المحتوى",)).fetchone()
            employee_department_id = department_row["id"]

            cursor = db.execute("""INSERT OR IGNORE INTO ai_employees
                (id,name,role,description,department_id,status,created_at) VALUES (?,?,?,?,?,?,?)""",
                (employee_id, "مساعد المحتوى", "محرر ومخطط محتوى",
                 "موظف تأسيسي لإعداد موجزات المحتوى ومتابعة مراجعتها.", employee_department_id, "ACTIVE", now))
            inserted["ai_employee"] = cursor.rowcount == 1
            if inserted["ai_employee"]:
                audit.append(("ai-team", "ai_employee", employee_id, "مساعد المحتوى"))

            cursor = db.execute("""INSERT OR IGNORE INTO characters
                (id,name,role,description,status,created_at) VALUES (?,?,?,?,?,?)""",
                (character_id, "ليان", "المقدمة الرقمية",
                 "شخصية عربية ودودة تمثل نموذجاً أولياً لمحتوى الشركة.", "ACTIVE", now))
            inserted["character"] = cursor.rowcount == 1
            if inserted["character"]:
                audit.append(("characters", "character", character_id, "ليان"))

            cursor = db.execute("""INSERT OR IGNORE INTO projects
                (id,name,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?)""",
                (project_id, "إطلاق قناة المحتوى التجريبية",
                 "إعداد ومراجعة الحزمة الأولى من محتوى AI Media OS.", "ACTIVE", now, now))
            inserted["project"] = cursor.rowcount == 1
            if inserted["project"]:
                audit.append(("projects", "project", project_id, "إطلاق قناة المحتوى التجريبية"))

            cursor = db.execute("""INSERT OR IGNORE INTO tasks
                (id,title,description,owner,assigned_employee,department,priority,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (task_id, "إعداد موجز الفيديو التجريبي",
                 "صياغة موجز أول فيديو تعريفي وربطه بهوية الشخصية الرقمية.", "المالك",
                 "مساعد المحتوى", "إنتاج المحتوى", "HIGH", "IN_PROGRESS", now, now))
            inserted["task"] = cursor.rowcount == 1
            if inserted["task"]:
                audit.append(("tasks", "task", task_id, "إعداد موجز الفيديو التجريبي"))

            cursor = db.execute("""INSERT OR IGNORE INTO approvals
                (id,title,description,submitted_by,status,decision_note,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (approval_id, "اعتماد الهوية التحريرية للحزمة الأولى",
                 "مراجعة نبرة المحتوى وموجز الفيديو قبل بدء الإنتاج.",
                 "مساعد المحتوى", "WAITING_APPROVAL", "", now, now))
            inserted["approval"] = cursor.rowcount == 1
            if inserted["approval"]:
                audit.append(("approvals", "approval", approval_id, "اعتماد الهوية التحريرية للحزمة الأولى"))

            for module, object_type, object_id, name in audit:
                self.log_activity(db, actor="system", action="seed.created", module=module,
                                  object_type=object_type, object_id=object_id, result=name)

            counts = {
                table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("departments", "ai_employees", "characters", "projects", "tasks", "approvals")
            }
        return {"inserted": inserted, "counts": counts}

    def dashboard(self, health: dict[str, Any]) -> dict[str, Any]:
        task_counts = self.count_tasks()
        approvals = self.count_pending_approvals()
        activities = self.list_activity(limit=8)
        recent_tasks = self.list_tasks(limit=8)
        pending_approvals = self.list_approvals(status="WAITING_APPROVAL", limit=8)
        return {
            "checked_at": utc_now(),
            "company": {
                "active_departments": {"status": "ONLINE", "value": self.count_active("departments")},
                "active_ai_employees": {"status": "ONLINE", "value": self.count_active("ai_employees")},
                "active_characters": {"status": "ONLINE", "value": self.count_active("characters")},
                "active_projects": {"status": "ONLINE", "value": self.count_active("projects")},
                "running_tasks": {"status": "ONLINE", "value": task_counts["IN_PROGRESS"]},
                "waiting_approvals": {"status": "ONLINE", "value": approvals},
                "production_jobs": {"status": "NOT_CONFIGURED", "value": None},
                "published_content": {"status": "NOT_CONFIGURED", "value": None},
                "task_counts": task_counts,
                "activity_count": self.activity_count(),
            },
            "health": health,
            "recent_tasks": recent_tasks,
            "pending_approvals": pending_approvals,
            "recent_activity": activities,
        }
