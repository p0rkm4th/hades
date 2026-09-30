"""Staged household self-service for the approved read-only catalog.

This module is deliberately separate from the Phase 2 live adapters.  It owns
creator/owner metadata, current-authority checks, simple admission limits, and
staged lifecycle semantics.  It never creates an n8n workflow; a future
promotion adapter must make that an explicit, separately authorized choice.
"""

from __future__ import annotations

import hashlib
import grp
import json
import os
import re
import secrets
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


PHASE3_TEMPLATES = {
    "server-health-watch": "Server Health Watch",
    "low-inventory-summary": "Low Inventory Summary",
    "weekly-household-summary": "Weekly Household Summary",
    "hades-backup-verification": "Backup Verification",
}

RESOURCE_LABELS = {
    "hades-core.health": "Server Health",
    "grocy.household": "Groceries",
    "backup.evidence": "Backup Verification",
}

DEFAULT_QUOTAS = {
    "owner_active": 10,
    "household_active": 5,
    "per_template_resource": 1,
    "min_interval_minutes": 5,
    "max_manual_runs": 2,
}


class Phase3Error(ValueError):
    pass


class Phase3AuthorizationError(Phase3Error):
    pass


class Phase3QuotaError(Phase3Error):
    pass


class Phase3DuplicateError(Phase3Error):
    pass


@dataclass(frozen=True)
class Phase3Authority:
    subject: str
    role: str
    resources: frozenset[str]
    active: bool = True

    @property
    def is_owner(self) -> bool:
        return self.role in {"owner", "admin"}


@dataclass(frozen=True)
class Phase3Quotas:
    owner_active: int = DEFAULT_QUOTAS["owner_active"]
    household_active: int = DEFAULT_QUOTAS["household_active"]
    per_template_resource: int = DEFAULT_QUOTAS["per_template_resource"]
    min_interval_minutes: int = DEFAULT_QUOTAS["min_interval_minutes"]
    max_manual_runs: int = DEFAULT_QUOTAS["max_manual_runs"]


def _now() -> int:
    return int(time.time())


def _valid_subject(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", str(value or "")))


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _resource_allowed(authority: Phase3Authority, resource: str) -> bool:
    if not authority.active:
        return False
    return resource in authority.resources


def _template_resources(template: str, payload: Mapping[str, Any]) -> set[str]:
    if template == "server-health-watch":
        return {f"{payload.get('resource_id', '')}.health"}
    if template == "low-inventory-summary":
        return {"grocy.household"}
    if template == "hades-backup-verification":
        return {"backup.evidence"}
    if template == "weekly-household-summary":
        return set(payload.get("resource_scope", ()))
    return set()


class Phase3Catalog:
    """Authority-aware catalog projection; no unavailable resource is named."""

    def __init__(self, health_resources: Mapping[str, str] | None = None):
        self.health_resources = dict(health_resources or {"hades-core": "HADES Core"})

    def entries(self, authority: Phase3Authority) -> list[dict[str, Any]]:
        if not authority.active:
            return []
        entries: list[dict[str, Any]] = []
        for resource_id, display_name in self.health_resources.items():
            if _resource_allowed(authority, f"{resource_id}.health"):
                entries.append({"template": "server-health-watch", "display_name": f"{display_name} Watch", "resource_id": resource_id, "resource": "Server Health", "interval_minutes": 10})
        if _resource_allowed(authority, "grocy.household"):
            entries.append({"template": "low-inventory-summary", "display_name": "Low Grocery Summary", "resource": "Groceries", "interval_minutes": 10080})
        sections = [resource for resource in RESOURCE_LABELS if _resource_allowed(authority, resource)]
        if sections:
            entries.append({"template": "weekly-household-summary", "display_name": "Weekly Household Summary", "resource_scope": sections, "sections": [RESOURCE_LABELS[item] for item in sections], "interval_minutes": 10080})
        if _resource_allowed(authority, "backup.evidence"):
            entries.append({"template": "hades-backup-verification", "display_name": "Backup Verification", "resource": "Backup Verification", "interval_minutes": 1440})
        return entries

    def require_template(self, authority: Phase3Authority, template: str, payload: Mapping[str, Any]) -> None:
        if template not in PHASE3_TEMPLATES:
            raise Phase3AuthorizationError("that automation template is not approved")
        resources = _template_resources(template, payload)
        if not resources or not resources.issubset(authority.resources) or not authority.active:
            raise Phase3AuthorizationError("current resource authority does not permit that automation")
        if template == "weekly-household-summary" and not resources.issubset(set(RESOURCE_LABELS)):
            raise Phase3AuthorizationError("weekly summary contains an unapproved section")
        if template == "server-health-watch" and payload.get("resource_id") not in self.health_resources:
            raise Phase3AuthorizationError("that server is not an approved health source")


class Phase3Store:
    """SQLite-backed staged metadata, ownership, pending previews, and audit."""

    SHARED_GROUP_ENV = "HADES_EPSILON_PHASE3_STATE_GROUP"
    SHARED_DIRECTORY_MODE = 0o2770
    SHARED_DATABASE_MODE = 0o660

    def __init__(self, path: str):
        self.path = Path(path)
        self._shared_gid: int | None = None
        shared_group = os.environ.get(self.SHARED_GROUP_ENV, "").strip()
        if shared_group:
            self._prepare_shared_state(shared_group)
        else:
            # Runner outcomes and ownership metadata are private state. Keep a
            # new isolated state directory private even when the host umask
            # is loose. This remains the default for disposable/single-user
            # runtimes.
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.path.is_symlink():
                raise Phase3Error("Phase 3 state must not be a symlink")
        with sqlite3.connect(self.path) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS phase3_automations (
                    automation_id TEXT PRIMARY KEY,
                    creator_subject_id TEXT NOT NULL,
                    owner_subject_id TEXT NOT NULL,
                    template_type TEXT NOT NULL,
                    resource_scope TEXT NOT NULL,
                    shared_with TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    enabled INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    manual_runs INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS phase3_previews (
                    preview_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    preview_hash TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS phase3_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS phase3_owner_idx ON phase3_automations(owner_subject_id, status);
                CREATE TABLE IF NOT EXISTS phase3_pending (
                    pending_key TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS phase3_runs (
                    run_id TEXT PRIMARY KEY,
                    automation_id TEXT NOT NULL,
                    execution_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    reason TEXT NOT NULL DEFAULT '',
                    started_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    UNIQUE(automation_id, execution_key),
                    FOREIGN KEY(automation_id) REFERENCES phase3_automations(automation_id)
                );
                CREATE INDEX IF NOT EXISTS phase3_runs_automation_idx
                    ON phase3_runs(automation_id, started_at DESC);
                CREATE TABLE IF NOT EXISTS phase3_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
        if self._shared_gid is None:
            self.path.chmod(0o600)
        else:
            self._verify_shared_database()

    def _prepare_shared_state(self, group_name: str) -> None:
        """Validate an explicitly provisioned group-shared SQLite location.

        Hermes and Epsilon are separate service users in production. The
        shared state contains automation ownership and read results, not
        credentials. A dedicated systemd supplementary group is the only
        supported cross-service access path; an existing private database is
        never silently widened.
        """
        try:
            gid = grp.getgrnam(group_name).gr_gid
        except KeyError as exc:
            raise Phase3Error("configured Phase 3 state group is unavailable") from exc
        parent = self.path.parent
        try:
            parent_info = parent.lstat()
        except OSError as exc:
            raise Phase3Error("shared Phase 3 state directory is unavailable") from exc
        if (
            not stat.S_ISDIR(parent_info.st_mode)
            or stat.S_IMODE(parent_info.st_mode) != self.SHARED_DIRECTORY_MODE
            or parent_info.st_gid != gid
            or gid not in {os.getegid(), *os.getgroups()}
        ):
            raise Phase3Error("shared Phase 3 state directory permissions are unsafe")

        self._shared_gid = gid
        try:
            info = self.path.lstat()
        except FileNotFoundError:
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self.path, flags, self.SHARED_DATABASE_MODE)
            except FileExistsError:
                # Another authorized service may have won first creation.
                # Validate its exact ownership/mode below before SQLite opens
                # the database; never loosen the racing file.
                try:
                    info = self.path.lstat()
                except OSError as exc:
                    self._shared_gid = None
                    raise Phase3Error("shared Phase 3 database is unavailable") from exc
            except OSError as exc:
                self._shared_gid = None
                raise Phase3Error("shared Phase 3 database could not be provisioned") from exc
            else:
                try:
                    os.fchown(fd, -1, gid)
                    os.fchmod(fd, self.SHARED_DATABASE_MODE)
                finally:
                    os.close(fd)
                info = self.path.lstat()
        except OSError as exc:
            self._shared_gid = None
            raise Phase3Error("shared Phase 3 database is unavailable") from exc

        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != self.SHARED_DATABASE_MODE
        ):
            self._shared_gid = None
            raise Phase3Error("shared Phase 3 database permissions are unsafe")

    def _verify_shared_database(self) -> None:
        try:
            info = self.path.lstat()
        except OSError as exc:
            raise Phase3Error("shared Phase 3 database is unavailable") from exc
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_gid != self._shared_gid
            or stat.S_IMODE(info.st_mode) != self.SHARED_DATABASE_MODE
        ):
            raise Phase3Error("shared Phase 3 database permissions are unsafe")

    def import_legacy_database(self, source_path: str) -> int:
        """Copy only Phase 3 tables from the former shared database once.

        The old shared state is never modified. If an import is retried after
        a partial/uncertain run, identical rows converge; conflicting rows
        fail closed instead of choosing one database silently.
        """
        source = Path(source_path)
        if not source.is_file() or source.resolve() == self.path.resolve():
            return 0
        source_key = str(source.resolve())
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            done = db.execute("SELECT value FROM phase3_meta WHERE key=?", ("legacy-import:" + source_key,)).fetchone()
            if done:
                return 0
            db.execute("ATTACH DATABASE ? AS legacy", (source_key,))
            tables = {row[0] for row in db.execute("SELECT name FROM legacy.sqlite_master WHERE type='table'")}
            copied = 0
            for table in ("phase3_automations", "phase3_previews", "phase3_audit", "phase3_pending", "phase3_runs"):
                if table not in tables:
                    continue
                legacy_columns = [row[1] for row in db.execute(f"PRAGMA legacy.table_info({table})")]
                local_columns = [row[1] for row in db.execute(f"PRAGMA main.table_info({table})")]
                if not legacy_columns:
                    continue
                if legacy_columns != local_columns:
                    db.execute("DETACH DATABASE legacy")
                    raise Phase3Error(f"legacy Phase 3 schema changed for {table}; manual reconciliation is required")
                # Compare rows with the same primary identity explicitly. A
                # row with any changed field must not be hidden by INSERT OR
                # IGNORE during a recovery rerun.
                primary = "automation_id" if table == "phase3_automations" else "preview_id" if table == "phase3_previews" else "audit_id" if table == "phase3_audit" else "pending_key" if table == "phase3_pending" else "run_id"
                if primary in legacy_columns:
                    equal = " AND ".join(f"old.{column} IS new.{column}" for column in legacy_columns)
                    changed = db.execute(
                        f"SELECT 1 FROM legacy.{table} AS old JOIN main.{table} AS new ON old.{primary}=new.{primary} WHERE NOT ({equal}) LIMIT 1"
                    ).fetchone()
                    if changed:
                        raise Phase3Error(f"conflicting Phase 3 row in legacy {table}; manual reconciliation is required")
                before = db.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
                db.execute(f"INSERT OR IGNORE INTO main.{table} ({','.join(legacy_columns)}) SELECT {','.join(legacy_columns)} FROM legacy.{table}")
                after = db.execute(f"SELECT COUNT(*) FROM main.{table}").fetchone()[0]
                copied += after - before
            db.execute("INSERT INTO phase3_meta(key,value) VALUES(?,?)", ("legacy-import:" + source_key, str(_now())))
        return copied

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        for key in ("resource_scope", "shared_with", "payload"):
            value[key] = json.loads(value[key])
        value["enabled"] = bool(value["enabled"])
        return value

    def list_for(self, authority: Phase3Authority) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT * FROM phase3_automations WHERE status != 'DELETED' ORDER BY created_at, automation_id").fetchall()
        visible = []
        for row in rows:
            item = self._row(row)
            if item["owner_subject_id"] == authority.subject or authority.subject in item["shared_with"]:
                if authority.active and set(item["resource_scope"]).issubset(authority.resources):
                    visible.append(item)
        return visible

    def list_owned(self, subject: str) -> list[dict[str, Any]]:
        """Return owner metadata even after resource authority is lost.

        This deliberately returns bounded metadata only.  It lets the creator
        delete or understand an authorization-lost record without exposing a
        protected result after revocation.
        """
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT * FROM phase3_automations WHERE owner_subject_id=? AND status != 'DELETED' ORDER BY created_at, automation_id",
                (subject,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def list_admin(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [self._row(row) for row in db.execute("SELECT * FROM phase3_automations WHERE status != 'DELETED' ORDER BY created_at, automation_id")]

    def _audit(self, db: sqlite3.Connection, automation_id: str, actor: str, action: str, detail: Mapping[str, Any] | None = None) -> None:
        db.execute("INSERT INTO phase3_audit(automation_id,actor,action,detail,created_at) VALUES(?,?,?,?,?)", (automation_id, actor, action, json.dumps(detail or {}, sort_keys=True), _now()))

    def audit_for(self, automation_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute("SELECT actor,action,detail,created_at FROM phase3_audit WHERE automation_id=? ORDER BY audit_id", (automation_id,))]

    def claim_run(self, automation_id: str, execution_key: str, authority: Phase3Authority) -> dict[str, Any]:
        """Atomically reserve one scheduled run after current owner checks.

        A previously completed key returns its stored result. A duplicate key
        that is already running or ended ambiguously never starts a second
        source read.
        """
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", execution_key or ""):
            raise Phase3Error("a bounded scheduler execution key is required")
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            automation = db.execute(
                "SELECT * FROM phase3_automations WHERE automation_id=?",
                (automation_id,),
            ).fetchone()
            if not automation:
                raise Phase3Error("automation does not exist")
            item = self._row(automation)
            if not authority.active or authority.subject != item["owner_subject_id"]:
                raise Phase3AuthorizationError("current automation owner authority is unavailable")
            if not set(item["resource_scope"]).issubset(authority.resources):
                raise Phase3AuthorizationError("current resource authority no longer permits this automation")
            if item["status"] != "STAGED" or not item["enabled"]:
                raise Phase3AuthorizationError("automation is disabled or no longer eligible to run")
            if item["template_type"] not in PHASE3_TEMPLATES:
                raise Phase3AuthorizationError("automation template is not approved")
            row = db.execute(
                "SELECT * FROM phase3_runs WHERE automation_id=? AND execution_key=?",
                (automation_id, execution_key),
            ).fetchone()
            if row:
                run = dict(row)
                if run["status"] == "RUNNING" and _now() - run["started_at"] > 120:
                    db.execute(
                        "UPDATE phase3_runs SET status='UNKNOWN',reason=?,completed_at=? WHERE run_id=? AND status='RUNNING'",
                        ("runner lease expired; source outcome was not reconciled", _now(), run["run_id"]),
                    )
                    run["status"] = "UNKNOWN"
                    run["reason"] = "runner lease expired; source outcome was not reconciled"
                    run["completed_at"] = _now()
                return {"disposition": "EXISTING", "run": run}
            run_id = "p3run-" + secrets.token_hex(12)
            started = _now()
            db.execute(
                "INSERT INTO phase3_runs(run_id,automation_id,execution_key,status,started_at) VALUES(?,?,?,?,?)",
                (run_id, automation_id, execution_key, "RUNNING", started),
            )
            self._audit(db, automation_id, authority.subject, "run-started", {"run_id": run_id})
            return {
                "disposition": "CLAIMED",
                "run": {"run_id": run_id, "automation_id": automation_id, "execution_key": execution_key,
                        "status": "RUNNING", "started_at": started},
                "automation": item,
            }

    def finish_run(self, run_id: str, *, result: Mapping[str, Any] | None = None, reason: str = "") -> dict[str, Any]:
        """Persist a bounded fixed-source outcome once; never overwrite a result."""
        encoded = None
        if result is not None:
            encoded = json.dumps(dict(result), separators=(",", ":"), sort_keys=True, allow_nan=False)
            if len(encoded.encode()) > 32768:
                raise Phase3Error("automation result exceeded its bounded storage size")
        status = "COMPLETE" if encoded is not None else "FAILED"
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT automation_id,status FROM phase3_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row:
                raise Phase3Error("scheduled run does not exist")
            if row[1] != "RUNNING":
                return self.get_run(run_id)
            db.execute(
                "UPDATE phase3_runs SET status=?,result=?,reason=?,completed_at=? WHERE run_id=? AND status='RUNNING'",
                (status, encoded, str(reason)[:200], _now(), run_id),
            )
            self._audit(db, row[0], "scheduler", "run-" + status.lower(), {"run_id": run_id, "reason": str(reason)[:200]})
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM phase3_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise Phase3Error("scheduled run does not exist")
        value = dict(row)
        value["result"] = json.loads(value["result"]) if value["result"] else None
        return value

    def result_for(self, run_id: str, requester: Phase3Authority, owner: Phase3Authority) -> dict[str, Any]:
        run = self.get_run(run_id)
        item = self.get(run["automation_id"])
        scope = set(item["resource_scope"])
        if not owner.active or owner.subject != item["owner_subject_id"] or not scope.issubset(owner.resources):
            raise Phase3AuthorizationError("current owner authority no longer permits this result")
        can_view = requester.subject == item["owner_subject_id"] or requester.subject in item["shared_with"]
        if not requester.active or not can_view or not scope.issubset(requester.resources):
            raise Phase3AuthorizationError("current authority does not permit this result")
        if run["status"] != "COMPLETE":
            raise Phase3Error("scheduled result is not complete")
        return {"run_id": run["run_id"], "automation_id": run["automation_id"], "status": run["status"], "result": run["result"]}

    def recent_completed_run_ids(self, automation_ids: Sequence[str], *, limit: int = 5) -> list[str]:
        """Return one latest completed run per visible automation, bounded for chat."""
        ids = sorted({value for value in automation_ids if isinstance(value, str) and value})
        if not ids:
            return []
        if not 1 <= limit <= 5:
            raise Phase3Error("result query limit is outside the fixed bound")
        placeholders = ",".join("?" for _ in ids)
        query = f"""SELECT run.run_id
            FROM phase3_runs AS run
            WHERE run.status='COMPLETE'
              AND run.automation_id IN ({placeholders})
              AND NOT EXISTS (
                SELECT 1 FROM phase3_runs AS newer
                WHERE newer.automation_id=run.automation_id
                  AND newer.status='COMPLETE'
                  AND (newer.completed_at > run.completed_at
                       OR (newer.completed_at=run.completed_at AND newer.rowid > run.rowid))
              )
            ORDER BY run.completed_at DESC, run.rowid DESC
            LIMIT ?"""
        with sqlite3.connect(self.path) as db:
            rows = db.execute(query, (*ids, limit)).fetchall()
        return [str(row[0]) for row in rows]

    def recent_backup_successes(
        self, automation_id: str, *, limit: int = 100,
    ) -> tuple[dict[str, dict[str, int | float]], bool]:
        """Return bounded last-good evidence for the two fixed repository targets."""
        if not 1 <= limit <= 100:
            raise Phase3Error("backup result history limit is outside the fixed bound")
        allowed = {"hades", "infra"}
        found: dict[str, dict[str, int | float]] = {}
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                """SELECT result, completed_at FROM phase3_runs
                   WHERE automation_id=? AND status='COMPLETE' AND result IS NOT NULL
                   ORDER BY completed_at DESC, rowid DESC LIMIT ?""",
                (automation_id, limit),
            ).fetchall()
        truncated = len(rows) == limit
        for encoded, completed_at in rows:
            if type(completed_at) is not int:
                continue
            try:
                result = json.loads(encoded)
            except (TypeError, ValueError):
                continue
            targets = result.get("targets") if isinstance(result, dict) else None
            if not isinstance(targets, list):
                continue
            for target in targets[:2]:
                if not isinstance(target, dict):
                    continue
                name = target.get("target")
                artifact_mtime = target.get("artifact_mtime")
                if (
                    not isinstance(name, str)
                    or name not in allowed
                    or name in found
                    or target.get("hades_state") != "HEALTHY"
                    or type(artifact_mtime) not in (int, float)
                    or not (0 <= artifact_mtime <= 253402300799)
                ):
                    continue
                found[name] = {
                    "checked_at": int(completed_at),
                    "artifact_mtime": float(artifact_mtime),
                }
            if found.keys() == allowed:
                break
        return found, truncated

    def due_schedule_items(
        self, *, template_type: str | None = None, now: int | None = None, limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Select a bounded due batch from enabled fixed-template records.

        Each interval has one stable key, so repeated scheduler delivery cannot
        create another source read. Missed intervals coalesce into the current
        slot; an UNKNOWN latest outcome blocks automatic later runs pending
        explicit operator recovery.
        """
        if not 1 <= limit <= 25:
            raise Phase3Error("schedule batch limit is outside the fixed bound")
        if template_type is not None and template_type not in PHASE3_TEMPLATES:
            raise Phase3Error("schedule template is outside the fixed catalog")
        current = _now() if now is None else int(now)
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT automation.automation_id, automation.interval_minutes,
                          automation.updated_at, latest.status AS latest_status
                   FROM phase3_automations AS automation
                   LEFT JOIN phase3_runs AS latest
                     ON latest.run_id = (
                       SELECT run.run_id FROM phase3_runs AS run
                       WHERE run.automation_id = automation.automation_id
                       ORDER BY run.started_at DESC, run.rowid DESC LIMIT 1
                     )
                   WHERE automation.status='STAGED' AND automation.enabled=1
                     AND automation.interval_minutes BETWEEN 5 AND 10080
                     AND automation.updated_at + automation.interval_minutes * 60 <= ?
                     AND (? IS NULL OR automation.template_type=?)
                   ORDER BY automation.updated_at, automation.automation_id
                   LIMIT 1000""",
                (current, template_type, template_type),
            ).fetchall()
            due: list[dict[str, Any]] = []
            for row in rows:
                if row["latest_status"] == "UNKNOWN":
                    continue
                interval = int(row["interval_minutes"]) * 60
                base = int(row["updated_at"])
                due_at = base + ((current - base) // interval) * interval
                execution_key = f"schedule:{due_at}"
                existing = db.execute(
                    "SELECT 1 FROM phase3_runs WHERE automation_id=? AND execution_key=?",
                    (row["automation_id"], execution_key),
                ).fetchone()
                if existing:
                    continue
                due.append({
                    "automation_id": str(row["automation_id"]),
                    "execution_key": execution_key,
                    "due_at": due_at,
                })
                if len(due) >= limit:
                    break
        return due

    def preview_put(self, actor: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        preview_id = "p3-" + secrets.token_urlsafe(12)
        value = dict(payload)
        preview_hash = _hash(value)
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO phase3_previews VALUES(?,?,?,?,?)", (preview_id, actor, json.dumps(value, sort_keys=True), preview_hash, _now() + 600))
        return {"preview_id": preview_id, "preview_hash": preview_hash, **value}

    def preview_take(self, actor: str, preview_id: str, expected_hash: str | None = None) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload,preview_hash,expires_at FROM phase3_previews WHERE preview_id=? AND actor=?", (preview_id, actor)).fetchone()
            if not row or row[2] < _now():
                raise Phase3Error("preview is missing or expired")
            if expected_hash and row[1] != expected_hash:
                raise Phase3Error("confirmation does not match the current preview")
            db.execute("DELETE FROM phase3_previews WHERE preview_id=?", (preview_id,))
        return json.loads(row[0])

    def latest_preview(self, actor: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT preview_id,payload,preview_hash,expires_at FROM phase3_previews WHERE actor=? ORDER BY expires_at DESC LIMIT 1", (actor,)).fetchone()
        if not row or row[3] < _now():
            return None
        value = json.loads(row[1])
        value.update({"preview_id": row[0], "preview_hash": row[2]})
        return value

    def pending_put(self, pending_key: str, actor: str, payload: Mapping[str, Any]) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO phase3_pending VALUES(?,?,?,?)", (pending_key, actor, json.dumps(dict(payload), sort_keys=True), _now() + 600))

    def pending_get(self, pending_key: str, actor: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload,expires_at FROM phase3_pending WHERE pending_key=? AND actor=?", (pending_key, actor)).fetchone()
            if row and row[1] < _now():
                db.execute("DELETE FROM phase3_pending WHERE pending_key=?", (pending_key,))
                row = None
        return json.loads(row[0]) if row else None

    def pending_delete(self, pending_key: str, actor: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM phase3_pending WHERE pending_key=? AND actor=?", (pending_key, actor))

    def pending_for_actor(self, actor: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT pending_key,payload,expires_at FROM phase3_pending WHERE actor=?", (actor,)).fetchall()
        now = _now()
        return [{"pending_key": row[0], **json.loads(row[1])} for row in rows if row[2] >= now]

    def create(self, authority: Phase3Authority, payload: Mapping[str, Any], quotas: Phase3Quotas, request_key: str) -> dict[str, Any]:
        if not _valid_subject(authority.subject):
            raise Phase3AuthorizationError("authenticated actor required")
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.row_factory = sqlite3.Row
            # Python's sqlite wrapper does not necessarily begin the IMMEDIATE
            # transaction for a read-only SELECT. Acquire the write reservation
            # before checking quotas/idempotency so two confirmations cannot
            # both observe the same available slot.
            db.execute("BEGIN IMMEDIATE")
            # A retried confirmation must reconcile to the canonical staged
            # record instead of consuming a second admission attempt.
            for audit in db.execute("SELECT automation_id,detail FROM phase3_audit WHERE action='create' ORDER BY audit_id DESC").fetchall():
                try:
                    detail = json.loads(audit[1])
                except (TypeError, ValueError):
                    detail = {}
                if detail.get("request_key") == request_key:
                    row = db.execute("SELECT * FROM phase3_automations WHERE automation_id=?", (audit[0],)).fetchone()
                    if row:
                        return self._row(row)
            active = db.execute("SELECT COUNT(*) FROM phase3_automations WHERE owner_subject_id=? AND enabled=1 AND status='STAGED'", (authority.subject,)).fetchone()[0]
            maximum = quotas.owner_active if authority.is_owner else quotas.household_active
            if active >= maximum:
                raise Phase3QuotaError(f"You already have {maximum} active automations. Pause or remove one before creating another.")
            duplicate = db.execute("SELECT automation_id FROM phase3_automations WHERE owner_subject_id=? AND template_type=? AND resource_scope=? AND status='STAGED'", (authority.subject, payload["template_type"], json.dumps(payload["resource_scope"], sort_keys=True))).fetchone()
            if duplicate:
                raise Phase3DuplicateError("You already have this automation. I did not create a duplicate.")
            automation_id = str(payload.get("automation_id") or ("p3-" + secrets.token_hex(8)))
            now = _now()
            db.execute("INSERT INTO phase3_automations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (automation_id, authority.subject, authority.subject, payload["template_type"], json.dumps(payload["resource_scope"], sort_keys=True), "[]", int(payload["interval_minutes"]), 1, "STAGED", json.dumps(dict(payload), sort_keys=True), now, now, 0))
            self._audit(db, automation_id, authority.subject, "create", {"request_key": request_key, "staged": True})
            row = db.execute("SELECT * FROM phase3_automations WHERE automation_id=?", (automation_id,)).fetchone()
        return self._row(row)

    def get(self, automation_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM phase3_automations WHERE automation_id=?", (automation_id,)).fetchone()
        if not row:
            raise Phase3Error("automation does not exist")
        return self._row(row)

    def control(
        self, authority: Phase3Authority, automation_id: str, action: str, *,
        interval_minutes: int | None = None, quotas: Phase3Quotas | None = None,
    ) -> dict[str, Any]:
        item = self.get(automation_id)
        shared_run = action == "run" and authority.subject in item["shared_with"]
        if not authority.active or (item["owner_subject_id"] != authority.subject and not shared_run):
            raise Phase3AuthorizationError("only the automation owner may control it")
        if action == "run":
            raise Phase3Error(
                "this automation is a saved draft and is not connected to the HADES runner; nothing was run"
            )
        if action not in {"pause", "resume", "edit", "delete"}:
            raise Phase3Error("unsupported staged lifecycle action")
        if action == "edit":
            if interval_minutes is None or interval_minutes < DEFAULT_QUOTAS["min_interval_minutes"] or interval_minutes > 10080:
                raise Phase3Error("schedule must stay between 5 minutes and 7 days")
            changes = ("interval_minutes=?", "updated_at=?")
            args = (int(interval_minutes), _now(), automation_id)
            status = item["status"]
        elif action == "pause":
            changes, args, status = ("enabled=?", "updated_at=?"), (0, _now(), automation_id), item["status"]
        elif action == "resume":
            limits = quotas or Phase3Quotas()
            with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
                db.execute("BEGIN IMMEDIATE")
                db.row_factory = sqlite3.Row
                row = db.execute(
                    "SELECT * FROM phase3_automations WHERE automation_id=?",
                    (automation_id,),
                ).fetchone()
                if not row:
                    raise Phase3Error("automation does not exist")
                item = self._row(row)
                if not authority.active or item["owner_subject_id"] != authority.subject:
                    raise Phase3AuthorizationError("only the automation owner may control it")
                if not set(item["resource_scope"]).issubset(authority.resources):
                    raise Phase3AuthorizationError("current resource authority no longer permits this automation")
                if item["status"] == "AUTHORIZATION_LOST":
                    raise Phase3AuthorizationError("current resource authority no longer permits this automation; it is disabled")
                if not item["enabled"]:
                    maximum = limits.owner_active if authority.is_owner else limits.household_active
                    active = db.execute(
                        "SELECT COUNT(*) FROM phase3_automations WHERE owner_subject_id=? AND enabled=1 AND status='STAGED'",
                        (authority.subject,),
                    ).fetchone()[0]
                    if active >= maximum:
                        raise Phase3QuotaError(f"You already have {maximum} active automations. Pause or remove one before resuming this one.")
                db.execute(
                    "UPDATE phase3_automations SET enabled=1,updated_at=? WHERE automation_id=?",
                    (_now(), automation_id),
                )
                self._audit(db, automation_id, authority.subject, "resume", {})
            return self.get(automation_id)
        elif action == "delete":
            changes, args, status = ("enabled=?", "status=?", "updated_at=?"), (0, "DELETED", _now(), automation_id), "DELETED"
        else:
            raise Phase3Error("unsupported staged lifecycle action")
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.execute(f"UPDATE phase3_automations SET {', '.join(changes)} WHERE automation_id=?", args)
            self._audit(db, automation_id, authority.subject, action, {"interval_minutes": interval_minutes} if interval_minutes else {})
        return self.get(automation_id)

    def share(self, authority: Phase3Authority, automation_id: str, recipient: Phase3Authority, revoke: bool = False) -> dict[str, Any]:
        item = self.get(automation_id)
        if item["owner_subject_id"] != authority.subject or not authority.active:
            raise Phase3AuthorizationError("only the automation owner may change sharing")
        if not recipient.active or not set(item["resource_scope"]).issubset(recipient.resources):
            raise Phase3AuthorizationError("recipient does not currently have the required resource authority")
        shared = set(item["shared_with"])
        if revoke:
            shared.discard(recipient.subject)
        else:
            shared.add(recipient.subject)
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.execute("UPDATE phase3_automations SET shared_with=?,updated_at=? WHERE automation_id=?", (json.dumps(sorted(shared)), _now(), automation_id))
            self._audit(db, automation_id, authority.subject, "revoke-share" if revoke else "share", {"recipient": recipient.subject})
        return self.get(automation_id)

    def revoke_actor(self, subject: str, reason: str = "authority removed") -> int:
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            rows = db.execute("SELECT automation_id FROM phase3_automations WHERE owner_subject_id=? AND status='STAGED'", (subject,)).fetchall()
            db.execute("UPDATE phase3_automations SET enabled=0,status='AUTHORIZATION_LOST',shared_with='[]',updated_at=? WHERE owner_subject_id=? AND status='STAGED'", (_now(), subject))
            shared_rows = db.execute("SELECT automation_id,shared_with FROM phase3_automations WHERE status='STAGED'").fetchall()
            for automation_id, encoded in shared_rows:
                shared = set(json.loads(encoded))
                if subject in shared:
                    shared.remove(subject)
                    db.execute("UPDATE phase3_automations SET shared_with=?,updated_at=? WHERE automation_id=?", (json.dumps(sorted(shared)), _now(), automation_id))
                    self._audit(db, automation_id, subject, "revoke-share", {"reason": reason})
            for row in rows:
                self._audit(db, row[0], subject, "authorization-lost", {"reason": reason})
        return len(rows)

    def revoke_resource(self, subject: str, resource: str, reason: str = "resource authority removed") -> int:
        changed = 0
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT automation_id,resource_scope FROM phase3_automations WHERE owner_subject_id=? AND status='STAGED'", (subject,)).fetchall()
            for row in rows:
                if resource in json.loads(row["resource_scope"]):
                    db.execute("UPDATE phase3_automations SET enabled=0,status='AUTHORIZATION_LOST',updated_at=? WHERE automation_id=?", (_now(), row["automation_id"]))
                    self._audit(db, row["automation_id"], subject, "authorization-lost", {"reason": reason, "resource": resource})
                    changed += 1
        return changed

    def admin_disable(self, authority: Phase3Authority, automation_id: str, reason: str) -> dict[str, Any]:
        if not authority.is_owner:
            raise Phase3AuthorizationError("owner oversight is required")
        item = self.get(automation_id)
        with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
            db.execute("UPDATE phase3_automations SET enabled=0,updated_at=? WHERE automation_id=?", (_now(), automation_id))
            self._audit(db, automation_id, authority.subject, "admin-disable", {"reason": reason})
        return self.get(item["automation_id"])


class Phase3Service:
    def __init__(self, store: Phase3Store, catalog: Phase3Catalog | None = None, quotas: Phase3Quotas | None = None):
        self.store = store
        self.catalog = catalog or Phase3Catalog()
        self.quotas = quotas or Phase3Quotas()

    def preview(self, authority: Phase3Authority, template: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not authority.active:
            raise Phase3AuthorizationError("current account is inactive")
        value = dict(payload)
        allowed_fields = {
            "server-health-watch": {"resource_id", "display_name", "interval_minutes"},
            "low-inventory-summary": {"interval_minutes", "resource_scope"},
            "weekly-household-summary": {"interval_minutes", "resource_scope"},
            "hades-backup-verification": {"interval_minutes", "resource_scope"},
        }.get(template)
        if allowed_fields is None or set(value) - allowed_fields:
            raise Phase3Error("that automation has unsupported configuration fields")
        value["template_type"] = template
        value.setdefault("interval_minutes", 10080 if template in {"low-inventory-summary", "weekly-household-summary"} else 10)
        value.setdefault("resource_scope", sorted(_template_resources(template, value)))
        interval = int(value["interval_minutes"])
        if interval < self.quotas.min_interval_minutes or interval > 10080:
            raise Phase3Error("schedule must stay between 5 minutes and 7 days")
        self.catalog.require_template(authority, template, value)
        existing = [item for item in self.store.list_for(authority) if item["owner_subject_id"] == authority.subject and item["template_type"] == template and item["resource_scope"] == value["resource_scope"]]
        value["existing_automation"] = existing[0]["automation_id"] if existing else ""
        value["creator_subject_id"] = authority.subject
        value["owner_subject_id"] = authority.subject
        value["shared_with"] = []
        preview = self.store.preview_put(authority.subject, value)
        preview["template"] = PHASE3_TEMPLATES[template]
        preview["staged_only"] = True
        preview["read_only"] = True
        preview["can_modify_resource"] = False
        preview["requires_confirmation"] = True
        return preview

    def confirm(self, authority: Phase3Authority, preview_id: str, preview_hash: str, request_key: str) -> dict[str, Any]:
        payload = self.store.preview_take(authority.subject, preview_id, preview_hash)
        self.catalog.require_template(authority, payload["template_type"], payload)
        if payload.get("existing_automation"):
            raise Phase3DuplicateError("You already have this automation saved. I did not create a duplicate.")
        return self.store.create(authority, payload, self.quotas, request_key)

    def control(self, authority: Phase3Authority, automation_id: str, action: str, *, interval_minutes: int | None = None) -> dict[str, Any]:
        item = self.store.get(automation_id)
        if action not in {"run", "pause", "resume", "edit", "delete"}:
            raise Phase3Error("unsupported staged lifecycle action")
        if not authority.active:
            raise Phase3AuthorizationError("only an active authenticated actor may control it")
        owns_record = item["owner_subject_id"] == authority.subject
        shared_run = action == "run" and authority.subject in item["shared_with"]
        if not owns_record and not shared_run:
            raise Phase3AuthorizationError("only the automation owner may control it")
        if action != "delete" and not set(item["resource_scope"]).issubset(authority.resources):
            missing = sorted(set(item["resource_scope"]) - set(authority.resources))
            # Only the authenticated owner may trigger authorization-loss
            # cleanup. A shared recipient with a stale/incomplete grant loses
            # access, but cannot disable the owner's record by naming its ID.
            if owns_record:
                for resource in missing:
                    self.store.revoke_resource(item["owner_subject_id"], resource)
            raise Phase3AuthorizationError("current resource authority no longer permits this automation")
        if action == "run":
            raise Phase3Error(
                "this automation is a saved draft and is not connected to the HADES runner; nothing was run"
            )
        return self.store.control(
            authority, automation_id, action,
            interval_minutes=interval_minutes, quotas=self.quotas,
        )


class Phase3Runner:
    """Execute one approved read-only source through current owner authority.

    The caller must authenticate the scheduler before calling this class. The
    runner resolves current authority itself for the stored owner, rechecks
    record state before dispatch, and stores an idempotent result. It accepts
    only the four fixed Phase 3 source readers; it has no workflow or URL
    selection input.
    """

    def __init__(
        self,
        store: Phase3Store,
        authority_for_subject: Callable[[str], Phase3Authority],
        source_readers: Mapping[str, Callable[[Mapping[str, Any]], Mapping[str, Any]]],
        catalog: Phase3Catalog | None = None,
    ):
        expected = set(PHASE3_TEMPLATES)
        if set(source_readers) - expected:
            raise Phase3Error("runner source registry contains an unapproved template")
        self.store = store
        self.authority_for_subject = authority_for_subject
        self.source_readers = dict(source_readers)
        self.catalog = catalog or Phase3Catalog()

    def run(self, automation_id: str, execution_key: str) -> dict[str, Any]:
        item = self.store.get(automation_id)
        owner = str(item["owner_subject_id"])
        try:
            authority = self.authority_for_subject(owner)
        except Exception:
            raise Phase3AuthorizationError("current automation owner authority is unavailable") from None
        claim = self.store.claim_run(automation_id, execution_key, authority)
        run = claim["run"]
        if claim["disposition"] == "EXISTING":
            return {
                "status": run["status"],
                "run_id": run["run_id"],
                "result": json.loads(run["result"]) if run.get("result") else None,
                "reason": run["reason"],
                "replayed": True,
            }

        template = claim["automation"]["template_type"]
        reader = self.source_readers.get(template)
        if reader is None:
            self.store.finish_run(run["run_id"], reason="approved source is not configured")
            return {"status": "FAILED", "run_id": run["run_id"], "result": None, "reason": "approved source is not configured"}

        # Resolve identity/grants and record state again immediately before a
        # canonical read. A revocation or pause after reservation fails closed.
        try:
            current = self.authority_for_subject(owner)
        except Exception:
            self.store.finish_run(run["run_id"], reason="current authority could not be revalidated before source read")
            return {
                "status": "FAILED",
                "run_id": run["run_id"],
                "result": None,
                "reason": "current authority could not be revalidated before source read",
                "replayed": False,
            }
        latest = self.store.get(automation_id)
        if (
            not current.active
            or current.subject != owner
            or not set(latest["resource_scope"]).issubset(current.resources)
            or set(latest["resource_scope"]) != _template_resources(template, claim["automation"]["payload"])
            or not latest["enabled"]
            or latest["status"] != "STAGED"
        ):
            self.store.finish_run(run["run_id"], reason="current authority or automation state changed before source read")
            return {"status": "FAILED", "run_id": run["run_id"], "result": None, "reason": "current authority or automation state changed before source read"}
        try:
            self.catalog.require_template(current, template, claim["automation"]["payload"])
        except Phase3Error:
            self.store.finish_run(run["run_id"], reason="current authority rejected the approved source")
            return {"status": "FAILED", "run_id": run["run_id"], "result": None, "reason": "current authority rejected the approved source"}

        try:
            result = reader(claim["automation"]["payload"])
            if not isinstance(result, Mapping):
                raise Phase3Error("fixed source returned an invalid result")
            saved = self.store.finish_run(run["run_id"], result=result)
            return {"status": saved["status"], "run_id": run["run_id"], "result": saved["result"], "reason": "", "replayed": False}
        except Exception as exc:
            reason = f"fixed source failed ({type(exc).__name__})"
            saved = self.store.finish_run(run["run_id"], reason=reason)
            return {"status": saved["status"], "run_id": run["run_id"], "result": None, "reason": saved["reason"], "replayed": False}

    def result_for(self, run_id: str, requester: Phase3Authority) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        item = self.store.get(run["automation_id"])
        owner = self.authority_for_subject(item["owner_subject_id"])
        return self.store.result_for(run_id, requester, owner)

    def recent_results_for(self, requester_subject: str) -> list[dict[str, Any]]:
        """Read only recent completed results visible under current grants."""
        requester = self.authority_for_subject(requester_subject)
        if not requester.active or requester.subject != requester_subject:
            raise Phase3AuthorizationError("current requester authority does not permit these results")
        visible = self.store.list_for(requester)
        run_ids = self.store.recent_completed_run_ids(
            [item["automation_id"] for item in visible], limit=5,
        )
        results = []
        for run_id in run_ids:
            # Resolve the requester again per row so a long list cannot outlive
            # a directory revocation while the response is being assembled.
            current_requester = self.authority_for_subject(requester_subject)
            if not current_requester.active or current_requester.subject != requester_subject:
                raise Phase3AuthorizationError("current requester authority does not permit these results")
            protected = self.result_for(run_id, current_requester)
            run = self.store.get_run(run_id)
            item = self.store.get(protected["automation_id"])
            result = protected["result"]
            if item["template_type"] == "hades-backup-verification" and isinstance(result, dict):
                result = dict(result)
                last_successes, history_truncated = self.store.recent_backup_successes(item["automation_id"])
                result["last_success_by_target"] = last_successes
                result["last_success_history_truncated"] = history_truncated
            results.append({
                "template_type": item["template_type"],
                "resource_scope": item["resource_scope"],
                "completed_at": run["completed_at"],
                "result": result,
            })
        return results
