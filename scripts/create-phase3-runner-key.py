#!/usr/bin/env python3
"""Create an Epsilon-owned HMAC key for the n8n Phase 3 Crypto credential."""

from __future__ import annotations

import grp
import os
import pwd
import secrets
import stat
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: create-phase3-runner-key.py ABSOLUTE_FILE EPSILON_USER EPSILON_GROUP", file=sys.stderr)
        return 2
    try:
        candidate = Path(sys.argv[1])
        if not candidate.is_absolute() or candidate.name in {"", ".", ".."}:
            raise ValueError("key destination must be an absolute file path")
        parent = candidate.parent.resolve(strict=True)
        parent_info = parent.stat()
        if not stat.S_ISDIR(parent_info.st_mode) or stat.S_IMODE(parent_info.st_mode) & 0o077:
            raise ValueError("key destination parent is not private")
        path = parent / candidate.name
        uid = pwd.getpwnam(sys.argv[2]).pw_uid
        gid = grp.getgrnam(sys.argv[3]).gr_gid
        if os.geteuid() != 0 and (uid != os.geteuid() or gid != os.getegid()):
            raise PermissionError("run as root to install the key for another service account")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        try:
            os.fchown(fd, uid, gid)
            os.fchmod(fd, 0o600)
            key = secrets.token_hex(32).encode("ascii") + b"\n"
            offset = 0
            while offset < len(key):
                offset += os.write(fd, key[offset:])
            os.fsync(fd)
        except Exception:
            os.close(fd)
            path.unlink(missing_ok=True)
            raise
        else:
            os.close(fd)
    except (OSError, KeyError, ValueError) as exc:
        print(f"FAIL could not create Phase 3 runner key: {exc}", file=sys.stderr)
        return 1
    print(f"HADES_EPSILON_PHASE3_HMAC_KEY_FILE={path}")
    print("PASS created an Epsilon-owned mode-0600 runner key; key contents were not printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
