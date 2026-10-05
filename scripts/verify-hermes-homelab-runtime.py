#!/usr/bin/env python3
"""Verify the homelab package selected by the active Hermes profile."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


def load_provenance_helpers(path: Path):
    spec = importlib.util.spec_from_file_location("_hades_deployed_provenance", path)
    if spec is None or spec.loader is None:
        raise ValueError("runtime identity helpers are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selected_profile_path(arguments: list[str], environment: dict[str, str]) -> Path:
    names: list[str] = []
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item in {"-p", "--profile"}:
            if index + 1 >= len(arguments):
                raise ValueError("Hermes profile argument is incomplete")
            names.append(arguments[index + 1])
            index += 2
            continue
        if item.startswith("--profile="):
            names.append(item.split("=", 1)[1])
        index += 1
    if len(names) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", names[0]):
        raise ValueError("running Hermes profile selection is ambiguous")
    home = environment.get("HERMES_HOME", "").strip()
    if not home or not Path(home).is_absolute():
        raise ValueError("running Hermes home is unavailable")
    return Path(home) / "profiles" / names[0] / "config.yaml"


def process_identity(pid_value: str) -> tuple[list[str], dict[str, str]]:
    if not pid_value.isdecimal() or int(pid_value) <= 1:
        raise ValueError("active Hermes process identifier is invalid")
    process = Path("/proc") / pid_value
    arguments = [
        item.decode("utf-8", errors="strict")
        for item in (process / "cmdline").read_bytes().split(b"\0")
        if item
    ]
    environment: dict[str, str] = {}
    for item in (process / "environ").read_bytes().split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        environment[key.decode("utf-8", errors="strict")] = value.decode("utf-8", errors="strict")
    if not arguments:
        raise ValueError("active Hermes process arguments are unavailable")
    return arguments, environment


def verify(expected_profile: Path, repo: Path, pid: str, helper_path: Path) -> None:
    helper = load_provenance_helpers(helper_path)
    arguments, environment = process_identity(pid)
    profile = selected_profile_path(arguments, environment)
    helper.verify_selected_profile(arguments, environment, profile)
    if profile.is_symlink() or not profile.is_file() or profile.resolve(strict=True) != expected_profile.resolve(strict=True):
        raise ValueError("active Hermes profile differs from the configured profile")
    registrations = helper.profile_server_blocks(profile.read_text(encoding="utf-8"))
    block = registrations.get("homelab-readonly")
    if block is None or re.search(r"(?m)^    enabled:\s*false\s*$", block):
        raise ValueError("required homelab MCP registration is absent or disabled")

    command_match = re.search(r"(?m)^    command:\s*(.+?)\s*$", block)
    command = command_match.group(1).strip().strip("'\"") if command_match else ""
    arguments = helper.profile_args(block, "homelab-readonly")
    resolved = [helper.expand_profile_value(item, environment) for item in arguments]
    if (
        not re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", Path(command).name)
        or not resolved
        or not resolved[0].endswith(".py")
        or any("${" in item or re.search(r"\$[A-Za-z_][A-Za-z0-9_]*", item) for item in resolved)
    ):
        raise ValueError("required homelab MCP registration has an unsupported command")

    selected_script = Path(resolved[0])
    if not selected_script.is_absolute():
        selected_script = repo / selected_script
    helper.homelab_package_identity(selected_script, environment, repo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-profile", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--pid", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    helper_path = repo / "scripts" / "write-deployed-provenance.py"
    if args.expected_profile.is_symlink() or not args.expected_profile.is_file():
        print("FAIL active Hermes profile is unavailable or unsafe", file=sys.stderr)
        return 1
    try:
        verify(args.expected_profile, repo, args.pid, helper_path)
    except (Exception, SystemExit):
        print("FAIL selected Hermes homelab MCP package does not match the installed source revision", file=sys.stderr)
        return 1
    print("PASS selected Hermes homelab MCP package matches the installed source revision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
