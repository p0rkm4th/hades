"""Reloadable, fail-closed Phase 3 operator authority policy source.

The policy is an operator-managed input, not user data or an authority cache.
Every call opens and validates the current on-disk file so a grant removal is
visible to the next scheduled operation without restarting a long-running
service. User/group directory synchronization remains a separate concern.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .phase3_self_service import Phase3Authority, Phase3AuthorizationError, _valid_subject


MAX_POLICY_BYTES = 64 * 1024
ALLOWED_RESOURCES = frozenset({"hades-core.health", "grocy.household", "backup.evidence"})
ALLOWED_ROLES = frozenset({"owner", "admin", "household"})


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


class Phase3AuthorityPolicy:
    """Resolve an active subject and explicit resource grants from a secure file."""

    def __init__(self, path: str | Path, *, owner_uid: int | None = None):
        self.path = Path(path)
        self.owner_uid = os.geteuid() if owner_uid is None else owner_uid

    def _read(self) -> dict[str, Any]:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(self.path, flags)
        except OSError as exc:
            raise Phase3AuthorizationError("current automation authority is unavailable") from exc
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self.owner_uid
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size <= 0
                or info.st_size > MAX_POLICY_BYTES
            ):
                raise Phase3AuthorizationError("current automation authority is unavailable")
            chunks = []
            remaining = MAX_POLICY_BYTES + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 8192))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > MAX_POLICY_BYTES:
                raise Phase3AuthorizationError("current automation authority is unavailable")
        finally:
            os.close(fd)
        try:
            value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise Phase3AuthorizationError("current automation authority is unavailable") from exc
        if (
            not isinstance(value, dict)
            or set(value) != {"schema", "subjects"}
            or type(value.get("schema")) is not int
            or value.get("schema") != 1
        ):
            raise Phase3AuthorizationError("current automation authority is unavailable")
        subjects = value.get("subjects")
        if not isinstance(subjects, dict) or len(subjects) > 1000:
            raise Phase3AuthorizationError("current automation authority is unavailable")
        for subject, record in subjects.items():
            if not _valid_subject(subject) or not isinstance(record, dict) or set(record) != {"active", "role", "resources"}:
                raise Phase3AuthorizationError("current automation authority is unavailable")
            role = record.get("role")
            if type(record.get("active")) is not bool or not isinstance(role, str) or role not in ALLOWED_ROLES:
                raise Phase3AuthorizationError("current automation authority is unavailable")
            resources = record.get("resources")
            if (
                not isinstance(resources, list)
                or any(not isinstance(resource, str) or resource not in ALLOWED_RESOURCES for resource in resources)
                or len(resources) != len(set(resources))
            ):
                raise Phase3AuthorizationError("current automation authority is unavailable")
        return subjects

    def __call__(self, subject: str) -> Phase3Authority:
        if not _valid_subject(subject):
            return Phase3Authority(str(subject or ""), "household", frozenset(), False)
        record = self._read().get(subject)
        if not record or not record["active"]:
            return Phase3Authority(subject, "household", frozenset(), False)
        return Phase3Authority(subject, record["role"], frozenset(record["resources"]), True)
