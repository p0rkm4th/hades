"""Resolve Phase 3 authority from current LLDAP membership.

The resolver uses a dedicated LLDAP account in ``lldap_strict_readonly`` and
never caches a JWT or directory snapshot. A protected local mapping binds the
stable Open WebUI subject to one LLDAP user ID and maps explicitly named
directory groups to the small Phase 3 resource allowlist.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .phase3_self_service import (
    Phase3Authority,
    Phase3AuthorizationError,
    RESOURCE_LABELS,
    _valid_subject,
)


MAX_CONFIG_BYTES = 64 * 1024
MAX_SECRET_BYTES = 4096
MAX_RESPONSE_BYTES = 1024 * 1024
_USER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}\Z")
_GROUP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_. -]{0,127}\Z")
_ROLES = frozenset({"owner", "admin", "household"})
_RESERVED_GROUPS = frozenset({"lldap_admin", "lldap_password_manager", "lldap_strict_readonly"})
_ROLE_RANK = {"household": 0, "admin": 1, "owner": 2}
_QUERY = """query HadesPhase3Authority($readerId: String!, $subjectId: String!) {
  reader: user(userId: $readerId) { id groups { displayName } }
  subject: user(userId: $subjectId) { id groups { displayName } }
}"""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read_private_json(path: Path, owner_uid: int, max_bytes: int) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise Phase3AuthorizationError("current directory authority is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner_uid
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size <= 0
            or info.st_size > max_bytes
        ):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 8192))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > max_bytes:
            raise Phase3AuthorizationError("current directory authority is unavailable")
    finally:
        os.close(fd)
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise Phase3AuthorizationError("current directory authority is unavailable") from exc
    if not isinstance(value, dict):
        raise Phase3AuthorizationError("current directory authority is unavailable")
    return value


class Phase3LldapAuthority:
    """Resolve actor grants from a live, read-only LLDAP account."""

    def __init__(
        self,
        config_path: str | Path,
        password_path: str | Path,
        endpoint: str,
        *,
        owner_uid: int | None = None,
        timeout: float = 4.0,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.password_path = Path(password_path)
        self.endpoint = self._validate_endpoint(endpoint)
        self.owner_uid = os.geteuid() if owner_uid is None else owner_uid
        if not 0.1 <= timeout <= 15:
            raise ValueError("directory timeout is outside the allowed range")
        self.timeout = timeout
        self.opener = opener or urlopen

    @staticmethod
    def _validate_endpoint(value: str) -> str:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except (TypeError, ValueError) as exc:
            raise ValueError("LLDAP endpoint is invalid") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"})
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("LLDAP endpoint must use HTTPS or local loopback HTTP")
        return value.rstrip("/")

    def _config(self) -> tuple[str, dict[str, str], dict[str, dict[str, Any]]]:
        value = _read_private_json(self.config_path, self.owner_uid, MAX_CONFIG_BYTES)
        if (
            set(value) != {"schema", "reader_user_id", "subjects", "groups"}
            or type(value.get("schema")) is not int
            or value.get("schema") != 1
        ):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        reader_id = value.get("reader_user_id")
        subjects = value.get("subjects")
        groups = value.get("groups")
        if not isinstance(reader_id, str) or not _USER_ID.fullmatch(reader_id):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        if not isinstance(subjects, dict) or len(subjects) > 1000:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        subject_map: dict[str, str] = {}
        for subject, user_id in subjects.items():
            if not _valid_subject(subject) or not isinstance(user_id, str) or not _USER_ID.fullmatch(user_id):
                raise Phase3AuthorizationError("current directory authority is unavailable")
            subject_map[subject] = user_id
        normalized_ids = {user_id.casefold() for user_id in subject_map.values()}
        if len(normalized_ids) != len(subject_map):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        if reader_id.casefold() in normalized_ids:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        if not isinstance(groups, dict) or len(groups) > 100:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        group_map: dict[str, dict[str, Any]] = {}
        for group_name, record in groups.items():
            if (
                not isinstance(group_name, str)
                or not _GROUP_NAME.fullmatch(group_name)
                or group_name in _RESERVED_GROUPS
            ):
                raise Phase3AuthorizationError("current directory authority is unavailable")
            if not isinstance(record, dict) or set(record) != {"role", "resources"}:
                raise Phase3AuthorizationError("current directory authority is unavailable")
            role = record.get("role")
            resources = record.get("resources")
            if (
                not isinstance(role, str)
                or role not in _ROLES
                or not isinstance(resources, list)
                or any(not isinstance(resource, str) or resource not in RESOURCE_LABELS for resource in resources)
                or len(resources) != len(set(resources))
            ):
                raise Phase3AuthorizationError("current directory authority is unavailable")
            group_map[group_name] = {"role": role, "resources": frozenset(resources)}
        return reader_id, subject_map, group_map

    def _password(self) -> str:
        try:
            fd = os.open(
                self.password_path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            )
        except OSError as exc:
            raise Phase3AuthorizationError("current directory authority is unavailable") from exc
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != self.owner_uid
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size <= 0
                or info.st_size > MAX_SECRET_BYTES
            ):
                raise Phase3AuthorizationError("current directory authority is unavailable")
            chunks: list[bytes] = []
            remaining = MAX_SECRET_BYTES + 1
            while remaining:
                chunk = os.read(fd, min(remaining, 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > MAX_SECRET_BYTES:
                raise Phase3AuthorizationError("current directory authority is unavailable")
        finally:
            os.close(fd)
        try:
            password = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise Phase3AuthorizationError("current directory authority is unavailable") from exc
        if not password or "\x00" in password:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        return password

    def _post(self, path: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(
            self.endpoint + path,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, URLError, TimeoutError, ValueError) as exc:
            raise Phase3AuthorizationError("current directory authority is unavailable") from exc
        if len(raw) > MAX_RESPONSE_BYTES:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        try:
            result = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Phase3AuthorizationError("current directory authority is unavailable") from exc
        if not isinstance(result, dict):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        return result

    @staticmethod
    def _groups(record: Any, expected_id: str) -> frozenset[str]:
        if not isinstance(record, dict) or record.get("id") != expected_id:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        groups = record.get("groups")
        if not isinstance(groups, list):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        names: set[str] = set()
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("displayName"), str):
                raise Phase3AuthorizationError("current directory authority is unavailable")
            name = group["displayName"]
            if not _GROUP_NAME.fullmatch(name) or name in names:
                raise Phase3AuthorizationError("current directory authority is unavailable")
            names.add(name)
        return frozenset(names)

    def __call__(self, subject: str) -> Phase3Authority:
        if not _valid_subject(subject):
            return Phase3Authority(str(subject or ""), "household", frozenset(), False)
        reader_id, subject_map, group_map = self._config()
        target_id = subject_map.get(subject)
        if target_id is None:
            return Phase3Authority(subject, "household", frozenset(), False)
        password = self._password()
        login = self._post("/auth/simple/login", {"username": reader_id, "password": password})
        token = login.get("token")
        if not isinstance(token, str) or not token or len(token) > 16 * 1024:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        result = self._post(
            "/api/graphql",
            {
                "operationName": "HadesPhase3Authority",
                "query": _QUERY,
                "variables": {"readerId": reader_id, "subjectId": target_id},
            },
            token,
        )
        if "errors" in result:
            raise Phase3AuthorizationError("current directory authority is unavailable")
        data = result.get("data")
        if not isinstance(data, dict):
            raise Phase3AuthorizationError("current directory authority is unavailable")
        reader_groups = self._groups(data.get("reader"), reader_id)
        if "lldap_strict_readonly" not in reader_groups or reader_groups.intersection(
            {"lldap_admin", "lldap_password_manager"}
        ):
            raise Phase3AuthorizationError("directory reader account is not least-privilege")
        subject_groups = self._groups(data.get("subject"), target_id)
        if not subject_groups:
            return Phase3Authority(subject, "household", frozenset(), True)
        matching = [group_map[name] for name in subject_groups if name in group_map]
        resources = frozenset(resource for entry in matching for resource in entry["resources"])
        role = max((entry["role"] for entry in matching), key=_ROLE_RANK.__getitem__, default="household")
        return Phase3Authority(subject, role, resources, True)
