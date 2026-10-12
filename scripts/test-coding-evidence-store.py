#!/usr/bin/env python3
"""Verify private, actor/session-bound persistence for test receipts."""

from __future__ import annotations

import hashlib
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.coding_evidence_store import (  # noqa: E402
    _MAX_AGE_SECONDS,
    clear_test_evidence,
    load_test_evidence,
    store_test_evidence,
)
from hermes.workspace_contract import (  # noqa: E402
    HermesTerminalResult,
    TestEvidence,
    WorkspaceBinding,
    begin_commit_invocation,
    begin_test_invocation,
    complete_test_invocation,
    snapshot_repository,
    verify_commit,
)


class CodingEvidenceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hades-coding-evidence-")
        self.parent = Path(self.temp.name) / "workspaces"
        self.parent.mkdir(mode=0o700)
        self.subject = "synthetic-owner"
        self.session = "conversation-a"
        self.binding = self.make_binding(self.subject, self.session)
        self.evidence = TestEvidence(
            subject=self.subject,
            workspace=self.binding.root,
            repository=self.binding.repository,
            branch="main",
            head="a" * 40,
            paths=frozenset({"calc.py"}),
            source_fingerprint="b" * 64,
            command="python3 -m unittest -q test_calc",
            exit_code=0,
            output="not persisted",
            task_id="test-task-1",
            session_id=self.session,
            turn_id="test-turn-1",
            tool_call_id="test-call-1",
        )

    def make_binding(self, subject: str, session: str) -> WorkspaceBinding:
        key = hashlib.sha256((subject + "\0" + session).encode()).hexdigest()
        workspace = self.parent / key
        workspace.mkdir(mode=0o700)
        return WorkspaceBinding(subject, workspace, workspace)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_receipt_is_private_and_reusable_only_for_same_session(self) -> None:
        store_test_evidence(self.binding, self.session, self.evidence, now=1000)
        receipt = self.parent / (self.binding.root.name + ".test-evidence.json")
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        loaded = load_test_evidence(self.binding, self.session, now=1001)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task_id, "test-task-1")
        self.assertEqual(loaded.output, "")
        self.assertFalse(receipt.is_relative_to(self.binding.root))

        other_session = "conversation-b"
        other_binding = self.make_binding(self.subject, other_session)
        self.assertIsNone(load_test_evidence(other_binding, other_session, now=1001))

    def test_expired_receipt_is_ignored(self) -> None:
        store_test_evidence(self.binding, self.session, self.evidence, now=1000)
        self.assertIsNone(
            load_test_evidence(
                self.binding, self.session,
                now=1000 + _MAX_AGE_SECONDS + 1,
            )
        )

    def test_receipt_verifies_commit_across_hermes_task_ids(self) -> None:
        binding = self.make_binding("commit-owner", "commit-conversation")

        def git(*args: str) -> str:
            result = subprocess.run(
                ["git", "-C", str(binding.repository), *args],
                check=True, capture_output=True, text=True,
            )
            return result.stdout.strip()

        (binding.root / "calc.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
        (binding.root / "test_calc.py").write_text(
            "import unittest\nfrom calc import answer\n"
            "class AnswerTest(unittest.TestCase):\n"
            " def test_answer(self): self.assertEqual(answer(), 42)\n",
            encoding="utf-8",
        )
        git("init", "-q", "-b", "main")
        git("config", "user.name", "Fixture Owner")
        git("config", "user.email", "fixture@example.invalid")
        git("add", "calc.py", "test_calc.py")
        git("commit", "-qm", "fixture")
        (binding.root / "calc.py").write_text("def answer():\n    return 42\n", encoding="utf-8")

        session = "commit-conversation"
        test_before = snapshot_repository(
            binding, task_id="test-task", session_id=session, turn_id="test-turn-001",
        )
        test_invocation = begin_test_invocation(
            binding, test_before, paths={"calc.py"},
            command="python3 -m unittest -q test_calc", tool_call_id="test-call",
        )
        test_run = subprocess.run(
            [sys.executable, "-m", "unittest", "-q", "test_calc"],
            cwd=binding.root, capture_output=True, text=True,
        )
        self.assertEqual(test_run.returncode, 0, test_run.stderr)
        test_evidence = complete_test_invocation(
            binding, test_invocation,
            snapshot_repository(
                binding, task_id="test-task", session_id=session, turn_id="test-turn-001",
            ),
            result=HermesTerminalResult(
                "test-task", session, "test-turn-001", "test-call",
                test_invocation.command, test_run.returncode, test_run.stderr, True,
            ),
        )
        store_test_evidence(binding, session, test_evidence)
        cached = load_test_evidence(binding, session)
        self.assertIsNotNone(cached)

        git("add", "calc.py")
        commit_before = snapshot_repository(
            binding, task_id="commit-task", session_id=session, turn_id="commit-turn-001",
        )
        command = 'git commit -m "fix answer"'
        invocation = begin_commit_invocation(
            binding, commit_before, command=command, tool_call_id="commit-call",
        )
        git("commit", "-qm", "fix answer")
        after = snapshot_repository(
            binding, task_id="commit-task", session_id=session, turn_id="commit-turn-001",
        )
        result = verify_commit(
            binding, invocation=invocation, after=after, test_evidence=cached,
            operation=HermesTerminalResult(
                "commit-task", session, "commit-turn-001", "commit-call",
                command, 0, "commit created", True,
            ),
            commit_requested=True,
        )
        self.assertEqual(result.outcome, "SUCCEEDED", result.reason)

    def test_malformed_or_symlink_receipt_fails_closed(self) -> None:
        receipt = self.parent / (self.binding.root.name + ".test-evidence.json")
        receipt.write_text("{}", encoding="utf-8")
        receipt.chmod(0o600)
        self.assertIsNone(load_test_evidence(self.binding, self.session))
        receipt.unlink()
        target = self.parent / "other.json"
        target.write_text("{}", encoding="utf-8")
        target.chmod(0o600)
        receipt.symlink_to(target)
        self.assertIsNone(load_test_evidence(self.binding, self.session))

    def test_clear_removes_receipt(self) -> None:
        store_test_evidence(self.binding, self.session, self.evidence)
        clear_test_evidence(self.binding, self.session)
        self.assertIsNone(load_test_evidence(self.binding, self.session))


if __name__ == "__main__":
    unittest.main(verbosity=2)
