"""Typed, bounded Server Health Watch state and authorization service.

This module is intentionally independent of n8n. HADES owns identity,
resource authorization, lifecycle semantics, transition state, and local
notification history; n8n is only a canonical execution runner for a
workflow that HADES has already authorized.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


HEALTH_STATES = frozenset({"UP", "DOWN", "SOURCE_UNAVAILABLE", "UNKNOWN", "AUTHORIZATION_LOST"})
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 1440
LOCAL_NOTIFICATION_POLICY = "hades-local"


class HealthWatchError(ValueError):
    """Expected, user-facing health-watch contract failure."""


class HealthWatchAuthorizationError(HealthWatchError):
    """Current subject or resource authority does not permit the operation."""


class HealthWatchNotFound(HealthWatchError):
    """The canonical automation is absent."""


@dataclass(frozen=True)
class HealthSource:
    """Trusted source metadata; callers cannot supply arbitrary URLs."""

    resource_id: str
    display_name: str
    url: str

    def __post_init__(self) -> None:
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HealthWatchError("health source must be an HTTP(S) endpoint")


@dataclass(frozen=True)
class HealthWatchSpec:
    automation_id: str
    owner: str
    resource_id: str
    display_name: str
    interval_minutes: int
    notification_policy: str = LOCAL_NOTIFICATION_POLICY
    shared_subjects: tuple[str, ...] = ()

    def validate(self, sources: Mapping[str, HealthSource]) -> None:
        if not _valid_id(self.automation_id) or not _valid_id(self.owner):
            raise HealthWatchError("automation identity is invalid")
        if not _valid_id(self.resource_id) or self.resource_id not in sources:
            raise HealthWatchError("resource is not an authorized health source")
        if not 1 <= len(self.display_name.strip()) <= 64:
            raise HealthWatchError("display name must contain 1 to 64 characters")
        if not MIN_INTERVAL_MINUTES <= self.interval_minutes <= MAX_INTERVAL_MINUTES:
            raise HealthWatchError(
                f"check interval must be between {MIN_INTERVAL_MINUTES} and "
                f"{MAX_INTERVAL_MINUTES} minutes"
            )
        if self.notification_policy != LOCAL_NOTIFICATION_POLICY:
            raise HealthWatchError("only HADES-local notifications are authorized")
        if len(self.shared_subjects) > 20 or any(not _valid_id(item) for item in self.shared_subjects):
            raise HealthWatchError("shared subject list is invalid or too large")


def _valid_id(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", str(value or "")))


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _now() -> int:
    return int(time.time())


class HealthWatchStore:
    """Private SQLite custody for automation metadata and bounded history."""

    def __init__(self, path: str):
        if not path:
            raise ValueError("health-watch state path is required")
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and (self.path.is_symlink() or self.path.stat().st_mode & 0o077):
            raise HealthWatchError("health-watch state must be a private regular file")
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5, isolation_level="IMMEDIATE")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS automations (
                    automation_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL,
                    notification_policy TEXT NOT NULL,
                    shared_subjects TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    state_reason TEXT NOT NULL,
                    last_run INTEGER,
                    last_transition INTEGER,
                    last_result TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_previews (
                    preview_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    request_key TEXT PRIMARY KEY,
                    automation_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id TEXT NOT NULL,
                    observed_at INTEGER NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    result TEXT NOT NULL,
                    notification_sent INTEGER NOT NULL,
                    execution_id TEXT NOT NULL,
                    FOREIGN KEY (automation_id) REFERENCES automations(automation_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    delivered INTEGER NOT NULL,
                    FOREIGN KEY (automation_id) REFERENCES automations(automation_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    automation_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    detail TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS transitions_by_automation
                    ON transitions(automation_id, observed_at DESC);
                CREATE INDEX IF NOT EXISTS notifications_by_automation
                    ON notifications(automation_id, created_at DESC);
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(automations)")}
            if "workflow_id" not in columns:
                db.execute("ALTER TABLE automations ADD COLUMN workflow_id TEXT NOT NULL DEFAULT ''")
        os.chmod(self.path, 0o600)

    def create(self, spec: HealthWatchSpec, request_key: str, actor: str) -> dict[str, Any]:
        now = _now()
        with self._lock, self._connect() as db:
            existing = db.execute(
                "SELECT automation_id FROM idempotency WHERE request_key = ?", (request_key,)
            ).fetchone()
            if existing:
                row = db.execute(
                    "SELECT * FROM automations WHERE automation_id = ?", (existing["automation_id"],)
                ).fetchone()
                if row:
                    return dict(row)
            # A browser double-submit can produce two distinct preview IDs
            # before either confirmation reaches the store. Treat an already
            # active equivalent watch as the same logical resource, even when
            # the request keys differ. This closes the gap between request-key
            # idempotency and semantic idempotency at the canonical boundary.
            candidates = db.execute(
                "SELECT * FROM automations WHERE owner = ? AND resource_id = ? "
                "AND display_name = ? AND enabled = 1 "
                "ORDER BY created_at, automation_id",
                (spec.owner, spec.resource_id, spec.display_name.strip()),
            ).fetchall()
            wanted_shared = _json(list(spec.shared_subjects))
            for row in candidates:
                if row["notification_policy"] == spec.notification_policy and row["shared_subjects"] == wanted_shared:
                    # A prior double-submit may have left sibling create
                    # previews behind after one was consumed. They must not
                    # be allowed to claim a later bare confirmation.
                    db.execute("DELETE FROM pending_previews WHERE actor = ?", (actor,))
                    db.execute(
                        "INSERT OR IGNORE INTO idempotency(request_key, automation_id, created_at) VALUES (?, ?, ?)",
                        (request_key, row["automation_id"], now),
                    )
                    return self._public(dict(row))
            db.execute(
                """INSERT INTO automations
                (automation_id, owner, resource_id, display_name, interval_minutes,
                 notification_policy, shared_subjects, enabled, state, state_reason,
                 last_run, last_transition, last_result, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'UNKNOWN', 'not yet checked', NULL, NULL,
                        'NOT_RUN', 1, ?, ?)""",
                (spec.automation_id, spec.owner, spec.resource_id, spec.display_name.strip(),
                 spec.interval_minutes, spec.notification_policy, _json(list(spec.shared_subjects)), now, now),
            )
            db.execute(
                "INSERT INTO idempotency(request_key, automation_id, created_at) VALUES (?, ?, ?)",
                (request_key, spec.automation_id, now),
            )
            self._audit(db, spec.automation_id, actor, "create", {"version": 1})
            row = db.execute("SELECT * FROM automations WHERE automation_id = ?", (spec.automation_id,)).fetchone()
            return self._public(dict(row))

    def get(self, automation_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM automations WHERE automation_id = ?", (automation_id,)).fetchone()
        if not row:
            raise HealthWatchNotFound("automation does not exist")
        return self._public(dict(row))

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM automations ORDER BY created_at, automation_id").fetchall()
        return [self._public(dict(row)) for row in rows]

    def update(self, automation_id: str, actor: str, **changes: Any) -> dict[str, Any]:
        allowed = {"display_name", "interval_minutes", "shared_subjects", "enabled", "state_reason"}
        if not set(changes).issubset(allowed):
            raise HealthWatchError("unsupported health-watch edit")
        if not changes:
            return self.get(automation_id)
        now = _now()
        assignments = ", ".join(f"{key} = ?" for key in changes)
        values = []
        for key, value in changes.items():
            values.append(_json(value) if key == "shared_subjects" else value)
        values.extend([now, automation_id])
        with self._lock, self._connect() as db:
            current = db.execute("SELECT version FROM automations WHERE automation_id = ?", (automation_id,)).fetchone()
            if not current:
                raise HealthWatchNotFound("automation does not exist")
            db.execute(
                f"UPDATE automations SET {assignments}, version = version + 1, updated_at = ? WHERE automation_id = ?",
                values,
            )
            self._audit(db, automation_id, actor, "edit", {"fields": sorted(changes)})
        return self.get(automation_id)

    def set_state(self, automation_id: str, state: str, reason: str, result: str, execution_id: str = "") -> dict[str, Any]:
        if state not in HEALTH_STATES:
            raise HealthWatchError("invalid health state")
        now = _now()
        with self._lock, self._connect() as db:
            current = db.execute("SELECT state FROM automations WHERE automation_id = ?", (automation_id,)).fetchone()
            if not current:
                raise HealthWatchNotFound("automation does not exist")
            previous = str(current["state"])
            changed = previous != state
            db.execute(
                """UPDATE automations SET state = ?, state_reason = ?, last_run = ?,
                last_transition = ?, last_result = ?, updated_at = ? WHERE automation_id = ?""",
                (state, reason, now, now if changed else None, result, now, automation_id),
            )
            notification_sent = int(changed and state in {"DOWN", "UP", "SOURCE_UNAVAILABLE"}
                                    and not (previous == "UNKNOWN" and state == "UP"))
            db.execute(
                """INSERT INTO transitions
                (automation_id, observed_at, from_state, to_state, reason, result,
                 notification_sent, execution_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (automation_id, now, previous, state, reason, result, notification_sent, execution_id),
            )
            if notification_sent:
                row = db.execute(
                    "SELECT owner, display_name, shared_subjects FROM automations WHERE automation_id = ?",
                    (automation_id,),
                ).fetchone()
                # Owner is always a recipient; shared subjects receive only
                # current-authority-filtered notifications at read time.
                recipients = [str(row["owner"])] + [
                    item for item in json.loads(row["shared_subjects"])
                    if item != row["owner"]
                ]
                message = _notification_message(row["display_name"], state)
                for recipient in recipients:
                    db.execute(
                        """INSERT INTO notifications
                        (automation_id, recipient, created_at, state, message, delivered)
                        VALUES (?, ?, ?, ?, ?, 1)""",
                        (automation_id, recipient, now, state, message),
                    )
            current = db.execute("SELECT * FROM automations WHERE automation_id = ?", (automation_id,)).fetchone()
            return self._public(dict(current))

    def history(self, automation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise HealthWatchError("history limit is out of bounds")
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT observed_at, from_state, to_state, reason, result, notification_sent, execution_id "
                "FROM transitions WHERE automation_id = ? ORDER BY transition_id DESC LIMIT ?",
                (automation_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def notifications(self, automation_id: str, recipient: str, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise HealthWatchError("notification limit is out of bounds")
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT created_at, state, message, delivered FROM notifications "
                "WHERE automation_id = ? AND recipient = ? ORDER BY created_at DESC LIMIT ?",
                (automation_id, recipient, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, automation_id: str, actor: str) -> bool:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT 1 FROM automations WHERE automation_id = ?", (automation_id,)).fetchone()
            if not row:
                return False
            self._audit(db, automation_id, actor, "delete", {})
            db.execute("DELETE FROM automations WHERE automation_id = ?", (automation_id,))
            return True

    def bind_workflow(self, automation_id: str, workflow_id: str, actor: str) -> dict[str, Any]:
        if not workflow_id:
            raise HealthWatchError("runner workflow identity is required")
        with self._lock, self._connect() as db:
            if not db.execute("SELECT 1 FROM automations WHERE automation_id = ?", (automation_id,)).fetchone():
                raise HealthWatchNotFound("automation does not exist")
            db.execute("UPDATE automations SET workflow_id = ?, updated_at = ? WHERE automation_id = ?", (workflow_id, _now(), automation_id))
            self._audit(db, automation_id, actor, "bind-runner", {"workflow_id": workflow_id})
        return self.get(automation_id)

    def store_preview(self, preview_id: str, actor: str, payload: Mapping[str, Any], expires_at: int) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM pending_previews WHERE expires_at <= ?", (_now(),))
            db.execute(
                "INSERT INTO pending_previews(preview_id, actor, payload, expires_at) VALUES (?, ?, ?, ?)",
                (preview_id, actor, _json(payload), expires_at),
            )

    def consume_preview(self, preview_id: str, actor: str) -> dict[str, Any]:
        with self._lock, self._connect() as db:
            row = db.execute(
                "SELECT payload, expires_at FROM pending_previews WHERE preview_id = ? AND actor = ?",
                (preview_id, actor),
            ).fetchone()
            if not row or row["expires_at"] <= _now():
                raise HealthWatchError("preview is expired or not valid for this subject")
            db.execute("DELETE FROM pending_previews WHERE preview_id = ?", (preview_id,))
        return json.loads(row["payload"])

    def latest_preview(self, actor: str) -> dict[str, Any] | None:
        """Return the newest unexpired preview for a subject, including its ID."""
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM pending_previews WHERE expires_at <= ?", (_now(),))
            rows = db.execute(
                "SELECT preview_id, payload FROM pending_previews WHERE actor = ? ORDER BY rowid DESC",
                (actor,),
            ).fetchall()
        if not rows:
            return None
        decoded = [(row, json.loads(row["payload"])) for row in rows]
        # Action confirmations are more specific than an older create
        # preview. Prefer them so a bare `yes` cannot replay stale creation
        # state after the user just requested share/revoke/control.
        row, payload = next(
            ((row, payload) for row, payload in decoded if payload.get("kind") == "action"),
            decoded[0],
        )
        payload["preview_id"] = str(row["preview_id"])
        return payload

    def clear_previews(self, actor: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM pending_previews WHERE actor = ?", (actor,))

    def _audit(self, db: sqlite3.Connection, automation_id: str, actor: str, action: str, detail: Mapping[str, Any]) -> None:
        db.execute(
            "INSERT INTO audit(automation_id, actor, action, created_at, detail) VALUES (?, ?, ?, ?, ?)",
            (automation_id, actor, action, _now(), _json(detail)),
        )

    @staticmethod
    def _public(row: dict[str, Any]) -> dict[str, Any]:
        row["shared_subjects"] = tuple(json.loads(row["shared_subjects"]))
        row["enabled"] = bool(row["enabled"])
        return row


def _notification_message(display_name: str, state: str) -> str:
    if state == "DOWN":
        return f"{display_name} is offline."
    if state == "UP":
        return f"{display_name} is back online."
    if state == "SOURCE_UNAVAILABLE":
        return f"HADES couldn't check {display_name} because its health service is temporarily unavailable."
    return f"HADES could not determine the state of {display_name}."


class HealthWatchService:
    """Authorization and transition facade for one typed watch family."""

    def __init__(
        self,
        store: HealthWatchStore,
        sources: Mapping[str, HealthSource],
        *,
        resource_authorizer: Callable[[str, str], bool] | None = None,
        fetcher: Callable[[HealthSource], tuple[str, str]] | None = None,
    ):
        self.store = store
        self.sources = dict(sources)
        self.resource_authorizer = resource_authorizer or (lambda actor, resource: True)
        self.fetcher = fetcher or _fetch_health_source

    def preview(
        self,
        actor: str,
        *,
        owner: bool,
        resource_id: str,
        display_name: str,
        interval_minutes: int,
        shared_subjects: Sequence[str] = (),
    ) -> dict[str, Any]:
        if not owner:
            raise HealthWatchAuthorizationError("only the owner may create a health watch")
        if not self.resource_authorizer(actor, resource_id):
            raise HealthWatchAuthorizationError("actor cannot access the selected resource")
        automation_id = "epsilon-shw-" + secrets.token_hex(8)
        spec = HealthWatchSpec(
            automation_id, actor, resource_id, display_name, interval_minutes,
            shared_subjects=tuple(dict.fromkeys(shared_subjects)),
        )
        spec.validate(self.sources)
        preview_id = secrets.token_urlsafe(18)
        payload = {
            "kind": "create",
            "automation_id": automation_id,
            "owner": actor,
            "resource_id": resource_id,
            "display_name": display_name.strip(),
            "interval_minutes": interval_minutes,
            "notification_policy": LOCAL_NOTIFICATION_POLICY,
            "shared_subjects": list(spec.shared_subjects),
            "preview_hash": _preview_hash(spec),
        }
        self.store.store_preview(preview_id, actor, payload, _now() + 600)
        source = self.sources[resource_id]
        return {
            "preview_id": preview_id,
            "schema": "hades-automation/v1",
            "template": "Server Health Watch",
            "automation_id": automation_id,
            "target": source.display_name,
            "display_name": spec.display_name,
            "owner": actor,
            "interval_minutes": interval_minutes,
            "notification_policy": "HADES-local only",
            "shared_subjects": list(spec.shared_subjects),
            "read_only": True,
            "can_modify_resource": False,
            "requires_confirmation": True,
        }

    def confirm_create(self, actor: str, preview_id: str, *, confirmed: bool, request_key: str) -> dict[str, Any]:
        if not confirmed:
            raise HealthWatchError("creating a health watch requires explicit confirmation")
        payload = self.store.consume_preview(preview_id, actor)
        spec = HealthWatchSpec(
            payload["automation_id"], payload["owner"], payload["resource_id"],
            payload["display_name"], int(payload["interval_minutes"]),
            payload["notification_policy"], tuple(payload["shared_subjects"]),
        )
        spec.validate(self.sources)
        if _preview_hash(spec) != payload["preview_hash"]:
            raise HealthWatchError("confirmation does not match the current preview")
        return self.store.create(spec, request_key, actor)

    def visible(self, actor: str, owner: bool) -> list[dict[str, Any]]:
        result = []
        for item in self.store.list_all():
            is_owner = owner and item["owner"] == actor
            shared = actor in item["shared_subjects"]
            if not (is_owner or shared):
                continue
            if not self.resource_authorizer(actor, item["resource_id"]):
                if is_owner:
                    self.store.set_state(
                        item["automation_id"], "AUTHORIZATION_LOST",
                        "resource authorization lost", "AUTHORIZATION_LOST",
                    )
                    self.store.update(
                        item["automation_id"], actor,
                        enabled=False, state_reason="resource authorization lost",
                    )
                    result.append(self.store.get(item["automation_id"]))
                continue
            public = dict(item)
            public.pop("owner", None) if not is_owner else None
            if not is_owner:
                public.pop("resource_id", None)
            result.append(public)
        return result

    def history_for(self, actor: str, *, owner: bool, automation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        item = self._authorized_item(actor, owner, automation_id)
        if not self.resource_authorizer(actor, item["resource_id"]):
            raise HealthWatchAuthorizationError("resource authorization is no longer available")
        return self.store.history(automation_id, limit)

    def notifications_for(self, actor: str, *, owner: bool, automation_id: str, limit: int = 20) -> list[dict[str, Any]]:
        item = self._authorized_item(actor, owner, automation_id)
        if not self.resource_authorizer(actor, item["resource_id"]):
            raise HealthWatchAuthorizationError("resource authorization is no longer available")
        return self.store.notifications(automation_id, actor, limit)

    def _authorized_item(self, actor: str, owner: bool, automation_id: str) -> dict[str, Any]:
        item = self.store.get(automation_id)
        if owner and item["owner"] == actor:
            return item
        if actor in item["shared_subjects"]:
            return item
        raise HealthWatchAuthorizationError("automation is not shared with this subject")

    def control(self, actor: str, *, owner: bool, automation_id: str, action: str, confirmed: bool) -> dict[str, Any]:
        if not owner:
            raise HealthWatchAuthorizationError("shared health watches are view-only in this canary")
        item = self.store.get(automation_id)
        if item["owner"] != actor:
            raise HealthWatchAuthorizationError("only the owner may control this health watch")
        if not confirmed:
            raise HealthWatchError("health-watch control requires explicit confirmation")
        # Removing the automation does not read or mutate the monitored
        # resource, so an owner may clean up a watch after resource authority
        # is lost.
        if action == "delete":
            self.store.delete(automation_id, actor)
            return {"status": "DELETED", "automation_id": automation_id}
        if not self.resource_authorizer(actor, item["resource_id"]):
            self.store.set_state(automation_id, "AUTHORIZATION_LOST", "resource authorization lost", "AUTHORIZATION_LOST")
            raise HealthWatchAuthorizationError("resource authorization is no longer available")
        if action == "pause":
            return self.store.update(automation_id, actor, enabled=False)
        if action == "resume":
            return self.store.update(automation_id, actor, enabled=True)
        if action == "run":
            return self.observe(automation_id, actor=actor)
        raise HealthWatchError("unsupported health-watch control")

    def edit(self, actor: str, *, owner: bool, automation_id: str, confirmed: bool, **changes: Any) -> dict[str, Any]:
        if not owner or not confirmed:
            raise HealthWatchAuthorizationError("bounded health-watch edits require owner confirmation")
        item = self.store.get(automation_id)
        if item["owner"] != actor:
            raise HealthWatchAuthorizationError("only the owner may edit this health watch")
        if "resource_id" in changes:
            raise HealthWatchError("changing the monitored resource requires a new preview")
        if "interval_minutes" in changes:
            HealthWatchSpec(
                item["automation_id"], item["owner"], item["resource_id"],
                str(changes.get("display_name", item["display_name"])),
                int(changes["interval_minutes"]),
                item["notification_policy"], tuple(changes.get("shared_subjects", item["shared_subjects"])),
            ).validate(self.sources)
        return self.store.update(automation_id, actor, **changes)

    def observe(self, automation_id: str, *, actor: str = "", execution_id: str = "") -> dict[str, Any]:
        item = self.store.get(automation_id)
        if actor and not self.resource_authorizer(actor, item["resource_id"]):
            self.store.set_state(automation_id, "AUTHORIZATION_LOST", "resource authorization lost", "AUTHORIZATION_LOST", execution_id)
            raise HealthWatchAuthorizationError("resource authorization is no longer available")
        source = self.sources.get(item["resource_id"])
        if source is None:
            return self.store.set_state(automation_id, "SOURCE_UNAVAILABLE", "health source is not configured", "SOURCE_UNAVAILABLE", execution_id)
        state, reason = self.fetcher(source)
        return self.store.set_state(automation_id, state, reason, state, execution_id)

    def reconcile_execution(self, automation_id: str, execution: Mapping[str, Any]) -> dict[str, Any] | None:
        """Project only the typed n8n result into HADES-owned state."""
        state = execution.get("hades_state") or execution.get("observed_state")
        if state not in HEALTH_STATES:
            return None
        reason = str(execution.get("hades_reason") or "canonical health result")[:200]
        return self.store.set_state(
            automation_id, state, reason, state,
            str(execution.get("executionId") or "")[:128],
        )


def _preview_hash(spec: HealthWatchSpec) -> str:
    payload = {
        "owner": spec.owner, "resource_id": spec.resource_id, "display_name": spec.display_name,
        "interval_minutes": spec.interval_minutes, "notification_policy": spec.notification_policy,
        "shared_subjects": list(spec.shared_subjects),
    }
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def build_n8n_workflow(spec: HealthWatchSpec, source: HealthSource, template_path: str | None = None) -> dict[str, Any]:
    """Instantiate only the checked-in Server Health Watch graph.

    This is a typed template substitution, not a user/model-supplied graph
    builder. The graph remains inactive until HADES explicitly enables it.
    """
    path = Path(template_path) if template_path else (
        Path(__file__).resolve().parents[2] / "config" / "epsilon-workflows" / "server-health-watch.json"
    )
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HealthWatchError("typed Server Health Watch template is unavailable") from exc
    if not isinstance(workflow, dict) or workflow.get("id") != "epsilon-server-health-watch-core":
        raise HealthWatchError("typed Server Health Watch template is invalid")
    workflow["id"] = spec.automation_id
    workflow["name"] = spec.display_name
    workflow["active"] = False
    workflow["tags"] = [
        {"name": "hades-template:shw"},
        {"name": "hades-owner:owner"},
        {"name": "hades-approved:true"},
        {"name": "hades-trigger:schedule"},
    ]

    def replace(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("epsilon-server-health-watch-core", spec.automation_id).replace(
                "http://hades-core.local:3000/health", source.url
            )
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(workflow)


def _fetch_health_source(source: HealthSource) -> tuple[str, str]:
    request = urllib.request.Request(source.url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                return "SOURCE_UNAVAILABLE", f"health source returned HTTP {response.status}"
            payload = json.loads(response.read(65536))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return "SOURCE_UNAVAILABLE", "health source could not be reached or parsed"
    if isinstance(payload, Mapping) and payload.get("state") in {"UP", "DOWN"}:
        return str(payload["state"]), "canonical health state"
    if isinstance(payload, Mapping) and payload.get("status") is True:
        return "UP", "canonical HADES health status"
    if isinstance(payload, Mapping) and payload.get("status") is False:
        return "DOWN", "canonical HADES health status"
    return "UNKNOWN", "health source returned no canonical state"
