"""Shared staged lifecycle for bounded typed read-only automations.

Phase 2 templates use this boundary while production promotion is disabled.
The default adapter is an in-memory staging adapter; no n8n schedule is
created unless the caller explicitly supplies an enabled promotion gate.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


class LifecycleError(ValueError):
    pass


class UnknownMutation(LifecycleError):
    pass


@dataclass(frozen=True)
class TypedTemplate:
    template_id: str
    display_name: str
    owner_only_creation: bool = True
    read_only: bool = True
    production_enabled: bool = False


PHASE2_TEMPLATES = {
    item.template_id: item for item in (
        TypedTemplate("hades-backup-verification", "Backup Check", production_enabled=True),
        TypedTemplate("low-inventory-summary", "Low Grocery Summary"),
        TypedTemplate("weekly-household-summary", "Weekly Household Summary"),
    )
}


class LifecycleAdapter(Protocol):
    def reconcile(self, operation_key: str) -> Mapping[str, Any] | None: ...
    def promote(self, template: TypedTemplate, payload: Mapping[str, Any], operation_key: str) -> Mapping[str, Any]: ...
    def mutate(self, action: str, template: TypedTemplate, payload: Mapping[str, Any], operation_key: str) -> Mapping[str, Any]: ...


class StagingAdapter:
    """Disabled fixture adapter; it never contacts n8n."""

    def __init__(self):
        self.staged: dict[str, dict[str, Any]] = {}

    def reconcile(self, operation_key: str) -> Mapping[str, Any] | None:
        return self.staged.get(operation_key)

    def promote(self, template: TypedTemplate, payload: Mapping[str, Any], operation_key: str) -> Mapping[str, Any]:
        result = {"status": "STAGED", "template_id": template.template_id, "operation_key": operation_key, "production_schedule": False}
        self.staged[operation_key] = result
        return result

    def mutate(self, action: str, template: TypedTemplate, payload: Mapping[str, Any], operation_key: str) -> Mapping[str, Any]:
        result = {"status": "STAGED", "action": action, "template_id": template.template_id, "operation_key": operation_key, "production_schedule": False}
        self.staged[operation_key] = result
        return result


class LifecycleStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS lifecycle_operations (operation_key TEXT PRIMARY KEY, actor TEXT NOT NULL, template_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL, updated_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS lifecycle_previews (preview_id TEXT PRIMARY KEY, actor TEXT NOT NULL, payload TEXT NOT NULL, expires_at INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS lifecycle_pending (pending_key TEXT PRIMARY KEY, actor TEXT NOT NULL, payload TEXT NOT NULL, expires_at INTEGER NOT NULL)")
        self.path.chmod(0o600)

    def get(self, operation_key: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT actor,template_id,payload,status,result,updated_at FROM lifecycle_operations WHERE operation_key=?", (operation_key,)).fetchone()
        if not row:
            return None
        return {"actor": row[0], "template_id": row[1], "payload": json.loads(row[2]), "status": row[3], "result": json.loads(row[4]), "updated_at": row[5]}

    def list_actor(self, actor: str, template_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT operation_key,template_id,payload,status,result,updated_at FROM lifecycle_operations WHERE actor=?"
        args: list[Any] = [actor]
        if template_id:
            query += " AND template_id=?"
            args.append(template_id)
        query += " ORDER BY updated_at DESC"
        with sqlite3.connect(self.path) as db:
            rows = db.execute(query, args).fetchall()
        return [{"operation_key": r[0], "template_id": r[1], "payload": json.loads(r[2]), "status": r[3], "result": json.loads(r[4]), "updated_at": r[5]} for r in rows]

    def list_template(self, template_id: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT operation_key,actor,template_id,payload,status,result,updated_at FROM lifecycle_operations WHERE template_id=? ORDER BY updated_at DESC", (template_id,)).fetchall()
        return [{"operation_key": r[0], "actor": r[1], "template_id": r[2], "payload": json.loads(r[3]), "status": r[4], "result": json.loads(r[5]), "updated_at": r[6]} for r in rows]

    def put(self, operation_key: str, actor: str, template_id: str, payload: Mapping[str, Any], status: str, result: Mapping[str, Any]) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO lifecycle_operations(operation_key,actor,template_id,payload,status,result,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(operation_key) DO UPDATE SET status=excluded.status,result=excluded.result,updated_at=excluded.updated_at", (operation_key, actor, template_id, json.dumps(payload, sort_keys=True), status, json.dumps(result, sort_keys=True), int(time.time())))

    def update_payload(self, operation_key: str, payload: Mapping[str, Any]) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE lifecycle_operations SET payload=?,updated_at=? WHERE operation_key=?", (json.dumps(payload, sort_keys=True), int(time.time()), operation_key))

    def preview_put(self, preview_id: str, actor: str, payload: Mapping[str, Any], expires_at: int) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO lifecycle_previews(preview_id,actor,payload,expires_at) VALUES(?,?,?,?)", (preview_id, actor, json.dumps(payload, sort_keys=True), expires_at))

    def preview_take(self, preview_id: str, actor: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload,expires_at FROM lifecycle_previews WHERE preview_id=? AND actor=?", (preview_id, actor)).fetchone()
            if not row or row[1] < int(time.time()):
                raise LifecycleError("preview is missing or expired")
            db.execute("DELETE FROM lifecycle_previews WHERE preview_id=?", (preview_id,))
        return json.loads(row[0])

    def pending_put(self, pending_key: str, actor: str, payload: Mapping[str, Any], expires_at: int) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO lifecycle_pending(pending_key,actor,payload,expires_at) VALUES(?,?,?,?)", (pending_key, actor, json.dumps(payload, sort_keys=True), expires_at))

    def pending_get(self, pending_key: str, actor: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload,expires_at FROM lifecycle_pending WHERE pending_key=? AND actor=?", (pending_key, actor)).fetchone()
            if row and row[1] < int(time.time()):
                db.execute("DELETE FROM lifecycle_pending WHERE pending_key=?", (pending_key,))
                row = None
        return json.loads(row[0]) if row else None

    def pending_delete(self, pending_key: str, actor: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM lifecycle_pending WHERE pending_key=? AND actor=?", (pending_key, actor))

    def pending_for_actor(self, actor: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT pending_key,payload,expires_at FROM lifecycle_pending WHERE actor=?", (actor,)).fetchall()
        now = int(time.time())
        return [{"pending_key": row[0], "payload": json.loads(row[1]), "expires_at": row[2]} for row in rows if row[2] >= now]


class TypedLifecycle:
    def __init__(self, store: LifecycleStore, adapter: LifecycleAdapter | None = None, *, promotion_enabled: bool = False):
        self.store = store
        self.adapter = adapter or StagingAdapter()
        self.promotion_enabled = promotion_enabled

    def preview(self, actor: str, template_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        template = PHASE2_TEMPLATES.get(template_id)
        if not template:
            raise LifecycleError("unsupported typed automation template")
        if not actor:
            raise LifecycleError("authenticated actor required")
        if not template.read_only:
            raise LifecycleError("Phase 2 lifecycle accepts read-only templates only")
        preview_hash = hashlib.sha256(json.dumps(dict(payload), sort_keys=True).encode()).hexdigest()
        return {"template_id": template.template_id, "display_name": template.display_name, "owner": actor, "payload": dict(payload), "preview_hash": preview_hash, "requires_confirmation": True, "production_enabled": self.promotion_enabled and template.production_enabled}

    def confirm(self, actor: str, preview: Mapping[str, Any], *, confirmed: bool, operation_key: str) -> Mapping[str, Any]:
        if not confirmed:
            raise LifecycleError("explicit confirmation is required")
        if not operation_key:
            raise LifecycleError("idempotency key is required")
        existing = self.store.get(operation_key)
        if existing:
            return existing["result"]
        template_id = str(preview.get("template_id", ""))
        template = PHASE2_TEMPLATES.get(template_id)
        if not template or preview.get("owner") != actor:
            raise LifecycleError("confirmation is not authorized for this template")
        payload = preview.get("payload")
        if not isinstance(payload, Mapping):
            raise LifecycleError("preview payload is invalid")
        expected = hashlib.sha256(json.dumps(dict(payload), sort_keys=True).encode()).hexdigest()
        if expected != preview.get("preview_hash"):
            raise LifecycleError("confirmation does not match the current preview")
        if not self.promotion_enabled or not template.production_enabled:
            result = self.adapter.promote(template, payload, operation_key)
            self.store.put(operation_key, actor, template_id, payload, "STAGED", result)
            return result
        try:
            result = self.adapter.promote(template, payload, operation_key)
        except UnknownMutation:
            # Reconcile canonical runner state before any possible retry.
            reconciled = self.adapter.reconcile(operation_key)
            if reconciled is not None:
                result = reconciled
            else:
                raise
        self.store.put(operation_key, actor, template_id, payload, "PROMOTED", result)
        return result

    def mutate(self, actor: str, template_id: str, action: str, payload: Mapping[str, Any], *, confirmed: bool, operation_key: str) -> Mapping[str, Any]:
        if not confirmed:
            raise LifecycleError("explicit confirmation is required")
        if action not in {"edit", "delete", "pause", "resume", "run"}:
            raise LifecycleError("unsupported typed lifecycle action")
        template = PHASE2_TEMPLATES.get(template_id)
        if not template or not actor or not operation_key:
            raise LifecycleError("current owner authorization and idempotency key are required")
        existing = self.store.get(operation_key)
        if existing:
            return existing["result"]
        try:
            result = self.adapter.mutate(action, template, payload, operation_key)
        except UnknownMutation:
            reconciled = self.adapter.reconcile(operation_key)
            if reconciled is None:
                raise
            result = reconciled
        self.store.put(operation_key, actor, template_id, payload, "STAGED" if not self.promotion_enabled else "PROMOTED", result)
        return result
