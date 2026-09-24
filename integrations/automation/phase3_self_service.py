"""Staged household self-service for the approved read-only catalog.

This module is deliberately separate from the Phase 2 live adapters.  It owns
creator/owner metadata, current-authority checks, simple admission limits, and
staged lifecycle semantics.  It never creates an n8n workflow; a future
promotion adapter must make that an explicit, separately authorized choice.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


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

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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
                """
            )
        self.path.chmod(0o600)

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

    def control(self, authority: Phase3Authority, automation_id: str, action: str, *, interval_minutes: int | None = None) -> dict[str, Any]:
        item = self.get(automation_id)
        shared_run = action == "run" and authority.subject in item["shared_with"]
        if not authority.active or (item["owner_subject_id"] != authority.subject and not shared_run):
            raise Phase3AuthorizationError("only the automation owner may control it")
        if action not in {"run", "pause", "resume", "edit", "delete"}:
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
            changes, args, status = ("enabled=?", "updated_at=?"), (1, _now(), automation_id), item["status"]
        elif action == "delete":
            changes, args, status = ("enabled=?", "status=?", "updated_at=?"), (0, "DELETED", _now(), automation_id), "DELETED"
        else:
            if item["status"] == "AUTHORIZATION_LOST":
                raise Phase3AuthorizationError("current resource authority no longer permits this automation; it is disabled")
            if not item["enabled"]:
                raise Phase3Error("automation is paused")
            with sqlite3.connect(self.path, isolation_level="IMMEDIATE") as db:
                count = db.execute("SELECT manual_runs FROM phase3_automations WHERE automation_id=?", (automation_id,)).fetchone()[0]
                if count >= DEFAULT_QUOTAS["max_manual_runs"]:
                    raise Phase3QuotaError("Manual run limit reached; wait for the next schedule window.")
                db.execute("UPDATE phase3_automations SET manual_runs=manual_runs+1,updated_at=? WHERE automation_id=?", (_now(), automation_id))
                self._audit(db, automation_id, authority.subject, "run", {})
            return self.get(automation_id)
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
            raise Phase3DuplicateError("You're already running this automation. I did not create a duplicate.")
        return self.store.create(authority, payload, self.quotas, request_key)

    def control(self, authority: Phase3Authority, automation_id: str, action: str, *, interval_minutes: int | None = None) -> dict[str, Any]:
        item = self.store.get(automation_id)
        if action != "delete" and not set(item["resource_scope"]).issubset(authority.resources):
            missing = sorted(set(item["resource_scope"]) - set(authority.resources))
            for resource in missing:
                self.store.revoke_resource(item["owner_subject_id"], resource)
            raise Phase3AuthorizationError("current resource authority no longer permits this automation")
        return self.store.control(authority, automation_id, action, interval_minutes=interval_minutes)
