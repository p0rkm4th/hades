"""Small durable Task store for episodic HADES coordination.

This is deliberately a store and transition boundary, not a scheduler,
workflow engine, model loop, or domain database.  Every mutating transition is
transactional, optimistic-concurrency checked, and recorded in bounded audit
history.  External execution is represented and reconciled here; it is never
performed by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping


SCHEMA_VERSION = 1
MAX_JSON_BYTES = 256 * 1024


class TaskError(ValueError):
    """Expected task contract error."""


class ConcurrencyError(TaskError):
    """The caller acted on a stale task revision."""


class AuthorityError(TaskError):
    """Current action-time authority is insufficient."""


class ApprovalError(TaskError):
    """Approval is absent, stale, or bound to another consequence."""


class ExecutionError(TaskError):
    """Execution state or callback is invalid."""


class TaskStatus(StrEnum):
    PROPOSED = "PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


TERMINAL = frozenset({TaskStatus.COMPLETED, TaskStatus.CANCELLED})
_NOW = lambda: int(time.time())
AuthorityChecker = Callable[[str, Mapping[str, Any], str, Mapping[str, Any]], bool | str]


def _json(value: Any, label: str) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise TaskError(f"{label} must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise TaskError(f"{label} exceeds the bounded size")
    return encoded


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _approval_digest(task_id: str, revision: int, actor: str, action: str,
                     resource: Mapping[str, Any], parameters: Mapping[str, Any]) -> str:
    payload = {
        "task_id": task_id,
        "task_revision": revision,
        "actor_subject_id": actor,
        "action": action,
        "resource": dict(resource),
        "parameters": dict(parameters),
    }
    return hashlib.sha256(_json(payload, "approval").encode("utf-8")).hexdigest()


class TaskStore:
    """SQLite-backed coordination state with explicit transition methods."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        if self.path.name == ":memory:":
            raise TaskError("Task storage must survive the process")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self.path.chmod(0o600)

    def _connect(self, *, immediate: bool = False) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE" if immediate else None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _initialize(self) -> None:
        with self._connect(immediate=True) as db:
            db.execute("CREATE TABLE IF NOT EXISTS task_schema (version INTEGER NOT NULL)")
            row = db.execute("SELECT version FROM task_schema LIMIT 1").fetchone()
            if row is None:
                db.execute("INSERT INTO task_schema(version) VALUES (?)", (SCHEMA_VERSION,))
            elif int(row[0]) != SCHEMA_VERSION:
                raise TaskError(f"unsupported task schema version: {row[0]}")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    actor_subject_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    task_revision INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    resource_scope TEXT NOT NULL,
                    required_authority TEXT NOT NULL,
                    bounded_plan TEXT NOT NULL,
                    current_step TEXT,
                    dependencies TEXT NOT NULL,
                    waiting_reason TEXT,
                    blocked_reason TEXT,
                    next_eligible_action TEXT,
                    execution_target TEXT,
                    artifacts TEXT NOT NULL,
                    canonical_references TEXT NOT NULL,
                    approval_state TEXT NOT NULL,
                    retry_semantics TEXT NOT NULL,
                    result TEXT,
                    UNIQUE(task_id, actor_subject_id)
                );
                CREATE TABLE IF NOT EXISTS task_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    task_revision INTEGER NOT NULL,
                    actor_subject_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_approvals (
                    approval_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    actor_subject_id TEXT NOT NULL,
                    task_revision INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    parameters TEXT NOT NULL,
                    digest TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    consumed_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS task_executions (
                    execution_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                    task_revision INTEGER NOT NULL,
                    step_id TEXT NOT NULL,
                    executor TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    requested_action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    status TEXT NOT NULL,
                    canonical_refs TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    finished_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS task_actor_idx ON tasks(actor_subject_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS task_event_idx ON task_events(task_id, event_id);
                CREATE INDEX IF NOT EXISTS task_execution_idx ON task_executions(task_id, started_at);
            """)

    @staticmethod
    def _task(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in (
            "resource_scope", "required_authority", "bounded_plan", "dependencies",
            "artifacts", "canonical_references", "approval_state", "retry_semantics",
            "result",
        ):
            if key in result:
                result[key] = _loads(result[key], {} if key != "result" else None)
        return result

    def _row(self, db: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise TaskError("task not found")
        return row

    def get(self, task_id: str, actor_subject_id: str | None = None) -> dict[str, Any]:
        with self._connect() as db:
            row = self._row(db, task_id)
        task = self._task(row)
        if actor_subject_id is not None and task["actor_subject_id"] != actor_subject_id:
            raise TaskError("task is not visible to this actor")
        return task

    def list_for_actor(self, actor_subject_id: str, *, include_shared: bool = False) -> list[dict[str, Any]]:
        # Sharing is intentionally not inferred here.  A future explicit share
        # policy may add rows, but private task visibility never broadens by text.
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM tasks WHERE actor_subject_id=? ORDER BY updated_at DESC",
                (actor_subject_id,),
            ).fetchall()
        return [self._task(row) for row in rows]

    def create(
        self,
        *,
        task_id: str,
        actor_subject_id: str,
        goal: str,
        resource_scope: Mapping[str, Any] | None = None,
        required_authority: Mapping[str, Any] | None = None,
        bounded_plan: list[Mapping[str, Any]] | None = None,
        current_step: str | None = None,
        dependencies: list[Mapping[str, Any]] | None = None,
        status: TaskStatus = TaskStatus.PROPOSED,
    ) -> dict[str, Any]:
        if not task_id or not actor_subject_id or not goal.strip():
            raise TaskError("task id, stable actor subject, and goal are required")
        now = _NOW()
        defaults = (resource_scope or {}, required_authority or {}, bounded_plan or [], dependencies or [])
        encoded = [_json(value, label) for value, label in zip(defaults, ("resource_scope", "required_authority", "bounded_plan", "dependencies"), strict=True)]
        with self._connect(immediate=True) as db:
            try:
                db.execute(
                    """INSERT INTO tasks(task_id,actor_subject_id,goal,created_at,updated_at,task_revision,status,
                    resource_scope,required_authority,bounded_plan,current_step,dependencies,waiting_reason,
                    blocked_reason,next_eligible_action,execution_target,artifacts,canonical_references,
                    approval_state,retry_semantics,result) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (task_id, actor_subject_id, goal.strip(), now, now, 1, status.value, encoded[0], encoded[1],
                     encoded[2], current_step, encoded[3], None, None, None, None, "{}", "{}", "{}",
                     _json({"max_attempts": 1, "unknown_requires_reconcile": True}, "retry_semantics"), None),
                )
            except sqlite3.IntegrityError as exc:
                raise TaskError("task id already exists") from exc
            self._event(db, task_id, 1, actor_subject_id, "CREATED", {"goal": goal.strip()})
        return self.get(task_id, actor_subject_id)

    def _event(self, db: sqlite3.Connection, task_id: str, revision: int, actor: str,
               event_type: str, detail: Mapping[str, Any]) -> None:
        db.execute(
            "INSERT INTO task_events(task_id,task_revision,actor_subject_id,event_type,detail,created_at) VALUES(?,?,?,?,?,?)",
            (task_id, revision, actor, event_type, _json(detail, "event detail"), _NOW()),
        )

    def events(self, task_id: str, actor_subject_id: str | None = None) -> list[dict[str, Any]]:
        task = self.get(task_id, actor_subject_id)
        with self._connect() as db:
            rows = db.execute(
                "SELECT event_id,task_revision,actor_subject_id,event_type,detail,created_at FROM task_events WHERE task_id=? ORDER BY event_id",
                (task["task_id"],),
            ).fetchall()
        return [{**dict(row), "detail": _loads(row["detail"], {})} for row in rows]

    def _transition(self, task_id: str, actor: str, expected_revision: int, status: TaskStatus,
                    *, event_type: str, fields: Mapping[str, Any] | None = None,
                    detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
        fields = dict(fields or {})
        allowed = {
            "goal", "status", "current_step", "waiting_reason", "blocked_reason", "next_eligible_action",
            "execution_target", "artifacts", "canonical_references", "approval_state",
            "result", "bounded_plan", "dependencies", "required_authority", "retry_semantics",
        }
        if set(fields) - allowed:
            raise TaskError("unsupported task transition field")
        now = _NOW()
        assignments = ["task_revision=task_revision+1", "updated_at=?"]
        values: list[Any] = [now]
        for key, value in fields.items():
            assignments.append(f"{key}=?")
            values.append(None if value is None else _json(value, key) if key in {
                "artifacts", "canonical_references", "approval_state", "result", "bounded_plan",
                "dependencies", "required_authority", "retry_semantics", "execution_target"
            } else value)
        assignments.append("status=?")
        values.append(status.value)
        values.extend([task_id, actor, expected_revision])
        with self._connect(immediate=True) as db:
            updated = db.execute(
                f"UPDATE tasks SET {', '.join(assignments)} WHERE task_id=? AND actor_subject_id=? AND task_revision=?",
                values,
            ).rowcount
            if updated != 1:
                raise ConcurrencyError("task revision is stale or task is not owned by this actor")
            revision = expected_revision + 1
            self._event(db, task_id, revision, actor, event_type, detail or {"status": status.value})
        return self.get(task_id, actor)

    def transition(self, task_id: str, actor: str, expected_revision: int, status: TaskStatus,
                   *, fields: Mapping[str, Any] | None = None, detail: Mapping[str, Any] | None = None,
                   event_type: str = "TRANSITION") -> dict[str, Any]:
        return self._transition(task_id, actor, expected_revision, status, event_type=event_type, fields=fields, detail=detail)

    def request_approval(self, task_id: str, actor: str, expected_revision: int, *, action: str,
                         resource: Mapping[str, Any], parameters: Mapping[str, Any]) -> dict[str, Any]:
        task = self.get(task_id, actor)
        if task["task_revision"] != expected_revision:
            raise ConcurrencyError("task revision is stale")
        approval = {
            "action": action,
            "resource": dict(resource),
            "parameters": dict(parameters),
            "task_revision": expected_revision + 1,
            "digest": _approval_digest(task_id, expected_revision + 1, actor, action, resource, parameters),
            "status": "PENDING",
        }
        result = self._transition(
            task_id, actor, expected_revision, TaskStatus.AWAITING_APPROVAL,
            fields={"approval_state": approval, "next_eligible_action": "approval"},
            event_type="APPROVAL_REQUESTED", detail=approval,
        )
        return result

    def approve(self, task_id: str, actor: str, expected_revision: int, *, action: str,
                resource: Mapping[str, Any], parameters: Mapping[str, Any],
                authority_checker: AuthorityChecker | None = None) -> dict[str, Any]:
        task = self.get(task_id, actor)
        approval = task["approval_state"]
        if task["task_revision"] != expected_revision or task["status"] != TaskStatus.AWAITING_APPROVAL.value:
            raise ApprovalError("approval is stale or task is not awaiting approval")
        if authority_checker is not None:
            allowed = authority_checker(actor, resource, action, parameters)
            if allowed is not True and allowed != "ALLOWED":
                raise AuthorityError(str(allowed) if isinstance(allowed, str) else "current authority denied")
        expected = _approval_digest(task_id, expected_revision, actor, action, resource, parameters)
        if approval.get("action") != action or approval.get("resource") != dict(resource) or approval.get("parameters") != dict(parameters):
            raise ApprovalError("approval does not match the requested consequence")
        if approval.get("digest") != expected:
            raise ApprovalError("approval binding is invalid")
        approval = {**approval, "status": "APPROVED", "approved_by": actor, "approved_at": _NOW()}
        return self._transition(
            task_id, actor, expected_revision, TaskStatus.READY,
            fields={"approval_state": approval, "next_eligible_action": "execute"},
            event_type="APPROVED", detail={"action": action, "resource": dict(resource)},
        )

    def replan(self, task_id: str, actor: str, expected_revision: int, *, goal: str | None = None,
               bounded_plan: list[Mapping[str, Any]] | None = None, current_step: str | None = None,
               detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
        task = self.get(task_id, actor)
        if task["task_revision"] != expected_revision:
            raise ConcurrencyError("task revision is stale")
        fields: dict[str, Any] = {"approval_state": {}, "next_eligible_action": "review", "execution_target": {}}
        if bounded_plan is not None:
            fields["bounded_plan"] = bounded_plan
        if current_step is not None:
            fields["current_step"] = current_step
        if goal is not None:
            fields["goal"] = goal.strip()
            fields["result"] = {
                "goal_changed": True,
                "previous_goal": task["goal"],
                "new_goal": goal,
                **({"task_command_digest": detail["task_command_digest"]} if detail and detail.get("task_command_digest") else {}),
            }
        result = self._transition(task_id, actor, expected_revision, TaskStatus.READY, fields=fields,
                                  event_type="REPLANNED", detail=detail or {"approval_invalidated": True})
        return self.get(task_id, actor)

    def cancel(self, task_id: str, actor: str, expected_revision: int, *, reason: str = "user cancelled") -> dict[str, Any]:
        task = self.get(task_id, actor)
        if task["status"] in {status.value for status in TERMINAL}:
            return task
        return self._transition(task_id, actor, expected_revision, TaskStatus.CANCELLED,
                                fields={"next_eligible_action": None, "blocked_reason": reason},
                                event_type="CANCELLED", detail={"reason": reason})

    def begin_execution(self, task_id: str, actor: str, expected_revision: int, *, execution_id: str,
                        step_id: str, executor: str, idempotency_key: str, action: str,
                        resource: Mapping[str, Any], authority_checker: AuthorityChecker | None = None) -> dict[str, Any]:
        task = self.get(task_id, actor)
        if task["task_revision"] != expected_revision or task["status"] not in {TaskStatus.READY.value, TaskStatus.RUNNING.value}:
            raise ExecutionError("task is not eligible for execution")
        if authority_checker is not None:
            allowed = authority_checker(actor, resource, action, {})
            if allowed is not True and allowed != "ALLOWED":
                raise AuthorityError(str(allowed) if isinstance(allowed, str) else "current authority denied")
        now = _NOW()
        with self._connect(immediate=True) as db:
            existing = db.execute("SELECT * FROM task_executions WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                if existing["task_id"] != task_id:
                    raise ExecutionError("idempotency key belongs to another task")
                return self.get(task_id, actor)
            db.execute("""INSERT INTO task_executions(execution_id,task_id,task_revision,step_id,executor,
                idempotency_key,requested_action,resource,status,canonical_refs,metadata,started_at,finished_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (execution_id, task_id, expected_revision, step_id, executor, idempotency_key, action,
                        _json(resource, "resource"), "STARTED", "{}", "{}", now, None))
        return self._transition(task_id, actor, expected_revision, TaskStatus.RUNNING,
                                fields={"execution_target": {"executor": executor, "execution_id": execution_id, "step_id": step_id}},
                                event_type="EXECUTION_STARTED", detail={"execution_id": execution_id, "idempotency_key": idempotency_key})

    def record_execution(self, task_id: str, actor: str, expected_revision: int, *, execution_id: str,
                         status: str, canonical_refs: Mapping[str, Any] | None = None,
                         metadata: Mapping[str, Any] | None = None, result: Mapping[str, Any] | None = None,
                         detail: Mapping[str, Any] | None = None,
                         success_status: TaskStatus = TaskStatus.COMPLETED,
                         next_eligible_action: str | None = None) -> dict[str, Any]:
        if status not in {"SUCCEEDED", "FAILED", "OUTCOME_UNKNOWN", "BLOCKED", "UNAVAILABLE"}:
            raise ExecutionError("invalid executor result")
        task = self.get(task_id, actor)
        with self._connect(immediate=True) as db:
            row = db.execute("SELECT * FROM task_executions WHERE execution_id=? AND task_id=?", (execution_id, task_id)).fetchone()
            if row is None:
                raise ExecutionError("execution is not registered")
            if row["status"] == status:
                return task
            db.execute("UPDATE task_executions SET status=?,canonical_refs=?,metadata=?,finished_at=? WHERE execution_id=?",
                       (status, _json(canonical_refs or {}, "canonical_refs"), _json(metadata or {}, "metadata"), _NOW(), execution_id))
        if success_status not in {TaskStatus.COMPLETED, TaskStatus.WAITING, TaskStatus.READY}:
            raise ExecutionError("invalid successful continuation status")
        next_status = {
            "SUCCEEDED": success_status,
            "FAILED": TaskStatus.FAILED,
            "OUTCOME_UNKNOWN": TaskStatus.OUTCOME_UNKNOWN,
            "BLOCKED": TaskStatus.BLOCKED,
            "UNAVAILABLE": TaskStatus.BLOCKED,
        }[status]
        return self._transition(task_id, actor, task["task_revision"], next_status,
                                fields={"canonical_references": canonical_refs or {}, "result": result or {"execution_id": execution_id, "status": status},
                                        "next_eligible_action": "reconcile" if status == "OUTCOME_UNKNOWN" else next_eligible_action},
                                event_type="EXECUTION_RESULT", detail=detail or {"execution_id": execution_id, "status": status})

    def reconcile_unknown(self, task_id: str, actor: str, expected_revision: int, *, execution_id: str,
                          succeeded: bool, canonical_refs: Mapping[str, Any],
                          detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
        task = self.get(task_id, actor)
        if task["status"] != TaskStatus.OUTCOME_UNKNOWN.value:
            raise ExecutionError("task is not awaiting unknown-outcome reconciliation")
        return self.record_execution(task_id, actor, expected_revision, execution_id=execution_id,
                                     status="SUCCEEDED" if succeeded else "FAILED",
                                     canonical_refs=canonical_refs, metadata={"reconciled": True}, detail=detail)

    def backup(self, destination: str | os.PathLike[str]) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as source, sqlite3.connect(destination) as target:
            source.backup(target)
        destination.chmod(0o600)
        return destination

    @staticmethod
    def restore(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> Path:
        source, destination = Path(source), Path(destination)
        if not source.is_file() or source.is_symlink():
            raise TaskError("restore source must be a regular file")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(source) as db:
            version = db.execute("SELECT version FROM task_schema LIMIT 1").fetchone()
            if not version or int(version[0]) != SCHEMA_VERSION:
                raise TaskError("restore source has unsupported task schema")
            db.execute("PRAGMA integrity_check").fetchone()
        fd, temp_name = tempfile.mkstemp(prefix="task-restore-", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copyfile(source, temp_name)
            os.replace(temp_name, destination)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        destination.chmod(0o600)
        return destination
