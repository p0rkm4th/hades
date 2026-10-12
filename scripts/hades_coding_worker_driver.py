#!/usr/bin/env python3
"""Run one trusted HADES coding turn with Hermes native tools in isolation."""

from __future__ import annotations

import json
import hashlib
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(sys.argv[1]).resolve(strict=True)
sys.path.insert(0, str(CONFIG_PATH.parent))
config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
sys.path.insert(0, config["hermes_source"])

from workspace_contract import (  # noqa: E402
    WorkspaceBinding,
    begin_commit_invocation,
    begin_test_invocation,
    complete_test_invocation,
    _recognized_test_command,
    snapshot_repository,
    terminal_result_from_hermes_hook,
)


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


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[-16:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            rows.append({"role": item["role"], "content": content[:8000]})
    return rows


def main() -> int:
    worker_started = time.perf_counter()
    diagnostics_enabled = os.environ.get("HADES_CODING_WORKER_DIAGNOSTICS", "").strip() == "1"
    capability_line = next(
        line for line in Path("/proc/self/status").read_text().splitlines()
        if line.startswith("CapEff:")
    )
    capability_mask = int(capability_line.split(":", 1)[1].strip(), 16)
    if capability_mask:
        raise RuntimeError("coding worker has effective capabilities")
    private_home = Path("/") / "home" / "scotty"
    canonical_checkout = Path("/") / "scootz" / "Workspaces" / "HADES"
    if private_home.exists() or canonical_checkout.exists():
        raise RuntimeError("private home or canonical HADES checkout is visible")
    if not Path("/run/hades-inference/model.sock").is_socket():
        raise RuntimeError("bounded inference relay socket is unavailable")

    workspace = Path.cwd().resolve(strict=True)
    if workspace != Path("/workspace").resolve(strict=True):
        raise RuntimeError("worker cwd does not match the isolated workspace")
    os.environ["HERMES_HOME"] = "/tmp/hermes-home"
    os.environ["HOME"] = "/tmp"
    os.environ["HADES_MODEL_BASE_URL"] = "http://127.0.0.1:18137/v1"
    home = Path(os.environ["HERMES_HOME"])
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    (home / "config.yaml").write_text(
        "terminal:\n  backend: local\n  cwd: /workspace\n  timeout: 60\n"
        "  persistent_shell: false\n",
        encoding="utf-8",
    )
    (home / "config.yaml").chmod(0o600)

    from hermes_cli.plugins import get_plugin_manager
    from run_agent import AIAgent
    import importlib.metadata

    version = importlib.metadata.version("hermes-agent")
    if version != "0.21.2":
        raise RuntimeError("coding worker requires the qualified Hermes 0.21.2 runtime")

    subject = config["subject"]
    session_id = config["session_id"]
    task_id = config["task_id"]
    turn_id = config["turn_id"]
    binding = WorkspaceBinding(subject, workspace, workspace)
    records: dict[str, dict[str, Any]] = {}
    tool_names: list[str] = []
    tool_trace: list[dict[str, Any]] = []
    trace_by_call: dict[str, dict[str, Any]] = {}
    agent = None

    def belongs_to_worker(task_id: str, session_id: str) -> bool:
        # The process owns one trusted task/session. Hermes creates its own turn
        # UUID, distinct from the HADES operation UUID in config.
        return task_id == config["task_id"] and session_id == config["session_id"]

    def pre_tool(*, tool_name: str = "", args: Any = None, task_id: str = "",
                 session_id: str = "", turn_id: str = "", tool_call_id: str = "", **_: Any) -> None:
        if isinstance(tool_name, str):
            tool_names.append(tool_name)
        if not belongs_to_worker(task_id, session_id) or not turn_id:
            return
        if diagnostics_enabled:
            test_command = (
                _recognized_test_command(args.get("command", ""))
                if tool_name == "terminal" and isinstance(args, dict) else None
            )
            kind = (
                "discovery" if tool_name in {"read_file", "read_many_files", "search_files", "list_directory"}
                else "edit" if tool_name in {"patch", "write_file", "create_file", "edit_file"}
                else "test" if test_command
                else "other"
            )
            safe_tool_name = tool_name[:64] if isinstance(tool_name, str) else "unknown"
            trace_row: dict[str, Any] = {
                "tool_name": safe_tool_name,
                "kind": kind,
                "start_ms": max(0, int((time.perf_counter() - worker_started) * 1000)),
                "elapsed_ms": None,
            }
            if kind == "discovery" and isinstance(args, (dict, list)):
                try:
                    encoded_args = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    if len(encoded_args) <= 8192:
                        trace_row["fingerprint"] = hashlib.sha256(
                            (safe_tool_name + "\0" + encoded_args).encode("utf-8")
                        ).hexdigest()
                except (TypeError, ValueError):
                    pass
            tool_trace.append(trace_row)
            if tool_call_id:
                trace_by_call[tool_call_id] = trace_row
        record: dict[str, Any] = {
            "tool_name": tool_name,
            "event_task_id": task_id,
            "event_session_id": session_id,
            "event_tool_call_id": tool_call_id,
        }
        if tool_name == "terminal" and isinstance(args, dict):
            command = args.get("command", "")
            test_command = _recognized_test_command(command)
            commit_command = bool(re.search(r"(?:^|[;&|]\s*)git\s+commit(?:\s|$)", command))
            if not test_command and not commit_command:
                records[tool_call_id] = record
                return
            record["command"] = command
            before = snapshot_repository(
                binding,
                task_id=config["task_id"],
                session_id=config["session_id"],
                turn_id=config["turn_id"],
            )
            if test_command:
                paths = {path for _, path in before.status_entries}
                if paths:
                    try:
                        record["test_invocation"] = _jsonable(begin_test_invocation(
                            binding, before, paths=paths, command=command, tool_call_id=tool_call_id,
                        ).__dict__)
                    except Exception as exc:
                        record["test_evidence_error"] = type(exc).__name__
            if commit_command:
                try:
                    record["commit_invocation"] = _jsonable(begin_commit_invocation(
                        binding, before, command=command, tool_call_id=tool_call_id,
                    ).__dict__)
                except Exception as exc:
                    record["commit_evidence_error"] = type(exc).__name__
        records[tool_call_id] = record

    def post_tool(*, tool_name: str = "", args: Any = None, result: Any = None,
                  task_id: str = "", session_id: str = "", turn_id: str = "",
                  tool_call_id: str = "", **_: Any) -> None:
        trace_row = trace_by_call.get(tool_call_id) if diagnostics_enabled else None
        if trace_row is not None and belongs_to_worker(task_id, session_id):
            trace_row["elapsed_ms"] = max(
                0, int((time.perf_counter() - worker_started) * 1000) - trace_row["start_ms"]
            )
        record = records.get(tool_call_id)
        if (record is None or not belongs_to_worker(task_id, session_id)
                or record.get("event_task_id") != task_id
                or record.get("event_session_id") != session_id
                or record.get("event_tool_call_id") != tool_call_id
                or not turn_id):
            return
        record["tool_name"] = tool_name
        if tool_name != "terminal" or not isinstance(args, dict):
            if agent is not None and not config.get("commit_authorized"):
                overrides = dict(getattr(agent, "request_overrides", {}) or {})
                if overrides.get("tool_choice") == "required":
                    overrides["tool_choice"] = "auto"
                    agent.request_overrides = overrides
            return
        try:
            operation = terminal_result_from_hermes_hook(
                tool_name=tool_name, args=args, result=result,
                task_id=config["task_id"], session_id=config["session_id"],
                turn_id=config["turn_id"], tool_call_id=tool_call_id,
            )
            record["terminal_result"] = _jsonable({
                **operation.__dict__,
                "output": "",
            })
            is_commit = bool(re.search(r"(?:^|[;&|]\s*)git\s+commit(?:\s|$)", args.get("command", "")))
            release_tool_choice = (
                not config.get("commit_authorized")
                or (is_commit and operation.completed and operation.exit_code == 0)
                or (is_commit and (not operation.completed or operation.exit_code is None))
            )
            if agent is not None and release_tool_choice:
                overrides = dict(getattr(agent, "request_overrides", {}) or {})
                if overrides.get("tool_choice") == "required":
                    overrides["tool_choice"] = "auto"
                    agent.request_overrides = overrides
            raw = record.get("test_invocation")
            if raw:
                from workspace_contract import TestInvocation
                invocation = TestInvocation(**{
                    **raw,
                    "workspace": Path(raw["workspace"]),
                    "repository": Path(raw["repository"]),
                    "paths": frozenset(raw["paths"]),
                })
                after = snapshot_repository(
                    binding, task_id=config["task_id"],
                    session_id=config["session_id"], turn_id=config["turn_id"],
                )
                evidence = complete_test_invocation(binding, invocation, after, result=operation)
                record["test_evidence"] = _jsonable({
                    **evidence.__dict__,
                    "output": "",
                })
        except Exception as exc:
            record["postcondition_error"] = type(exc).__name__
            if agent is not None and not config.get("commit_authorized"):
                overrides = dict(getattr(agent, "request_overrides", {}) or {})
                if overrides.get("tool_choice") == "required":
                    overrides["tool_choice"] = "auto"
                    agent.request_overrides = overrides

    agent = AIAgent(
        api_key="inference-only-local-relay",
        base_url=os.environ["HADES_MODEL_BASE_URL"],
        provider="custom",
        model=config["model"],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        skip_background_review=True,
        session_id=session_id,
        user_id=subject,
        enabled_toolsets=["terminal", "file"],
        max_iterations=20,
        max_tokens=1024,
        request_overrides={"tool_choice": "required"},
    )
    agent._disable_streaming = True
    agent.ephemeral_system_prompt = (
        "You are the coding worker for one authenticated HADES owner conversation. "
        "Use only /workspace and Hermes native file/terminal tools. Do not claim an edit, test, "
        "or commit unless the tool result confirms it. Never commit unless the current user request "
        "explicitly asks for a commit. Do not use network, install packages, or inspect outside "
        "/workspace. If a command fails, inspect and continue only after checking current state."
    )
    manager = get_plugin_manager()
    if not getattr(manager, "_discovered", True):
        manager.discover_and_load()
    manager._hooks.setdefault("pre_tool_call", []).append(pre_tool)
    manager._hooks.setdefault("post_tool_call", []).append(post_tool)
    try:
        result = agent.run_conversation(
            config["prompt"], conversation_history=_dict_rows(config.get("history")), task_id=task_id,
        )
        output = {
            "completed": bool(result.get("completed")),
            "final_response": str(result.get("final_response") or "")[:24_000],
            "tool_records": records,
            "tool_call_names": tool_names[:128],
            "tool_trace": tool_trace[:128] if diagnostics_enabled else [],
            "hermes_version": version,
            "subject": subject,
            "session_id": session_id,
            "task_id": task_id,
            "turn_id": turn_id,
            "hermes_turn_id": str(result.get("turn_id") or ""),
        }
        print("HADES_CODING_RESULT=" + json.dumps(output, sort_keys=True, default=str), flush=True)
        return 0 if output["completed"] else 1
    finally:
        manager._hooks["pre_tool_call"].remove(pre_tool)
        manager._hooks["post_tool_call"].remove(post_tool)


if __name__ == "__main__":
    raise SystemExit(main())
