#!/usr/bin/env python3
"""Read-only check that the running Hindsight worker matches Compose policy."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from hindsight_runtime_contract import worker_identity_matches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", required=True, type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--container", default="hades-hindsight")
    args = parser.parse_args()
    if not args.compose_file.is_file() or args.compose_file.is_symlink():
        print("FAIL Hindsight Compose record is missing or unsafe")
        return 1
    command = ["docker", "compose"]
    if args.env_file:
        command += ["--env-file", str(args.env_file)]
    command += ["-f", str(args.compose_file), "config", "--format", "json"]
    try:
        rendered = subprocess.run(command, check=True, capture_output=True, text=True)
        inspected = subprocess.run(["docker", "inspect", args.container], check=True, capture_output=True, text=True)
        compose_config = json.loads(rendered.stdout)
        container_state = json.loads(inspected.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        print("FAIL Hindsight Compose/runtime worker identity could not be checked")
        return 1
    if not worker_identity_matches(compose_config, container_state):
        print("FAIL Hindsight worker identity is missing or differs from the deployment contract")
        return 1
    print("PASS Hindsight worker identity matches the deployment contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
