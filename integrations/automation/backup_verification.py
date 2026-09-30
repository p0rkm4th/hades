"""Typed verification of the small, operator-owned HADES backup set.

This module deliberately verifies evidence, not job intent.  Target paths and
verification methods are fixed by the operator manifest; callers cannot supply
paths, shell commands, hosts, or SSH arguments.
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping


BACKUP_STATES = frozenset({"HEALTHY", "STALE", "FAILED", "MISSING", "SOURCE_UNAVAILABLE", "UNKNOWN"})

BACKUP_TARGETS = {
    "hades-repository": {"label": "HADES repository backup", "endpoint": "http://host.docker.internal:8643/v1/epsilon/backup/hades"},
    "infrastructure-repository": {"label": "Infrastructure repository backup", "endpoint": "http://host.docker.internal:8643/v1/epsilon/backup/infra"},
}


@dataclass(frozen=True)
class BackupTarget:
    target_id: str
    label: str
    artifact: Path
    checksum: str
    custody: str
    max_age_seconds: int
    kind: str = "file"


@dataclass(frozen=True)
class BackupObservation:
    target_id: str
    state: str
    reason: str
    observed_at: str
    artifact_mtime: str | None = None
    checksum_verified: bool = False
    validity_verified: bool = False


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _bundle_valid(path: Path) -> tuple[bool, str]:
    # git is a fixed verifier selected by the typed target kind, never input.
    try:
        result = subprocess.run(
            ["git", "bundle", "verify", str(path)],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"bundle verifier unavailable: {type(exc).__name__}"
    if result.returncode:
        return False, "git bundle verification failed"
    return True, "git bundle verified"


def verify_target(target: BackupTarget, *, now: float, exists: Callable[[Path], bool] = Path.exists) -> BackupObservation:
    observed = _iso(now)
    path = target.artifact
    if not exists(path):
        return BackupObservation(target.target_id, "MISSING", "expected backup artifact is absent", observed)
    try:
        stat = path.stat()
        if not path.is_file() or stat.st_size <= 0:
            return BackupObservation(target.target_id, "FAILED", "backup artifact is empty or not a regular file", observed)
        if now - stat.st_mtime > target.max_age_seconds:
            return BackupObservation(target.target_id, "STALE", "backup artifact exceeded its staleness threshold", observed, _iso(stat.st_mtime))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        return BackupObservation(target.target_id, "SOURCE_UNAVAILABLE", f"backup custody could not be read: {type(exc).__name__}", observed)
    if digest.lower() != target.checksum.lower():
        return BackupObservation(target.target_id, "FAILED", "backup checksum does not match the expected digest", observed, _iso(stat.st_mtime), False)
    valid, reason = (True, "artifact verified")
    if target.kind == "git-bundle":
        valid, reason = _bundle_valid(path)
    if not valid:
        return BackupObservation(target.target_id, "FAILED", reason, observed, _iso(stat.st_mtime), True, False)
    return BackupObservation(target.target_id, "HEALTHY", reason, observed, _iso(stat.st_mtime), True, True)


def verify_all(targets: Iterable[BackupTarget], *, now: float) -> tuple[BackupObservation, ...]:
    return tuple(verify_target(target, now=now) for target in targets)


def build_n8n_workflow(automation_id: str, target_id: str, interval_minutes: int, *, template_path: str | None = None) -> dict[str, object]:
    """Instantiate the fixed backup graph; target input selects an allowlist entry only."""
    if target_id not in BACKUP_TARGETS:
        raise ValueError("backup target is not in the operator allowlist")
    if not 60 <= interval_minutes <= 10080:
        raise ValueError("backup schedule is outside the bounded interval")
    path = Path(template_path) if template_path else Path(__file__).resolve().parents[2] / "config" / "epsilon-workflows" / "backup-verification-n8n.json"
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("typed backup workflow template is unavailable") from exc
    if workflow.get("id") != "hades-backup-verification":
        raise ValueError("typed backup workflow template is invalid")
    workflow["id"] = automation_id
    workflow["name"] = f"HADES {BACKUP_TARGETS[target_id]['label']}"
    workflow["active"] = False
    workflow["tags"] = [
        {"name": "hades-template:bkp"}, {"name": "hades-owner:owner"},
        {"name": "hades-approved:true"}, {"name": "hades-trigger:schedule"},
    ]
    for node in workflow.get("nodes", []):
        if node.get("name") == "HADES-local backup verification source":
            node.setdefault("parameters", {})["url"] = BACKUP_TARGETS[target_id]["endpoint"]
        if node.get("name") == "Bounded backup schedule":
            node.setdefault("parameters", {}).setdefault("rule", {}).setdefault("interval", [{}])[0]["minutesInterval"] = interval_minutes
        if node.get("name") == "HADES-local run-now trigger":
            node.setdefault("parameters", {})["path"] = automation_id
            node["webhookId"] = automation_id
    return workflow


def notification_transition(previous: str | None, current: str) -> bool:
    return (previous, current) in {
        ("HEALTHY", "FAILED"), ("HEALTHY", "STALE"),
        ("FAILED", "HEALTHY"), ("STALE", "HEALTHY"),
    }


@dataclass(frozen=True)
class BackupVerificationSpec:
    automation_id: str
    owner: str
    schedule: str = "daily"
    staleness_threshold_seconds: int = 7 * 86400
    notification_behavior: str = "hades-local-failure-only"
    enabled: bool = True

    def validate(self) -> None:
        if not self.automation_id or not self.owner:
            raise ValueError("backup verification identity is required")
        if self.schedule != "daily":
            raise ValueError("backup verification currently supports a daily schedule only")
        if self.staleness_threshold_seconds <= 0:
            raise ValueError("staleness threshold must be positive")
        if self.notification_behavior != "hades-local-failure-only":
            raise ValueError("only HADES-local failure notifications are authorized")


class BackupVerificationService:
    """Small private lifecycle/state boundary for a typed backup check."""

    def __init__(self, state_file: str, spec: BackupVerificationSpec):
        spec.validate()
        self.spec = spec
        self.path = Path(state_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS backup_checks (automation_id TEXT PRIMARY KEY, state TEXT NOT NULL, reason TEXT NOT NULL, observed_at TEXT NOT NULL, last_good TEXT, notifications INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS backup_notifications (notification_id INTEGER PRIMARY KEY AUTOINCREMENT, automation_id TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL)")
        self.path.chmod(0o600)

    def observe(self, observations: Iterable[BackupObservation]) -> dict[str, object]:
        rows = tuple(observations)
        if not rows:
            raise ValueError("backup verification requires canonical observations")
        precedence = ("SOURCE_UNAVAILABLE", "FAILED", "MISSING", "STALE", "UNKNOWN", "HEALTHY")
        state = next((item for item in precedence if any(row.state == item for row in rows)), "UNKNOWN")
        reason = next(row.reason for row in rows if row.state == state)
        observed_at = max(row.observed_at for row in rows)
        with sqlite3.connect(self.path) as db:
            old = db.execute("SELECT state, last_good, notifications FROM backup_checks WHERE automation_id = ?", (self.spec.automation_id,)).fetchone()
            previous = old[0] if old else None
            notify = notification_transition(previous, state)
            last_good = (old[1] if old else None) or (observed_at if state == "HEALTHY" else None)
            count = (old[2] if old else 0) + (1 if notify else 0)
            db.execute("INSERT INTO backup_checks(automation_id,state,reason,observed_at,last_good,notifications) VALUES(?,?,?,?,?,?) ON CONFLICT(automation_id) DO UPDATE SET state=excluded.state, reason=excluded.reason, observed_at=excluded.observed_at, last_good=excluded.last_good, notifications=excluded.notifications", (self.spec.automation_id, state, reason, observed_at, last_good, count))
            if notify:
                db.execute("INSERT INTO backup_notifications(automation_id,state,message,created_at) VALUES(?,?,?,?)", (self.spec.automation_id, state, f"{self.spec.automation_id}: backup state changed to {state}: {reason}", observed_at))
        return {"state": state, "reason": reason, "notify": notify, "last_good": last_good, "notifications": count}

    def status(self) -> dict[str, object]:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT state, reason, observed_at, last_good, notifications FROM backup_checks WHERE automation_id = ?", (self.spec.automation_id,)).fetchone()
        if not row:
            return {"state": "UNKNOWN", "reason": "backup check has not run", "last_good": None, "notifications": 0}
        return {"state": row[0], "reason": row[1], "observed_at": row[2], "last_good": row[3], "notifications": row[4]}

    def notifications(self, limit: int = 20) -> list[dict[str, object]]:
        if not 1 <= limit <= 100:
            raise ValueError("notification limit is out of bounds")
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT state,message,created_at FROM backup_notifications WHERE automation_id=? ORDER BY notification_id DESC LIMIT ?", (self.spec.automation_id, limit)).fetchall()
        return [{"state": row[0], "message": row[1], "created_at": row[2]} for row in rows]

    def reconcile_execution(self, execution: Mapping[str, object]) -> dict[str, object] | None:
        """Project only the bounded n8n result; raw node data never enters state."""
        state = execution.get("hades_state")
        if state not in BACKUP_STATES:
            return None
        observed = str(execution.get("observed_at") or time.time())
        observation = BackupObservation("aggregate", str(state), str(execution.get("hades_reason") or "canonical backup result"), observed)
        return self.observe((observation,))
