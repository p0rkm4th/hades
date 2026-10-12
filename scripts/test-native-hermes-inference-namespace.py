#!/usr/bin/env python3
"""Real-model coding acceptance through a fixed Unix-socket inference relay.

This is an opt-in integration test. It reads the host's selected Hermes model
configuration, but neither mounts that configuration nor its credentials into
the worker namespace. The relay destination is fixed from that configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO / "hermes"))
from workspace_contract import (  # noqa: E402
    CommitInvocation,
    HermesTerminalResult,
    TestEvidence,
    WorkspaceBinding,
    snapshot_repository,
    verify_commit,
)
from workspace_test_sandbox import run_isolated_workspace  # noqa: E402
from model_inference_relay import parse_upstream  # noqa: E402


RESULT_PREFIX = "HADES_REAL_HERMES_RESULT="
TASK_ID = "inference-coding-task"
SESSION_ID = "inference-coding-session"
TURN_ID = "inference-coding-turn"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
        text=True, timeout=10,
    ).stdout.strip()


def _endpoint(config_path: Path) -> tuple[str, int, str, int, int, int]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    model = data.get("model") if isinstance(data, dict) else None
    if not isinstance(model, dict) or not isinstance(model.get("default"), str):
        raise RuntimeError("active Hermes model selection is unavailable")
    if model.get("provider") != "custom":
        raise RuntimeError("the first inference relay proof expects the active custom OpenAI-compatible provider")
    url = model.get("base_url")
    if not isinstance(url, str):
        raise RuntimeError("active inference endpoint is unavailable")
    address, port = parse_upstream(url)
    context_length = model.get("context_length")
    ollama_num_ctx = model.get("ollama_num_ctx")
    max_tokens = model.get("max_tokens")
    if (isinstance(context_length, bool) or not isinstance(context_length, int) or context_length < 64_000
            or isinstance(ollama_num_ctx, bool) or not isinstance(ollama_num_ctx, int)
            or ollama_num_ctx < 64_000 or isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int) or max_tokens < 1):
        raise RuntimeError("active profile does not declare Hermes' minimum model context")
    return address, port, model["default"], context_length, ollama_num_ctx, max_tokens


def _start_relay(socket_path: Path, host: str, port: int, model: str) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [sys.executable, str(_REPO / "scripts/model_inference_relay.py"),
         "--socket", str(socket_path), "--upstream", f"http://{host}:{port}/v1",
         "--model", model],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        if socket_path.is_socket():
            return process
        if process.poll() is not None:
            raise RuntimeError("fixed-destination inference relay exited during startup")
        time.sleep(0.1)
    process.terminate()
    raise RuntimeError("fixed-destination inference socket did not appear")


def _stop_relay(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _rebuild(raw: dict, workspace: Path) -> CommitInvocation:
    return CommitInvocation(
        subject=raw["subject"], workspace=workspace, repository=workspace,
        branch=raw["branch"], head=raw["head"],
        status_entries=frozenset(tuple(row) for row in raw["status_entries"]),
        expected_paths=frozenset(raw["expected_paths"]),
        source_fingerprint=raw["source_fingerprint"], command=raw["command"],
        task_id=raw["task_id"], session_id=raw["session_id"], turn_id=raw["turn_id"],
        tool_call_id=raw["tool_call_id"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    args = parser.parse_args()
    hermes_root = args.hermes_root.resolve(strict=True)
    endpoint_host, endpoint_port, model_id, context_length, ollama_num_ctx, max_tokens = _endpoint(
        args.model_config.resolve(strict=True)
    )
    # The coding recovery task needs enough completion budget for tool
    # selection plus concise progress. Keep this test-only budget bounded by
    # the configured context; do not change the production profile.
    max_tokens = min(max(max_tokens, 4096), context_length - 1)
    python = hermes_root / "venv/bin/python"
    if not python.exists():
        raise RuntimeError("Hermes venv interpreter is unavailable")

    with tempfile.TemporaryDirectory(prefix="hades-inference-coding-") as temp:
        root = Path(temp)
        support = root / "support"
        support.mkdir(mode=0o700)
        shutil.copyfile(_HERE / "native_hermes_inference_driver.py", support / "native_hermes_inference_driver.py")
        shutil.copyfile(_REPO / "hermes/workspace_contract.py", support / "workspace_contract.py")
        (support / "inference-config.json").write_text(json.dumps({
            "model": model_id,
            "provider": "custom",
            "context_length": context_length,
            "ollama_num_ctx": ollama_num_ctx,
            "max_tokens": max_tokens,
            "endpoint_ip": endpoint_host,
            "endpoint_port": endpoint_port,
            "hermes_root": str(hermes_root),
            "contract_root": str(support),
        }), encoding="utf-8")
        (support / "inference-config.json").chmod(0o400)

        workspace = root / "workspace"
        workspace.mkdir(mode=0o700)
        _git(workspace, "init", "-q", "-b", "main")
        _git(workspace, "config", "user.name", "HADES Inference Fixture")
        _git(workspace, "config", "user.email", "inference-fixture@example.invalid")
        (workspace / "calc.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
        (workspace / "test_calc.py").write_text(
            "import unittest\nfrom calc import answer\n\n"
            "class AnswerTest(unittest.TestCase):\n"
            "    def test_answer(self):\n        self.assertEqual(answer(), 42)\n",
            encoding="utf-8",
        )
        _git(workspace, "add", "calc.py", "test_calc.py")
        _git(workspace, "commit", "-qm", "fixture")
        binding = WorkspaceBinding("owner-disposable-fixture", workspace, workspace)
        before = snapshot_repository(binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=TURN_ID)

        relay_dir = root / "relay"
        relay_dir.mkdir(mode=0o700)
        socket_path = relay_dir / "model.sock"
        relay = _start_relay(socket_path, endpoint_host, endpoint_port, model_id)
        try:
            result = run_isolated_workspace(
                workspace,
                [str(python), str(support / "native_hermes_inference_driver.py")],
                timeout=600,
                read_only_paths=(hermes_root, support),
                unix_socket=socket_path,
                enable_loopback=True,
                writable_git_metadata=True,
            )
        finally:
            _stop_relay(relay)
        lines = [line for line in result.stdout.splitlines() if line.startswith(RESULT_PREFIX)]
        if result.returncode or not lines:
            raise RuntimeError(
                "real-model Hermes worker failed; "
                f"exit={result.returncode}, stderr={result.stderr[-3000:]}, stdout={result.stdout[-3000:]}"
            )
        payload = json.loads(lines[-1][len(RESULT_PREFIX):])
        if (payload.get("hermes_version") != "0.21.2" or not payload.get("completed")
                or payload.get("capabilities") != "0000000000000000"
                or payload.get("network_blocked") != [
                    "internet", "arbitrary-lan", "model-direct", "ssh", "grocy",
                    "open-webui", "dns", "unapproved-loopback-port"
                ]):
            raise RuntimeError("real-model namespace assertions failed")

        calls = payload.get("tool_calls", {})
        tests = [row for row in calls.values() if "test_evidence" in row]
        commits = [row for row in calls.values() if "commit_invocation" in row]
        writes = [row for row in calls.values()
                  if row.get("tool_name") in {"write_file", "patch", "edit_file"}]
        reads = [row for row in calls.values() if row.get("tool_name") == "read_file"]
        diffs = [row for row in calls.values() if row.get("tool_name") == "terminal"
                 and "git diff" in str(row.get("args", {}).get("command", ""))]
        successful_tests = [
            row for row in tests
            if row.get("test_evidence", {}).get("exit_code") == 0
            and row.get("test_evidence", {}).get("head") == before.head
            and row.get("terminal_result", {}).get("exit_code") == 0
        ]
        failed_tests = [
            row for row in tests
            if row.get("test_evidence", {}).get("exit_code") not in (None, 0)
            and row.get("terminal_result", {}).get("exit_code") not in (None, 0)
        ]
        bad_path_recovered = any(
            "test_missing" in str(row.get("args", {}).get("command", ""))
            and row.get("terminal_result", {}).get("exit_code") not in (None, 0)
            for row in calls.values()
        )
        if not successful_tests or len(commits) != 1 or not writes or not reads or not diffs:
            summary = [
                (row.get("tool_name"),
                 str((row.get("args") or {}).get("command", ""))[:180]
                 if isinstance(row.get("args"), dict) else "")
                for row in calls.values()
            ]
            raise RuntimeError(
                "real Hermes turn did not exercise inspect/edit/test/diff/commit; "
                f"completed={payload.get('completed')}, counts="
                f"tests:{len(tests)} successful_tests:{len(successful_tests)} commits:{len(commits)} "
                f"edits:{len(writes)} reads:{len(reads)} diffs:{len(diffs)}, "
                f"tool_calls={summary}, "
                f"final={str(payload.get('final_response', ''))[:500]}"
            )
        if not bad_path_recovered or not failed_tests:
            raise RuntimeError(
                "real model did not recover from both the intentional command error "
                "and the fixture's initial failing test"
            )
        passed_test = successful_tests[-1]

        commit_row = commits[0]
        invocation = _rebuild(commit_row["commit_invocation"], workspace)
        if invocation.head != before.head or invocation.branch != "main":
            raise RuntimeError("commit evidence used stale or wrong-branch state")
        operation = HermesTerminalResult(**commit_row["terminal_result"])
        after = snapshot_repository(
            binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=invocation.turn_id
        )
        verification = verify_commit(
            binding, invocation=invocation, after=after,
            test_evidence=TestEvidence(
                **{**passed_test["test_evidence"], "workspace": workspace, "repository": workspace,
                   "paths": frozenset(passed_test["test_evidence"]["paths"])}
            ),
            operation=operation, commit_requested=True,
        )
        changed = _git(workspace, "diff-tree", "--no-commit-id", "--name-only", "-r", after.head).splitlines()
        if (verification.outcome != "SUCCEEDED" or changed != ["calc.py"]
                or _git(workspace, "status", "--porcelain")
                or _git(workspace, "rev-parse", "HEAD^1") != before.head):
            raise RuntimeError(
                "canonical post-commit repository verification failed; "
                f"outcome={verification.outcome}, reason={verification.reason}, "
                f"changed={changed}, status={_git(workspace, 'status', '--porcelain')!r}, "
                f"before={before.head}, commit_before={invocation.head}, after={after.head}, "
                f"expected={sorted(invocation.expected_paths)}, "
                f"test_exit={passed_test['test_evidence'].get('exit_code')}, "
                f"test_head={passed_test['test_evidence'].get('head')}, "
                f"test_turn={passed_test['test_evidence'].get('turn_id')}, "
                f"commit_turn={invocation.turn_id}, operation_exit={operation.exit_code}"
            )

        outage = run_isolated_workspace(
            workspace,
            [str(python), "-c",
             "import socket\n"
             "for host,port in [('127.0.0.1',18137),('1.1.1.1',443)]:\n"
             " try: socket.create_connection((host,port),timeout=.5); raise SystemExit('unexpected route')\n"
             " except OSError: pass\n"],
            timeout=30,
            read_only_paths=(hermes_root,),
            enable_loopback=True,
        )
        if outage.returncode or _git(workspace, "rev-parse", "HEAD") != after.head:
            raise RuntimeError("inference outage did not fail closed without workspace mutation")

        # Independently rerun the focused test after commit, in a fresh offline namespace.
        post_test = run_isolated_workspace(
            workspace,
            [str(python), "-m", "unittest", "-q"],
            timeout=120,
            read_only_paths=(hermes_root,),
        )
        if post_test.returncode:
            raise RuntimeError("post-commit focused test failed in the offline namespace")

        print(json.dumps({
            "hermes_version": "0.21.2",
            "model_inference": "PASS",
            "inference_transport": "fixed Unix-socket relay",
            "general_network": "DENIED",
            "network_probes": "PASS",
            "native_inspect_edit_test_diff_commit": "PASS",
            "commit_verification": verification.outcome,
            "branch": after.branch,
            "changed_paths": changed,
            "post_commit_test": "PASS",
            "inference_outage": "SAFE; no mutation",
            "final_response": payload.get("final_response", "")[:1000],
        }, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
