#!/usr/bin/env python3
"""Run one real-model Hermes coding turn inside the disposable test namespace."""

from __future__ import annotations

import importlib.metadata
import json
import os
import socket
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_config = json.loads((Path(__file__).parent / "inference-config.json").read_text())
sys.path.insert(0, _config["hermes_root"] + "/source")
sys.path.insert(0, _config["contract_root"])

from workspace_contract import (
    WorkspaceBinding,
    begin_commit_invocation,
    begin_test_invocation,
    complete_test_invocation,
    snapshot_repository,
    terminal_result_from_hermes_hook,
)


TASK_ID = "inference-coding-task"
SESSION_ID = "inference-coding-session"
TURN_ID = "inference-coding-turn"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def type_from_dict(name: str, value: dict[str, Any]) -> Any:
    from workspace_contract import CommitInvocation, TestInvocation
    return {"CommitInvocation": CommitInvocation, "TestInvocation": TestInvocation}[name](**value)


def main() -> int:
    model = _config["model"]
    base_url = os.environ["HADES_MODEL_BASE_URL"]
    os.environ["HERMES_HOME"] = "/tmp/hermes-home"
    os.environ["HOME"] = "/tmp"
    Path(os.environ["HERMES_HOME"]).mkdir(mode=0o700, parents=True, exist_ok=True)
    config = Path(os.environ["HERMES_HOME"]) / "config.yaml"
    config.write_text(
        "model:\n  default: " + str(_config["model"]) + "\n"
        "  provider: custom\n  base_url: " + base_url + "\n"
        "  context_length: " + str(_config["context_length"]) + "\n"
        "  ollama_num_ctx: " + str(_config["ollama_num_ctx"]) + "\n"
        "  max_tokens: " + str(_config["max_tokens"]) + "\n"
        "terminal:\n  backend: local\n  cwd: /workspace\n  timeout: 30\n"
        "  persistent_shell: false\n",
        encoding="utf-8",
    )
    config.chmod(0o600)

    from hermes_cli.plugins import get_plugin_manager
    from run_agent import AIAgent

    version = importlib.metadata.version("hermes-agent")
    if version != "0.21.2":
        raise RuntimeError("coding proof requires Hermes 0.21.2")
    caps = next(line for line in Path("/proc/self/status").read_text().splitlines()
                if line.startswith("CapEff:")).split(":", 1)[1].strip()
    if int(caps, 16) != 0:
        raise RuntimeError("effective capabilities are not empty")
    if (Path("/") / "home" / "scotty").exists() or (
        Path("/") / "scootz" / "Workspaces" / "HADES"
    ).exists():
        raise RuntimeError("private home or canonical HADES checkout is visible")
    if not Path("/run/hades-inference/model.sock").is_socket():
        raise RuntimeError("the bounded inference socket is not mounted")

    blocked = []
    arbitrary_lan = ".".join(("10", "0", "0", "1"))
    ssh_target = ".".join(("10", "0", "0", "156"))
    probes = (
        ("internet", "1.1.1.1", 443),
        ("arbitrary-lan", arbitrary_lan, 80),
        ("model-direct", _config["endpoint_ip"], _config["endpoint_port"]),
        ("ssh", ssh_target, 22),
        ("grocy", arbitrary_lan, 7003),
        ("open-webui", arbitrary_lan, 3000),
        ("dns", "example.invalid", 443),
    )
    for label, host, port in probes:
        try:
            socket.create_connection((host, port), timeout=0.5).close()
        except OSError:
            blocked.append(label)
        else:
            raise RuntimeError("unexpected network route was reachable: " + label)
    try:
        socket.create_connection(("127.0.0.1", 18138), timeout=0.5).close()
    except OSError:
        blocked.append("unapproved-loopback-port")
    else:
        raise RuntimeError("unexpected loopback service was reachable")
    if len(blocked) != len(probes) + 1:
        raise RuntimeError("network deny-by-default probe set was incomplete")

    calls: dict[str, dict[str, Any]] = {}
    manager = get_plugin_manager()
    workspace = Path.cwd().resolve(strict=True)
    binding = WorkspaceBinding("owner-disposable-fixture", workspace, workspace)
    active_turn_id = TURN_ID + "-01"
    initial_head = snapshot_repository(
        binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=active_turn_id
    ).head

    def pre_tool(*, tool_name: str = "", args: Any = None, task_id: str = "",
                 session_id: str = "", tool_call_id: str = "", **_: Any) -> None:
        if task_id == TASK_ID and session_id == SESSION_ID:
            print("HADES_TOOL_START=" + tool_name, flush=True)
            record = {"tool_name": tool_name, "args": args}
            if tool_name == "terminal" and isinstance(args, dict):
                command = args.get("command", "")
                snapshot = snapshot_repository(
                    binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=active_turn_id
                )
                record["before"] = _jsonable(snapshot.__dict__)
                if "python3 -m unittest" in command or "pytest" in command:
                    record["test_invocation"] = begin_test_invocation(
                        binding, snapshot, paths={"calc.py"}, command=command,
                        tool_call_id=tool_call_id,
                    ).__dict__
                if "git commit" in command:
                    record["commit_invocation"] = begin_commit_invocation(
                        binding, snapshot, command=command, tool_call_id=tool_call_id
                    ).__dict__
            calls[tool_call_id] = record

    def post_tool(*, tool_name: str = "", args: Any = None, result: Any = None,
                  task_id: str = "", session_id: str = "", tool_call_id: str = "",
                  **_: Any) -> None:
        if task_id == TASK_ID and session_id == SESSION_ID:
            print("HADES_TOOL_END=" + tool_name, flush=True)
            record = calls.setdefault(tool_call_id, {"tool_name": tool_name, "args": args})
            record["result"] = result
            if tool_name == "terminal" and isinstance(args, dict):
                try:
                    terminal = terminal_result_from_hermes_hook(
                        tool_name=tool_name, args=args, result=result, task_id=task_id,
                        session_id=session_id, turn_id=active_turn_id, tool_call_id=tool_call_id,
                    )
                    record["terminal_result"] = _jsonable(terminal.__dict__)
                    if "test_invocation" in record:
                        after = snapshot_repository(
                            binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=active_turn_id
                        )
                        evidence = complete_test_invocation(
                            binding,
                            type_from_dict("TestInvocation", record["test_invocation"]),
                            after,
                            result=terminal,
                        )
                        record["test_evidence"] = _jsonable(evidence.__dict__)
                except Exception as exc:
                    record["evidence_error"] = type(exc).__name__

    manager._hooks.setdefault("pre_tool_call", []).append(pre_tool)
    manager._hooks.setdefault("post_tool_call", []).append(post_tool)
    agent = AIAgent(
        api_key="inference-only-local-relay",
        base_url=base_url,
        provider="custom",
        model=model,
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        session_id=SESSION_ID,
        user_id="owner-disposable-fixture",
        enabled_toolsets=["terminal", "file"],
        max_iterations=20,
        max_tokens=_config["max_tokens"],
    )
    agent._disable_streaming = True
    agent.ephemeral_system_prompt = (
        "You are working in one disposable repository. Use Hermes native terminal, read_file, "
        "and write_file tools directly; do not call tool_call or tool_search. Make one tool call "
        "at a time. After a command fails, read its result, inspect current files or Git state, "
        "then choose a corrected operation. Never repeat a state-changing command until you have "
        "checked canonical Git state."
    )
    try:
        history = None
        prompts = (
            "First run exactly `python3 -m unittest -q test_missing` as an intentionally "
            "bad test path. When it fails, inspect the real calc.py and test_calc.py, "
            "confirm the actual focused test fails, fix only calc.py, rerun the focused "
            "test, and inspect `git diff -- calc.py`. The terminal starts in /workspace. "
            "Read the failures and continue; do not stop after either failure or search unrelated files.",
            "Continue this same task. First inspect actual git status and HEAD; do not "
            "repeat any commit that already happened. If the fix is not committed, rerun "
            "`python3 -m unittest -q` now and verify it passes, inspect `git diff -- calc.py`, "
            "then call `git add calc.py` alone and `git commit -m 'Fix answer calculation'` "
            "in a separate terminal call. This is explicit authorization to commit only "
            "calc.py. If state is ambiguous, report it and do not retry.",
            "Continue only after checking canonical status and HEAD. If no commit happened, "
            "verify the fix and passing test, then complete the separately staged commit. "
            "Never repeat a commit if HEAD already advanced.",
        )
        result = {}
        turns_executed = 0
        for index, prompt in enumerate(prompts, start=1):
            active_turn_id = f"{TURN_ID}-{index:02d}"
            result = agent.run_conversation(
                prompt,
                conversation_history=history,
                task_id=TASK_ID,
            )
            turns_executed = index
            history = result.get("messages") if isinstance(result, dict) else None
            current = snapshot_repository(
                binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=active_turn_id
            )
            # Reconcile Git before deciding whether another user turn may retry.
            if current.head != initial_head:
                break
        payload = {
            "completed": bool(result.get("completed")),
            "final_response": result.get("final_response", ""),
            "turns_executed": turns_executed,
            "hermes_version": version,
            "model_configured": bool(model),
            "capabilities": caps,
            "private_paths_absent": True,
            "network_blocked": blocked,
            "task_id": TASK_ID,
            "session_id": SESSION_ID,
            "turn_id": TURN_ID,
            "tool_calls": calls,
        }
        print("HADES_REAL_HERMES_RESULT=" + json.dumps(_jsonable(payload), sort_keys=True, default=str))
        return 0 if payload["completed"] else 1
    finally:
        manager._hooks["pre_tool_call"].remove(pre_tool)
        manager._hooks["post_tool_call"].remove(post_tool)


if __name__ == "__main__":
    raise SystemExit(main())
