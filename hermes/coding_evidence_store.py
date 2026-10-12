"""Private host-side persistence for verified coding-turn test receipts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import tempfile
import time
from pathlib import Path

from hermes.workspace_contract import TestEvidence, WorkspaceBinding, WorkspaceEvidenceError

_MAX_BYTES = 16 * 1024
_MAX_AGE_SECONDS = 4 * 60 * 60
_HEAD = re.compile(r"^[0-9a-f]{40,64}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def _receipt_path(binding: WorkspaceBinding, session_id: str) -> Path:
    if not binding.subject or "\0" in binding.subject or not session_id or "\0" in session_id:
        raise WorkspaceEvidenceError("coding evidence session identity is incomplete")
    key = hashlib.sha256((binding.subject + "\0" + session_id).encode()).hexdigest()
    workspace = binding.root.resolve(strict=True)
    if workspace.name != key or binding.repository.resolve(strict=True) != workspace:
        raise WorkspaceEvidenceError("coding evidence workspace does not match its session")
    parent = workspace.parent
    try:
        info = parent.stat()
    except OSError as exc:
        raise WorkspaceEvidenceError("coding evidence directory is unavailable") from exc
    if not parent.is_dir() or info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o077:
        raise WorkspaceEvidenceError("coding evidence directory is not private")
    return parent / (key + ".test-evidence.json")


def _data(evidence: TestEvidence) -> dict:
    return {
        "subject": evidence.subject,
        "workspace": str(evidence.workspace),
        "repository": str(evidence.repository),
        "branch": evidence.branch,
        "head": evidence.head,
        "paths": sorted(evidence.paths),
        "source_fingerprint": evidence.source_fingerprint,
        "path_fingerprints": dict(evidence.path_fingerprints),
        "command": evidence.command,
        "exit_code": evidence.exit_code,
        "task_id": evidence.task_id,
        "session_id": evidence.session_id,
        "turn_id": evidence.turn_id,
        "tool_call_id": evidence.tool_call_id,
    }


def store_test_evidence(
    binding: WorkspaceBinding,
    session_id: str,
    evidence: TestEvidence,
    *,
    now: float | None = None,
) -> None:
    """Atomically store a trusted receipt outside the worker-writable tree.

    Callers hold ``workspace_lease`` so test and commit turns serialize.
    """
    path = _receipt_path(binding, session_id)
    if (
        not evidence.passed
        or evidence.subject != binding.subject
        or evidence.workspace != binding.root
        or evidence.repository != binding.repository
        or evidence.session_id != session_id
        or not _HEAD.fullmatch(evidence.head)
        or not _FINGERPRINT.fullmatch(evidence.source_fingerprint)
        or not evidence.paths
        or set(evidence.path_fingerprints) != set(evidence.paths)
        or any(not _FINGERPRINT.fullmatch(value) for value in evidence.path_fingerprints.values())
        or len(evidence.paths) > 256
        or len(evidence.command) > 2048
    ):
        raise WorkspaceEvidenceError("coding test receipt is not bound to this session")
    payload = json.dumps(
        {"version": 2, "created_at": float(time.time() if now is None else now),
         "evidence": _data(evidence)},
        separators=(",", ":"),
    ).encode()
    if len(payload) > _MAX_BYTES:
        raise WorkspaceEvidenceError("coding test receipt is oversized")
    fd, temporary = tempfile.mkstemp(prefix=".coding-evidence-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = ""
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def load_test_evidence(
    binding: WorkspaceBinding,
    session_id: str,
    *,
    now: float | None = None,
) -> TestEvidence | None:
    """Load only a recent receipt owned by this authenticated workspace session."""
    path = _receipt_path(binding, session_id)
    try:
        info = path.lstat()
        if (
            stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or info.st_uid not in {0, os.geteuid()} or info.st_mode & 0o077
            or info.st_size > _MAX_BYTES
        ):
            return None
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            envelope = json.loads(stream.read(_MAX_BYTES + 1))
        data = envelope["evidence"]
        created = float(envelope["created_at"])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, TypeError, KeyError):
        return None
    clock = time.time() if now is None else now
    required_strings = (
        "subject", "branch", "head", "source_fingerprint", "command",
        "task_id", "session_id", "turn_id", "tool_call_id",
    )
    if (
        not isinstance(data, dict)
        or envelope.get("version") != 2
        or not math.isfinite(created)
        or created > clock + 60
        or clock - created > _MAX_AGE_SECONDS
        or data.get("subject") != binding.subject
        or data.get("workspace") != str(binding.root)
        or data.get("repository") != str(binding.repository)
        or data.get("session_id") != session_id
        or not all(isinstance(data.get(key), str) and data[key] for key in required_strings)
        or not isinstance(data.get("paths"), list)
        or len(data["paths"]) > 256
        or any(not isinstance(item, str) for item in data["paths"])
        or not isinstance(data.get("path_fingerprints"), dict)
        or set(data["path_fingerprints"]) != set(data["paths"])
        or any(not isinstance(value, str) or not _FINGERPRINT.fullmatch(value)
               for value in data["path_fingerprints"].values())
        or isinstance(data.get("exit_code"), bool)
        or not isinstance(data.get("exit_code"), int)
    ):
        return None
    try:
        evidence = TestEvidence(
            subject=data["subject"], workspace=binding.root, repository=binding.repository,
            branch=data["branch"], head=data["head"], paths=frozenset(data["paths"]),
            source_fingerprint=data["source_fingerprint"],
            path_fingerprints=dict(data["path_fingerprints"]), command=data["command"],
            exit_code=data["exit_code"], output="", task_id=data["task_id"],
            session_id=data["session_id"], turn_id=data["turn_id"],
            tool_call_id=data["tool_call_id"],
        )
    except (TypeError, ValueError):
        return None
    if (
        not evidence.passed or not _HEAD.fullmatch(evidence.head)
        or not _FINGERPRINT.fullmatch(evidence.source_fingerprint)
        or len(evidence.command) > 2048
    ):
        return None
    return evidence


def clear_test_evidence(binding: WorkspaceBinding, session_id: str) -> None:
    """Remove a session receipt after a source mutation or verified commit."""
    path = _receipt_path(binding, session_id)
    try:
        info = path.lstat()
        if stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode):
            path.unlink()
    except FileNotFoundError:
        pass
