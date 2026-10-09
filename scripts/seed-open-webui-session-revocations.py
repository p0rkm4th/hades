#!/usr/bin/env python3
"""Invalidate every JWT issued before the Open WebUI P0 cutover.

Run only after ingress and the old Open WebUI instance are quiesced, and before
the candidate is allowed to accept traffic. The SQLite input must be a
read-only, integrity-checked copy of the pre-cutover database. The markers are
permanent so a long-lived legacy token cannot become valid again after expiry
assumptions or a Valkey restart.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import time
from pathlib import Path


def run(args: list[str]) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path, help="read-only pre-cutover webui.db copy")
    parser.add_argument("--valkey-container", default="hades-open-webui-auth-state")
    parser.add_argument("--redis-prefix", default="open-webui")
    parser.add_argument(
        "--confirm-quiesced", action="store_true",
        help="assert old Open WebUI is stopped and all ingress is quiesced",
    )
    args = parser.parse_args()
    if not args.confirm_quiesced:
        parser.error("refusing to seed markers without --confirm-quiesced")
    if not args.database.is_file() or args.database.is_symlink():
        parser.error("database must be an existing regular file, not a symlink")

    uri = f"file:{args.database.resolve()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"FAIL source database integrity: {integrity}")
        columns = {row[1] for row in db.execute('PRAGMA table_info("user")')}
        if "id" not in columns:
            raise SystemExit("FAIL source database has no user.id column")
        user_ids = [str(row[0]) for row in db.execute('SELECT id FROM "user"')]
    if not user_ids or any(not user_id or "\n" in user_id for user_id in user_ids):
        raise SystemExit("FAIL source database contains no valid user IDs")

    ping = run(["docker", "exec", args.valkey_container, "valkey-cli", "--raw", "PING"])
    if ping != "PONG":
        raise SystemExit("FAIL auth-state Valkey is not ready")

    # Give all already-issued NumericDate (integer-second) JWTs a strict
    # cutoff. New logins wait in the candidate adapter until iat exceeds it.
    cutoff = repr(time.time() + 5.0)
    for user_id in user_ids:
        key = f"{args.redis_prefix}:auth:user:{user_id}:revoked_at"
        current = run(["docker", "exec", args.valkey_container, "valkey-cli", "--raw", "GET", key])
        try:
            already = float(current) if current else float("-inf")
        except ValueError as error:
            raise SystemExit("FAIL invalid pre-existing user revocation marker") from error
        if already < float(cutoff):
            run(["docker", "exec", args.valkey_container, "valkey-cli", "--raw", "SET", key, cutoff])
        actual = run(["docker", "exec", args.valkey_container, "valkey-cli", "--raw", "GET", key])
        ttl = run(["docker", "exec", args.valkey_container, "valkey-cli", "--raw", "PTTL", key])
        if float(actual) < float(cutoff) or ttl != "-1":
            raise SystemExit("FAIL user revocation marker was not stored permanently")

    print(
        f"PASS seeded permanent pre-cutover session revocation for {len(user_ids)} users; "
        f"cutoff={cutoff}; source database integrity=ok"
    )


if __name__ == "__main__":
    main()
