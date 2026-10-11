#!/usr/bin/env python3
"""Focused tests for fail-closed coding workspace and commit evidence."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workspace_test_sandbox import WorkspaceSandboxUnavailable, run_isolated_workspace  # noqa: E402
from hermes.workspace_contract import (  # noqa: E402
    WorkspaceDenied,
    WorkspaceEvidenceError,
    HermesTerminalResult,
    begin_commit_invocation,
    begin_test_invocation,
    complete_test_invocation,
    load_workspace_bindings,
    resolve_workspace_binding,
    snapshot_repository,
    terminal_result_from_hermes_hook,
    verify_commit,
    workspace_lease,
)


class WorkspaceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="hades-workspace-contract-")
        self.base = Path(self.tmp.name)
        self.repo = self.base / "owner-workspace"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "HADES Fixture")
        self.git("config", "user.email", "hades-fixture@example.invalid")
        (self.repo / "calc.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
        (self.repo / "test_calc.py").write_text(
            "import unittest\nfrom calc import answer\n\nclass AnswerTest(unittest.TestCase):\n    def test_answer(self):\n        self.assertEqual(answer(), 42)\n",
            encoding="utf-8",
        )
        self.git("add", "calc.py", "test_calc.py")
        self.git("commit", "-qm", "fixture")
        self.binding = resolve_workspace_binding(
            subject="owner-123",
            scope="owner",
            bindings={"owner-123": str(self.repo)},
            allowed_root=self.base,
        )
        self.turn_id = "contract-turn-001"
        self.before = self.snapshot()
        (self.repo / "calc.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        self.test_evidence = self.run_fixture_test({"calc.py"})
        self.git("add", "calc.py")
        self.commit_invocation = begin_commit_invocation(
            self.binding,
            self.snapshot(),
            command='git commit -m "requested fix"',
            tool_call_id="commit-tool-call-001",
        )

    def snapshot(self, binding=None):
        return snapshot_repository(
            binding or self.binding,
            task_id="hermes-task-001",
            session_id="conversation-001",
            turn_id=self.turn_id,
        )

    def require_namespace(self) -> None:
        try:
            run_isolated_workspace(self.binding.repository, ["true"])
        except WorkspaceSandboxUnavailable as exc:
            self.skipTest(str(exc))

    def terminal_result(self, tool_call_id, command, exit_code, *, completed=True):
        return HermesTerminalResult(
            task_id="hermes-task-001",
            session_id="conversation-001",
            turn_id=self.turn_id,
            tool_call_id=tool_call_id,
            command=command,
            exit_code=exit_code,
            output="trusted Hermes terminal result",
            completed=completed,
        )

    def run_fixture_test(self, paths: set[str]):
        pre_test = self.snapshot()
        invocation = begin_test_invocation(
            self.binding,
            pre_test,
            paths=paths,
            command="python3 -m unittest -q test_calc",
            tool_call_id="test-tool-call-001",
        )
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "-q", "test_calc"],
            cwd=self.binding.repository,
            capture_output=True,
            text=True,
            check=False,
        )
        return complete_test_invocation(
            self.binding,
            invocation,
            self.snapshot(),
            result=self.terminal_result(
                invocation.tool_call_id,
                invocation.command,
                completed.returncode,
            ),
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", "-C", str(cwd or self.repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        return result.stdout.strip()

    def commit(self, *paths: str) -> None:
        self.git("add", *paths)
        self.git("commit", "-qm", "requested fix")

    def verify(self, *, evidence=None, invocation=None, operation=None, binding=None, after=None):
        return verify_commit(
            binding or self.binding,
            invocation=self.commit_invocation if invocation is None else invocation,
            after=self.snapshot(binding) if after is None else after,
            test_evidence=self.test_evidence if evidence is None else evidence,
            operation=operation if operation is not None else self.terminal_result(
                "commit-tool-call-001", 'git commit -m "requested fix"', 0
            ),
            commit_requested=True,
        )

    def test_no_commit_is_failed_not_success(self) -> None:
        result = verify_commit(
            self.binding,
            invocation=None,
            after=self.snapshot(),
            test_evidence=self.test_evidence,
            operation=None,
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "FAILED")
        self.assertIn("no Hermes terminal commit invocation", result.reason)

    def test_failed_commit_is_not_success(self) -> None:
        failed = subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=", "-c", "user.email=", "commit", "-m", "requested"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(failed.returncode, 0)
        result = self.verify(
            operation=self.terminal_result(
                "commit-tool-call-001", 'git commit -m "requested fix"', failed.returncode
            )
        )
        self.assertEqual(result.outcome, "FAILED")

    def test_valid_commit_requires_exact_paths_and_tested_source(self) -> None:
        # test_calc.py is included as evidence but is unchanged; the commit's
        # intended paths are deliberately just the edited source file.
        evidence = self.test_evidence
        self.git("add", "calc.py")
        self.git("commit", "-qm", "requested fix")
        commit_returncode = 0
        result = verify_commit(
            self.binding,
            invocation=self.commit_invocation,
            after=self.snapshot(),
            test_evidence=evidence,
            operation=self.terminal_result(
                "commit-tool-call-001", 'git commit -m "requested fix"', commit_returncode
            ),
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "SUCCEEDED", result.reason)

    def test_wrong_repository_cannot_satisfy_operation(self) -> None:
        other = self.base / "other"
        other.mkdir()
        subprocess.run(["git", "-C", str(other), "init", "-q", "-b", "main"], check=True)
        subprocess.run(["git", "-C", str(other), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(other), "config", "user.email", "fixture@example.invalid"], check=True)
        (other / "calc.py").write_text("def answer(): return 42\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(other), "add", "calc.py"], check=True)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", "wrong repo"], check=True)
        wrong = resolve_workspace_binding(
            subject="owner-123", scope="owner", bindings={"owner-123": str(other)}, allowed_root=self.base
        )
        wrong_before = self.snapshot(wrong)
        # A commit in the wrong repo has no connection to the captured repo's HEAD.
        result = verify_commit(
            wrong,
            invocation=self.commit_invocation,
            after=self.snapshot(wrong),
            test_evidence=self.test_evidence,
            operation=self.terminal_result("commit-tool-call-001", 'git commit -m "requested fix"', 0),
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "VERIFY")
        self.assertNotEqual(wrong_before.head, self.before.head)

    def test_stale_prior_commit_is_not_a_new_commit(self) -> None:
        result = verify_commit(
            self.binding,
            invocation=self.commit_invocation,
            after=self.snapshot(),
            test_evidence=self.test_evidence,
            operation=self.terminal_result("commit-tool-call-001", 'git commit -m "requested fix"', 1),
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "FAILED")

    def test_ambiguous_commit_without_new_head_requires_verification(self) -> None:
        result = verify_commit(
            self.binding,
            invocation=self.commit_invocation,
            after=self.snapshot(),
            test_evidence=self.test_evidence,
            operation=None,
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "VERIFY")

    def test_other_tool_call_commit_cannot_satisfy_this_request(self) -> None:
        self.commit("calc.py")
        result = self.verify(
            operation=self.terminal_result(
                "another-task-commit", 'git commit -m "requested fix"', 0
            )
        )
        self.assertEqual(result.outcome, "VERIFY")

    def test_failed_commit_result_with_advanced_head_requires_reconciliation(self) -> None:
        self.commit("calc.py")
        result = self.verify(
            operation=self.terminal_result(
                "commit-tool-call-001", 'git commit -m "requested fix"', 1
            )
        )
        self.assertEqual(result.outcome, "VERIFY")

    def test_hermes_hook_result_uses_exact_server_call_identity(self) -> None:
        receipt = terminal_result_from_hermes_hook(
            tool_name="terminal",
            args={"command": "python3 -m unittest -q test_calc"},
            result='{"output":"anything","exit_code":0}',
            task_id="hermes-task-001",
            session_id="conversation-001",
            turn_id=self.turn_id,
            tool_call_id="trusted-tool-call-77",
        )
        self.assertEqual(receipt.tool_call_id, "trusted-tool-call-77")
        self.assertTrue(receipt.completed)
        with self.assertRaises(WorkspaceEvidenceError):
            terminal_result_from_hermes_hook(
                tool_name="terminal",
                args={"command": "pytest"},
                result="The tests passed.",
                task_id="hermes-task-001",
                session_id="conversation-001",
                turn_id=self.turn_id,
                tool_call_id="trusted-tool-call-78",
            )

    def test_same_workspace_turns_serialize_without_coupling_other_workspaces(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        second_entered = threading.Event()

        def hold_first():
            with workspace_lease(self.binding):
                entered.set()
                release.wait(timeout=2)

        def enter_second():
            with workspace_lease(self.binding):
                second_entered.set()

        first = threading.Thread(target=hold_first)
        second = threading.Thread(target=enter_second)
        first.start()
        self.assertTrue(entered.wait(timeout=1))
        second.start()
        self.assertFalse(second_entered.wait(timeout=0.05))
        other_repo = self.base / "independent"
        other_repo.mkdir()
        self.git("init", "-q", "-b", "main", cwd=other_repo)
        self.git("config", "user.name", "Workspace Test", cwd=other_repo)
        self.git("config", "user.email", "workspace-test@example.invalid", cwd=other_repo)
        (other_repo / "README").write_text("isolated\n", encoding="utf-8")
        self.git("add", "README", cwd=other_repo)
        self.git("commit", "-qm", "independent", cwd=other_repo)
        other_binding = resolve_workspace_binding(
            subject="other-owner", scope="owner", bindings={"other-owner": str(other_repo)},
            allowed_root=self.base,
        )
        with workspace_lease(other_binding):
            pass
        release.set()
        first.join(timeout=2)
        second.join(timeout=2)
        self.assertTrue(second_entered.is_set())

    def test_wrong_branch_fails_closed(self) -> None:
        self.git("switch", "-qc", "other")
        self.commit("calc.py")
        self.assertEqual(self.verify().outcome, "VERIFY")

    def test_unrelated_committed_path_fails_closed(self) -> None:
        (self.repo / "notes.txt").write_text("unrelated\n", encoding="utf-8")
        self.git("add", "calc.py", "notes.txt")
        self.git("commit", "-qm", "mixed commit")
        self.assertEqual(self.verify().outcome, "VERIFY")

    def test_edit_after_test_invalidates_test_evidence(self) -> None:
        evidence = self.test_evidence
        (self.repo / "calc.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
        self.git("add", "calc.py")
        self.git("commit", "-qm", "changed after test")
        result = self.verify(evidence=evidence)
        self.assertEqual(result.outcome, "VERIFY")
        self.assertIn("tested source differs", result.reason)

    def test_test_must_be_tied_to_preoperation_head(self) -> None:
        invalid = self.test_evidence
        object.__setattr__(invalid, "head", "0" * 40)
        self.commit("calc.py")
        self.assertEqual(self.verify(evidence=invalid).outcome, "VERIFY")

    def test_shell_echo_cannot_masquerade_as_test(self) -> None:
        with self.assertRaises(WorkspaceEvidenceError):
            begin_test_invocation(
                self.binding,
                self.before,
                paths={"calc.py"},
                command="echo 'pytest 1 passed'",
                tool_call_id="not-a-test-call",
            )

    def test_test_result_is_tied_to_actual_invocation_and_source(self) -> None:
        before_test = self.snapshot()
        invocation = begin_test_invocation(
            self.binding,
            before_test,
            paths={"calc.py"},
            command="python3 -m unittest -q test_calc",
            tool_call_id="test-tool-call-002",
        )
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "-q", "test_calc"],
            cwd=self.binding.repository,
            capture_output=True,
            text=True,
            check=False,
        )
        (self.repo / "calc.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
        with self.assertRaises(WorkspaceEvidenceError):
            complete_test_invocation(
                self.binding,
                invocation,
                self.snapshot(),
                result=self.terminal_result(
                    invocation.tool_call_id, invocation.command, completed.returncode
                ),
            )

    def test_wrong_terminal_result_id_cannot_complete_test(self) -> None:
        before_test = self.snapshot()
        invocation = begin_test_invocation(
            self.binding, before_test, paths={"calc.py"},
            command="python3 -m unittest -q test_calc", tool_call_id="test-tool-call-003"
        )
        with self.assertRaises(WorkspaceEvidenceError):
            complete_test_invocation(
                self.binding,
                invocation,
                self.snapshot(),
                result=self.terminal_result(
                    "different-tool-call", invocation.command, 0
                ),
            )

    def test_repository_fsmonitor_config_is_not_executed(self) -> None:
        marker = self.base / "fsmonitor-ran"
        helper = self.base / "fsmonitor.sh"
        helper.write_text(f"#!/bin/sh\ntouch {marker}\necho token\n", encoding="utf-8")
        helper.chmod(0o755)
        self.git("config", "core.fsmonitor", str(helper))
        self.snapshot()
        self.assertFalse(marker.exists())

    def test_ambiguous_missing_post_state_requires_reconciliation(self) -> None:
        result = verify_commit(
            self.binding,
            invocation=self.commit_invocation,
            after=None,
            test_evidence=self.test_evidence,
            operation=None,
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "VERIFY")

    def test_unknown_and_household_subjects_have_no_workspace(self) -> None:
        for subject, scope, bindings in (
            ("unknown", "owner", {"owner-123": str(self.repo)}),
            ("owner-123", "household", {"owner-123": str(self.repo)}),
        ):
            with self.subTest(subject=subject, scope=scope), self.assertRaises(WorkspaceDenied):
                resolve_workspace_binding(
                    subject=subject, scope=scope, bindings=bindings, allowed_root=self.base
                )

    def test_ambiguous_workspace_alias_is_denied(self) -> None:
        with self.assertRaises(WorkspaceDenied):
            resolve_workspace_binding(
                subject="owner-123",
                scope="owner",
                bindings={"owner-123": str(self.repo), "other-owner": str(self.repo)},
                allowed_root=self.base,
            )

    def test_workspace_overlapping_protected_source_checkout_is_denied(self) -> None:
        with self.assertRaises(WorkspaceDenied):
            resolve_workspace_binding(
                subject="owner-123",
                scope="owner",
                bindings={"owner-123": str(self.repo)},
                allowed_root=self.base,
                forbidden_roots=(self.base,),
            )

    def test_untrusted_mapping_file_is_denied(self) -> None:
        config = self.base / "bindings.json"
        config.write_text(
            '{"version":1,"bindings":{"owner-123":"' + str(self.repo) + '"}}',
            encoding="utf-8",
        )
        config.chmod(0o666)
        with self.assertRaises(WorkspaceDenied):
            load_workspace_bindings(config)

    def test_disposable_workspace_command_is_rootless_and_offline(self) -> None:
        self.require_namespace()
        result = run_isolated_workspace(
            self.binding.repository,
            [
                "python3",
                "-c",
                "import socket; s=socket.socket(); s.settimeout(1); "
                "caps=[x for x in open('/proc/self/status') if x.startswith('CapEff:')][0]; "
                "assert int(caps.split()[1], 16) == 0; "
                "\ntry: s.connect(('1.1.1.1', 53)); raise SystemExit(1)\n"
                "except OSError: raise SystemExit(0)",
            ],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        filesystem = run_isolated_workspace(
            self.binding.repository,
            ["python3", "-c", "import os; assert os.listdir('/home') == []"],
        )
        self.assertEqual(filesystem.returncode, 0, filesystem.stderr)
        denied_write = run_isolated_workspace(
            self.binding.repository,
            ["python3", "-c", "open('/usr/hades-boundary-probe', 'w').write('x')"],
        )
        self.assertNotEqual(denied_write.returncode, 0)
        workspace_write = run_isolated_workspace(
            self.binding.repository,
            ["python3", "-c", "open('/workspace/.boundary-probe', 'w').write('ok')"],
        )
        self.assertEqual(workspace_write.returncode, 0, workspace_write.stderr)
        (self.repo / ".boundary-probe").unlink()
        namespace = run_isolated_workspace(
            self.binding.repository,
            ["python3", "-c", "import os; print(os.readlink('/proc/self/ns/user'))"],
        )
        host_namespace = subprocess.check_output(
            ["python3", "-c", "import os; print(os.readlink('/proc/self/ns/user'))"], text=True
        ).strip()
        self.assertNotEqual(namespace.stdout.strip(), host_namespace)

    def test_disposable_workspace_timeout_is_reported_without_success(self) -> None:
        self.require_namespace()
        with self.assertRaises(RuntimeError):
            run_isolated_workspace(
                self.binding.repository,
                ["python3", "-c", "import time; time.sleep(10)"],
                timeout=1,
            )

    def test_explicit_runtime_mount_is_read_only_and_private_paths_are_absent(self) -> None:
        self.require_namespace()
        runtime = self.base / "runtime"
        runtime.mkdir()
        marker = runtime / "runtime-marker"
        marker.write_text("runtime", encoding="utf-8")
        result = run_isolated_workspace(
            self.binding.repository,
            [
                "python3",
                "-c",
                "from pathlib import Path; "
                "p=Path('" + str(marker) + "'); assert p.read_text() == 'runtime'; "
                "assert not Path('/home/scootz').exists(); "
                "p.write_text('changed')",
            ],
            read_only_paths=(runtime,),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(encoding="utf-8"), "runtime")

    def test_concurrent_namespaces_keep_workspace_mounts_separate(self) -> None:
        self.require_namespace()
        workspaces = []
        for label in ("left", "right"):
            workspace = self.base / f"concurrent-{label}"
            workspace.mkdir()
            (workspace / "identity").write_text(label, encoding="utf-8")
            workspaces.append((label, workspace))

        def execute(item):
            label, workspace = item
            return run_isolated_workspace(
                workspace,
                [
                    "python3",
                    "-c",
                    "from pathlib import Path; "
                    "assert Path.cwd() == Path('/workspace'); "
                    "p=Path('identity'); value=p.read_text(); "
                    "assert value == '" + label + "'; "
                    "Path('result').write_text(value)",
                ],
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute, workspaces))
        self.assertTrue(all(result.returncode == 0 for result in results))
        for label, workspace in workspaces:
            self.assertEqual((workspace / "result").read_text(encoding="utf-8"), label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
