#!/usr/bin/env python3
"""Create two private copies of one Phase 3 result-query key atomically."""

from __future__ import annotations

import os
import pwd
import grp
import secrets
import stat
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 7:
        print(
            "usage: create-phase3-result-query-keys.py "
            "HERMES_FILE HERMES_USER HERMES_GROUP EPSILON_FILE EPSILON_USER EPSILON_GROUP",
            file=sys.stderr,
        )
        return 2
    paths: list[Path] = []
    owners: list[tuple[int, int]] = []
    try:
        for raw_path, user_name, group_name in (
            (sys.argv[1], sys.argv[2], sys.argv[3]),
            (sys.argv[4], sys.argv[5], sys.argv[6]),
        ):
            candidate = Path(raw_path)
            if not candidate.is_absolute() or candidate.name in {"", ".", ".."}:
                raise ValueError("key destinations must be absolute file paths")
            parent = candidate.parent.resolve(strict=True)
            parent_info = parent.stat()
            if not stat.S_ISDIR(parent_info.st_mode) or stat.S_IMODE(parent_info.st_mode) & 0o022:
                raise ValueError("key destination parent is not a directory")
            path = parent / candidate.name
            owners.append((pwd.getpwnam(user_name).pw_uid, grp.getgrnam(group_name).gr_gid))
            paths.append(path)
        if paths[0] == paths[1]:
            raise ValueError("Hermes and Epsilon need separate key files")
        if os.geteuid() != 0 and any(uid != os.geteuid() or gid != os.getegid() for uid, gid in owners):
            raise PermissionError("run as root to install files for different service accounts")
        key = secrets.token_hex(32).encode("ascii") + b"\n"
        created: list[Path] = []
        try:
            for path, (uid, gid) in zip(paths, owners):
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(path, flags, 0o600)
                created.append(path)
                try:
                    os.fchown(fd, uid, gid)
                    os.fchmod(fd, 0o600)
                    offset = 0
                    while offset < len(key):
                        offset += os.write(fd, key[offset:])
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except Exception:
            for path in created:
                try:
                    path.unlink()
                except OSError:
                    pass
            raise
    except (OSError, KeyError, ValueError) as exc:
        print(f"FAIL could not create Phase 3 result-query key copies: {exc}", file=sys.stderr)
        return 1
    print(f"Epsilon service input: HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE={paths[1]}")
    print(f"Hermes profile input: HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE={paths[0]}")
    print("PASS created separate mode-0600 result-query key copies for Hermes and Epsilon")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
