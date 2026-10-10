#!/usr/bin/env python3
"""Verify an Open WebUI Valkey RDB contains restorable revocations.

The verifier does not print Redis key names or marker values. It compares the
live source marker set with a disposable, network-isolated restore of the RDB.
"""

from __future__ import annotations

import argparse
import subprocess
import time
import uuid
from pathlib import Path


def run(args: list[str], *, check: bool = True) -> str:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {args[0]}")
    return result.stdout.strip()


def marker_snapshot(container: str, pattern: str, *, integer_value: bool) -> dict[str, tuple[str, int]]:
    keys = run([
        "docker", "exec", container, "valkey-cli", "--raw", "--scan",
        "--pattern", pattern,
    ]).splitlines()
    markers: dict[str, tuple[str, int]] = {}
    for key in keys:
        expires_at = run([
            "docker", "exec", container, "valkey-cli", "--raw", "PEXPIRETIME", key,
        ])
        if expires_at == "-2":
            continue  # The marker expired between SCAN and inspection.
        kind = run(["docker", "exec", container, "valkey-cli", "--raw", "TYPE", key])
        if kind != "string":
            expires_after_type = run([
                "docker", "exec", container, "valkey-cli", "--raw", "PEXPIRETIME", key,
            ])
            if expires_after_type == "-2":
                continue
            raise RuntimeError("matching revocation key is not a string")
        value = run(["docker", "exec", container, "valkey-cli", "--raw", "GET", key])
        if not value:
            expires_after_read = run([
                "docker", "exec", container, "valkey-cli", "--raw", "PEXPIRETIME", key,
            ])
            if expires_after_read == "-2":
                continue
            raise RuntimeError("matching revocation key has an empty value")
        try:
            expires_at_ms = int(expires_at)
        except ValueError as error:
            raise RuntimeError("matching revocation key has an invalid expiry") from error
        if integer_value:
            try:
                int(value)
            except ValueError as error:
                raise RuntimeError("user-revocation marker is not an integer timestamp") from error
            if expires_at_ms != -1 and expires_at_ms <= 0:
                raise RuntimeError("user-revocation marker has an invalid expiry")
        elif value != "1" or expires_at_ms <= 0:
            raise RuntimeError("token-revocation marker has an invalid value or expiry")
        markers[key] = (value, expires_at_ms)
    return markers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rdb", type=Path)
    parser.add_argument("--source-container", default="hades-open-webui-auth-state")
    parser.add_argument("--image", required=True, help="immutable, locally available Valkey image")
    parser.add_argument("--prefix", default="open-webui")
    parser.add_argument("--minimum-user-markers", type=int, default=0)
    parser.add_argument("--minimum-token-markers", type=int, default=0)
    args = parser.parse_args()

    if not args.rdb.is_file() or args.rdb.is_symlink() or args.rdb.stat().st_size == 0:
        raise SystemExit("FAIL auth-state RDB must be a nonempty regular file")
    if ("@sha256:" not in args.image
            or args.minimum_user_markers < 0 or args.minimum_token_markers < 0
            or args.minimum_user_markers + args.minimum_token_markers < 1):
        raise SystemExit("FAIL immutable Valkey image and a positive revocation marker minimum are required")

    user_pattern = f"{args.prefix}:auth:user:*:revoked_at"
    token_pattern = f"{args.prefix}:auth:token:*:revoked"
    source_user_markers = marker_snapshot(args.source_container, user_pattern, integer_value=True)
    source_token_markers = marker_snapshot(args.source_container, token_pattern, integer_value=False)
    if (len(source_user_markers) < args.minimum_user_markers
            or len(source_token_markers) < args.minimum_token_markers):
        raise SystemExit("FAIL source auth-state has fewer revocation markers than required")

    run([
        "docker", "run", "--rm", "--pull=never", "--network", "none",
        "--entrypoint", "valkey-check-rdb", "-v", f"{args.rdb.parent.resolve()}:/backup:ro",
        args.image, f"/backup/{args.rdb.name}",
    ])

    suffix = uuid.uuid4().hex[:12]
    restore_container = f"hades-auth-state-backup-restore-{suffix}"
    run([
        "docker", "create", "--rm", "--pull=never", "--network", "none",
        "--name", restore_container, "--entrypoint", "valkey-server", args.image,
        "--dir", "/data", "--dbfilename", "dump.rdb", "--save", "",
        "--appendonly", "no", "--protected-mode", "yes",
    ])
    try:
        run(["docker", "cp", str(args.rdb), f"{restore_container}:/data/dump.rdb"])
        run(["docker", "start", restore_container])
        ready = False
        for _ in range(30):
            result = subprocess.run(
                ["docker", "exec", restore_container, "valkey-cli", "--raw", "PING"],
                check=False, capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip() == "PONG":
                ready = True
                break
            time.sleep(1)
        if not ready:
            logs = subprocess.run(["docker", "logs", restore_container], check=False,
                                  capture_output=True, text=True)
            raise RuntimeError(
                "disposable auth-state restore did not become ready: "
                + logs.stdout[-500:] + logs.stderr[-500:]
            )

        restored_user_markers = marker_snapshot(restore_container, user_pattern, integer_value=True)
        restored_token_markers = marker_snapshot(restore_container, token_pattern, integer_value=False)
        if (restored_user_markers != source_user_markers
                or restored_token_markers != source_token_markers):
            raise RuntimeError("restored RDB did not preserve exact revocation marker values and expiries")
    finally:
        subprocess.run(["docker", "rm", "-f", restore_container], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(
        "PASS isolated auth-state restore preserved "
        f"{len(source_user_markers)} active user and {len(source_token_markers)} active token revocation markers"
    )


if __name__ == "__main__":
    main()
