#!/usr/bin/env python3
"""Deterministic model driver for a native Hermes 0.21.x coding-loop probe.

This is disposable qualification code. Hermes AIAgent, tool definitions,
tool-call lifecycle, and native terminal dispatch remain real; only model
responses are scripted so the experiment needs no network or credentials.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import socket
import importlib.metadata
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hermes_cli.plugins import get_plugin_manager
from run_agent import AIAgent


TASK_ID = "namespace-coding-task"
SESSION_ID = "namespace-coding-session"
TURN_ID = "namespace-coding-turn"


def _message(content: str = "", calls: list[tuple[str, str, dict[str, Any]]] | None = None) -> Any:
    tool_calls = []
    for call_id, name, arguments in calls or []:
        tool_calls.append(SimpleNamespace(
            id=call_id,
            type="function",
            function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
        ))
    return SimpleNamespace(content=content, tool_calls=tool_calls or None)


def _response(message: Any, finish_reason: str) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        model="test-model",
        usage=None,
    )


def _tool_response(call_id: str, name: str, arguments: dict[str, Any]) -> Any:
    return _response(_message(calls=[(call_id, name, arguments)]), "tool_calls")


def _terminal_response(call_id: str, command: str) -> Any:
    return _tool_response(call_id, "terminal", {"command": command})


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


def main() -> int:
    os.environ["HERMES_HOME"] = "/tmp/hermes-home"
    os.environ["HOME"] = "/tmp"
    Path(os.environ["HERMES_HOME"]).mkdir(mode=0o700, parents=True, exist_ok=True)
    config_path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
    config_path.write_text(
        "terminal:\n  backend: local\n  cwd: /workspace\n  timeout: 30\n  persistent_shell: false\n",
        encoding="utf-8",
    )
    config_path.chmod(0o600)
    hermes_version = importlib.metadata.version("hermes-agent")
    if hermes_version != "0.21.2":
        raise RuntimeError(f"expected Hermes 0.21.2, found {hermes_version}")
    capabilities = next(
        line for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith("CapEff:")
    ).split(":", 1)[1].strip()
    if int(capabilities, 16) != 0:
        raise RuntimeError("namespace coding process retained effective capabilities")
    private_home = Path("/") / "home" / "scotty"
    canonical_checkout = Path("/") / "scootz" / "Workspaces" / "HADES"
    if private_home.exists() or canonical_checkout.exists():
        raise RuntimeError("private home or canonical HADES checkout is visible")
    network_probe = socket.socket()
    network_probe.settimeout(1)
    try:
        network_probe.connect(("1.1.1.1", 53))
    except OSError:
        network_denied = True
    else:
        network_denied = False
    finally:
        network_probe.close()
    if not network_denied:
        raise RuntimeError("network namespace allowed an external connection")

    responses = [
        _terminal_response(
            "inspect-01",
            "pwd && git status --short --branch && cat calc.py && cat test_calc.py",
        ),
        _tool_response("read-source-02", "read_file", {"path": "calc.py"}),
        _tool_response("read-test-03", "read_file", {"path": "test_calc.py"}),
        _terminal_response(
            "capability-04",
            "python3 -c " + shlex.quote(
                "from pathlib import Path; "
                "cap=next(x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('CapEff:')); "
                "assert int(cap.split(':',1)[1],16)==0; "
                "assert not (Path('/')/'home'/'scotty'/'.ssh').exists(); "
                "assert not (Path('/')/'scootz'/'Workspaces'/'HADES').exists(); print('capabilities=none private-paths=absent')"
            ),
        ),
        _terminal_response(
            "network-05",
            "python3 -c " + shlex.quote(
                "import socket; s=socket.socket(); s.settimeout(1); "
                "\ntry: s.connect(('1.1.1.1',53)); raise SystemExit(1)\n"
                "except OSError: print('network-denied')\nfinally: s.close()"
            ),
        ),
        _terminal_response(
            "outside-write-06",
            "python3 -c " + shlex.quote(
                "from pathlib import Path; (Path('/')/'home'/'scotty'/'.cinder-sandbox-probe').write_text('unexpected')"
            ),
        ),
        _tool_response(
            "edit-file-07",
            "write_file",
            {"path": "calc.py", "content": "def answer():\n    return 42\n"},
        ),
        _terminal_response("test-08", "python3 -m unittest -q"),
        _terminal_response("diff-09", "git diff -- calc.py"),
        _terminal_response("stage-10", "git add calc.py"),
        _terminal_response("commit-11", "git commit -m 'Fix answer calculation'"),
        _response(_message("Fixed the failing test and committed the change."), "stop"),
    ]

    from workspace_contract import (
        begin_commit_invocation,
        begin_test_invocation,
        snapshot_repository,
        terminal_result_from_hermes_hook,
    )

    workspace = Path.cwd().resolve(strict=True)
    binding = SimpleNamespace(subject="owner-fixture", root=workspace, repository=workspace)
    calls: dict[str, dict[str, Any]] = {}

    def _pre_tool_call(
        *, tool_name: str = "", args: Any = None, task_id: str = "",
        session_id: str = "", tool_call_id: str = "", **_: Any,
    ) -> None:
        if task_id != TASK_ID or session_id != SESSION_ID:
            return None
        record = calls.setdefault(tool_call_id, {"tool_name": tool_name, "args": args})
        if tool_name != "terminal":
            return None
        command = args.get("command", "") if isinstance(args, dict) else ""
        snapshot = snapshot_repository(
            binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=TURN_ID
        )
        record.update({"command": command, "snapshot": asdict(snapshot)})
        if re.match(r"^python3 -m unittest(?:\s|$)", command):
            invocation = begin_test_invocation(
                binding,
                snapshot,
                paths={"calc.py"},
                command=command,
                tool_call_id=tool_call_id,
            )
            record["test_invocation"] = asdict(invocation)
        if re.search(r"(?:^|[;&|]\s*)git\s+commit(?:\s|$)", command):
            invocation = begin_commit_invocation(
                binding, snapshot, command=command, tool_call_id=tool_call_id
            )
            record["commit_invocation"] = asdict(invocation)
        calls[tool_call_id] = record
        return None

    def _post_tool_call(
        *, tool_name: str = "", args: Any = None, result: Any = None,
        task_id: str = "", session_id: str = "", tool_call_id: str = "",
        **_: Any,
    ) -> None:
        if task_id != TASK_ID or session_id != SESSION_ID:
            return None
        record = calls.setdefault(tool_call_id, {"tool_name": tool_name, "args": args})
        if tool_name != "terminal":
            record["result"] = result
            return None
        command = args.get("command", "") if isinstance(args, dict) else ""
        if record.get("command") != command:
            return None
        try:
            terminal = terminal_result_from_hermes_hook(
                tool_name=tool_name,
                args=args,
                result=result,
                task_id=task_id,
                session_id=session_id,
                turn_id=TURN_ID,
                tool_call_id=tool_call_id,
            )
        except Exception as exc:
            record["hook_error"] = type(exc).__name__
            return None
        record["terminal_result"] = asdict(terminal)
        if "test_invocation" in record:
            after = snapshot_repository(
                binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=TURN_ID
            )
            from workspace_contract import complete_test_invocation
            evidence = complete_test_invocation(
                binding,
                type_from_dict("TestInvocation", record["test_invocation"]),
                after,
                result=terminal,
            )
            record["test_evidence"] = asdict(evidence)
        return None

    manager = get_plugin_manager()
    manager._hooks.setdefault("pre_tool_call", []).append(_pre_tool_call)
    manager._hooks.setdefault("post_tool_call", []).append(_post_tool_call)

    def _next_response(_api_kwargs: Any = None, **_: Any) -> Any:
        if not responses:
            raise RuntimeError("scripted model response sequence was exhausted")
        return responses.pop(0)

    agent = AIAgent(
        api_key="offline-fixture-key",
        base_url="http://127.0.0.1:9/v1",
        provider="openai",
        model="gpt-4o-mini",
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        session_id=SESSION_ID,
        user_id="owner-fixture",
        enabled_toolsets=["terminal", "file"],
    )
    agent._disable_streaming = True
    agent._interruptible_api_call = _next_response
    try:
        result = agent.run_conversation(
            "Inspect this project, fix the failing test, run it, review the diff, then commit the fix.",
            task_id=TASK_ID,
        )
        payload = _jsonable({
            "completed": bool(result.get("completed")),
            "final_response": result.get("final_response", ""),
            "hermes_version": hermes_version,
            "capabilities": capabilities,
            "network_denied": network_denied,
            "private_paths_absent": True,
            "task_id": TASK_ID,
            "session_id": SESSION_ID,
            "turn_id": TURN_ID,
            "tool_calls": calls,
            "file_tool_calls": {
                key: {
                    "tool_name": value.get("tool_name"),
                    "args": value.get("args"),
                    "result": value.get("result"),
                }
                for key, value in calls.items()
                if value.get("tool_name") in {"read_file", "write_file"}
            },
            "responses_remaining": len(responses),
        })
        print("HADES_NATIVE_HERMES_RESULT=" + json.dumps(payload, sort_keys=True))
        return 0 if payload["completed"] and not responses else 1
    finally:
        manager._hooks["pre_tool_call"].remove(_pre_tool_call)
        manager._hooks["post_tool_call"].remove(_post_tool_call)


def type_from_dict(name: str, value: dict[str, Any]) -> Any:
    from workspace_contract import CommitInvocation, TestInvocation
    return {"TestInvocation": TestInvocation, "CommitInvocation": CommitInvocation}[name](**value)


if __name__ == "__main__":
    raise SystemExit(main())
