#!/usr/bin/env python3
"""Run native Hermes in the rootless workspace namespace and verify its Git effects."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CONTRACT = _HERE / "workspace_contract.py"
if not _CONTRACT.is_file():
    sys.path.insert(0, str(_HERE.parent / "hermes"))
from workspace_contract import (
    CommitInvocation,
    HermesTerminalResult,
    TestEvidence,
    WorkspaceBinding,
    snapshot_repository,
    verify_commit,
)
from workspace_test_sandbox import run_isolated_workspace


TASK_ID = "namespace-coding-task"
SESSION_ID = "namespace-coding-session"
TURN_ID = "namespace-coding-turn"
RESULT_PREFIX = "HADES_NATIVE_HERMES_RESULT="


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _path_set(values: list[str]) -> frozenset[str]:
    return frozenset(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", type=Path, required=True)
    args = parser.parse_args()
    hermes_root = args.hermes_root.resolve(strict=True)
    python = hermes_root / "venv/bin/python"
    if not python.is_file():
        raise SystemExit("Hermes venv Python is absent")

    with tempfile.TemporaryDirectory(prefix="hades-native-hermes-support-") as support_tmp:
        support_dir = Path(support_tmp)
        shutil.copyfile(_HERE / "native_hermes_namespace_driver.py", support_dir / "native_hermes_namespace_driver.py")
        contract_source = _CONTRACT if _CONTRACT.is_file() else _HERE.parent / "hermes/workspace_contract.py"
        shutil.copyfile(contract_source, support_dir / "workspace_contract.py")

        with tempfile.TemporaryDirectory(prefix="hades-native-hermes-workspace-") as tmp:
            workspace = Path(tmp) / "owner-project"
            workspace.mkdir()
            _git(workspace, "init", "-q", "-b", "main")
            _git(workspace, "config", "user.name", "HADES Namespace Fixture")
            _git(workspace, "config", "user.email", "namespace-fixture@example.invalid")
            (workspace / "calc.py").write_text(
                "def answer():\n    return 41\n", encoding="utf-8"
            )
            (workspace / "test_calc.py").write_text(
                "import unittest\nfrom calc import answer\n\n"
                "class AnswerTest(unittest.TestCase):\n"
                "    def test_answer(self):\n"
                "        self.assertEqual(answer(), 42)\n",
                encoding="utf-8",
            )
            _git(workspace, "add", "calc.py", "test_calc.py")
            _git(workspace, "commit", "-qm", "fixture")

            binding = WorkspaceBinding("owner-fixture", workspace, workspace)
            before = snapshot_repository(
                binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=TURN_ID
            )
            driver = support_dir / "native_hermes_namespace_driver.py"
            result = run_isolated_workspace(
                workspace,
                [str(python), str(driver)],
                timeout=180,
                read_only_paths=(hermes_root, support_dir),
            )
            lines = [line for line in result.stdout.splitlines() if line.startswith(RESULT_PREFIX)]
            if result.returncode != 0 or not lines:
                raise RuntimeError(
                    "native Hermes namespace task failed; "
                    f"exit={result.returncode}, stderr={result.stderr[-4000:]}, "
                    f"stdout={result.stdout[-4000:]}"
                )
            payload = json.loads(lines[-1][len(RESULT_PREFIX):])
            if (
                payload.get("hermes_version") != "0.21.2"
                or payload.get("task_id") != TASK_ID
                or payload.get("session_id") != SESSION_ID
                or payload.get("turn_id") != TURN_ID
                or not payload.get("completed")
                or payload.get("responses_remaining") != 0
                or payload.get("network_denied") is not True
                or payload.get("private_paths_absent") is not True
                or payload.get("capabilities") != "0000000000000000"
            ):
                raise RuntimeError("native Hermes runtime or namespace assertions failed")

            calls = payload.get("tool_calls", {})
            file_calls = payload.get("file_tool_calls", {})
            read_calls = [record for record in file_calls.values() if record.get("tool_name") == "read_file"]
            write_calls = [record for record in file_calls.values() if record.get("tool_name") == "write_file"]
            if len(read_calls) != 2 or len(write_calls) != 1:
                raise RuntimeError("Hermes native file tools did not perform the expected reads and edit")
            try:
                read_payloads = [json.loads(record["result"]) for record in read_calls]
                write_payload = json.loads(write_calls[0]["result"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("Hermes native file tool returned no structured trusted result") from exc
            if sorted(payload.get("content", "") for payload in read_payloads) != sorted((
                "1|def answer():\n2|    return 41\n3|",
                "1|import unittest\n2|from calc import answer\n3|\n4|class AnswerTest(unittest.TestCase):\n5|    def test_answer(self):\n6|        self.assertEqual(answer(), 42)\n7|",
            )):
                raise RuntimeError("Hermes native file reads did not return the fixture source")
            if (
                write_calls[0].get("args", {}).get("path") != "calc.py"
                or write_payload.get("verified") is not True
                or write_payload.get("resolved_path") != "/workspace/calc.py"
            ):
                raise RuntimeError("Hermes native file edit did not verify the expected workspace path")
            test_records = [record for record in calls.values() if "test_evidence" in record]
            commit_records = [record for record in calls.values() if "commit_invocation" in record]
            if len(test_records) != 1 or len(commit_records) != 1:
                raise RuntimeError("Hermes lifecycle evidence did not capture exactly one test and commit")
            test_record = test_records[0]
            commit_record = commit_records[0]
            if test_record.get("terminal_result", {}).get("exit_code") != 0:
                raise RuntimeError("Hermes focused test did not pass")
            if not any(
                record.get("terminal_result", {}).get("exit_code", 0) != 0
                and "cinder-sandbox-probe" in record.get("command", "")
                and "FileNotFoundError" in record.get("terminal_result", {}).get("output", "")
                for record in calls.values()
            ):
                raise RuntimeError("Hermes did not exercise the denied outside-write continuation")
            if not any(
                record.get("terminal_result", {}).get("exit_code") == 0
                and "CapEff" in record.get("command", "")
                and "capabilities=none" in record.get("terminal_result", {}).get("output", "")
                and "private-paths=absent" in record.get("terminal_result", {}).get("output", "")
                for record in calls.values()
            ):
                raise RuntimeError("Hermes terminal process did not prove zero capabilities and absent private paths")
            if not any(
                record.get("terminal_result", {}).get("exit_code") == 0
                and "1.1.1.1" in record.get("command", "")
                and "network-denied" in record.get("terminal_result", {}).get("output", "")
                for record in calls.values()
            ):
                network_records = [
                    record for record in calls.values()
                    if "1.1.1.1" in record.get("command", "")
                ]
                raise RuntimeError(
                    "Hermes terminal process did not prove network denial: "
                    f"{network_records}"
                )

            raw_commit = commit_record["commit_invocation"]
            invocation = CommitInvocation(
                subject=raw_commit["subject"],
                workspace=workspace,
                repository=workspace,
                branch=raw_commit["branch"],
                head=raw_commit["head"],
                status_entries=frozenset(tuple(item) for item in raw_commit["status_entries"]),
                expected_paths=_path_set(raw_commit["expected_paths"]),
                command=raw_commit["command"],
                task_id=raw_commit["task_id"],
                session_id=raw_commit["session_id"],
                turn_id=raw_commit["turn_id"],
                tool_call_id=raw_commit["tool_call_id"],
            )
            if invocation.head != before.head:
                raise RuntimeError("unexpected commit occurred before the explicit commit request")
            raw_test = test_record["test_evidence"]
            evidence = TestEvidence(
                subject=raw_test["subject"],
                workspace=workspace,
                repository=workspace,
                branch=raw_test["branch"],
                head=raw_test["head"],
                paths=_path_set(raw_test["paths"]),
                source_fingerprint=raw_test["source_fingerprint"],
                command=raw_test["command"],
                exit_code=raw_test["exit_code"],
                output=raw_test["output"],
                task_id=raw_test["task_id"],
                session_id=raw_test["session_id"],
                turn_id=raw_test["turn_id"],
                tool_call_id=raw_test["tool_call_id"],
            )
            raw_operation = commit_record["terminal_result"]
            operation = HermesTerminalResult(**raw_operation)
            after = snapshot_repository(
                binding, task_id=TASK_ID, session_id=SESSION_ID, turn_id=TURN_ID
            )
            verification = verify_commit(
                binding,
                invocation=invocation,
                after=after,
                test_evidence=evidence,
                operation=operation,
                commit_requested=True,
            )
            if verification.outcome != "SUCCEEDED":
                raise RuntimeError(f"independent commit postcondition failed: {verification}")
            if _git(workspace, "branch", "--show-current") != "main":
                raise RuntimeError("commit landed on the wrong branch")
            if _git(workspace, "status", "--porcelain"):
                raise RuntimeError("workspace is not clean after the requested commit")

            print(json.dumps({
                "hermes_version": payload["hermes_version"],
                "hermes_loop": "PASS",
                "outside_write_denial": "PASS",
                "network_denial": "PASS",
                "private_paths_absent": "PASS",
                "effective_capabilities": payload["capabilities"],
                "edit_test_diff_commit": "PASS",
                "commit_verification": verification.outcome,
                "commit": after.head,
                "branch": after.branch,
                "changed_paths": sorted(verification.committed_paths),
                "working_tree": "CLEAN",
                "native_file_results": {
                    key: str(record.get("result"))[:500]
                    for key, record in file_calls.items()
                },
            }, sort_keys=True))
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
