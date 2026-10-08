#!/usr/bin/env python3
"""Contract test for bounded, read-only workspace Git inspection."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hermes"))


def tool(name: str) -> dict:
    properties = {"path": {"type": "string"}}
    required = ["path"]
    if name == "search_files":
        properties["target"] = {"type": "string", "description": "Optional target"}
    if name == "terminal":
        properties = {"command": {"type": "string"}}
        required = ["command"]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Native {name} tool",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def definitions() -> list[dict]:
    return [tool(name) for name in (
        "read_file", "search_files", "write_file", "patch", "terminal"
    )]


fake_model_tools = types.ModuleType("model_tools")
fake_model_tools.get_tool_definitions = lambda **_kwargs: definitions()
sys.modules["model_tools"] = fake_model_tools

from workspace import (  # noqa: E402
    get_workspace_tools,
    is_workspace_git_inspection_request,
    is_workspace_read_only_request,
    is_workspace_request,
    terminal_policy,
    workspace_enabled,
)


def main() -> int:
    os.environ["HADES_WORKSPACE_ENABLED"] = "true"
    diff_question = "Show me exactly what changed and whether anything unrelated is in the diff."
    branch_question = "What branch am I on, and are there existing local changes?"
    commit_request = "Commit the change we just verified with a clear message."

    assert workspace_enabled()
    assert is_workspace_request(diff_question)
    assert is_workspace_request(branch_question)
    assert is_workspace_git_inspection_request(diff_question)
    assert is_workspace_git_inspection_request(branch_question)
    assert is_workspace_read_only_request(diff_question)
    assert is_workspace_read_only_request(branch_question)
    assert not is_workspace_git_inspection_request(commit_request)
    assert is_workspace_request(commit_request, [{
        "role": "user", "content": diff_question,
    }]), "workspace mutation follow-up lost its reviewed workspace context"
    assert not is_workspace_request(commit_request, [{
        "role": "user", "content": "What changed in the homelab this week?",
    }]), "homelab history incorrectly activated workspace tools"

    read_only_names = {
        row["function"]["name"] for row in get_workspace_tools(read_only=True)
    }
    git_names = {
        row["function"]["name"]
        for row in get_workspace_tools(read_only=True, git_inspection=True)
    }
    assert read_only_names == {"read_file", "search_files"}, read_only_names
    assert git_names == {"read_file", "search_files", "terminal"}, git_names
    terminal = next(
        row["function"] for row in get_workspace_tools(
            read_only=True, git_inspection=True
        ) if row["function"]["name"] == "terminal"
    )
    assert "read-only /workspace mount" in terminal["description"]
    try:
        get_workspace_tools(read_only=False, git_inspection=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Git inspection terminal was allowed on a writable turn")

    with tempfile.TemporaryDirectory(prefix="hades-readonly-git-") as temporary:
        root = Path(temporary)
        readonly = terminal_policy(root, "sandbox@sha256:" + "a" * 64, read_only_git=True)
        assert readonly["TERMINAL_CWD"] == "/workspace"
        assert readonly["TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE"] == "false"
        assert json.loads(readonly["TERMINAL_DOCKER_VOLUMES"]) == [
            f"{root.resolve()}:/workspace:ro"
        ]
        assert readonly["TERMINAL_DOCKER_NETWORK"] == "false"
        assert readonly["TERMINAL_CONTAINER_PERSISTENT"] == "false"
        writable = terminal_policy(root, "sandbox@sha256:" + "a" * 64)
        assert writable["TERMINAL_CWD"] == str(root)
        assert writable["TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE"] == "true"
        assert writable["TERMINAL_DOCKER_VOLUMES"] == "[]"

    print("PASS Git status/diff questions receive only file reads plus read-only terminal")
    print("PASS Git inspection mounts the workspace read-only, offline, and non-persistently")
    print("PASS commit requests remain on the writable action policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
