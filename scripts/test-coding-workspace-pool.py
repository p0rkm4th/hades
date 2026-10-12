#!/usr/bin/env python3
"""Tests server-side subject/session resolution to separate disposable clones."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.coding_workspace_pool import resolve_session_workspace  # noqa: E402
from hermes.workspace_contract import WorkspaceDenied


class CodingWorkspacePoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="hades-coding-pool-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir(mode=0o700)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Fixture Owner")
        self.git("config", "user.email", "owner@example.invalid")
        (self.source / "app.py").write_text("def answer(): return 42\n", encoding="utf-8")
        self.git("add", "app.py")
        self.git("commit", "-qm", "fixture")
        self.workspace_root = self.root / "workspaces"
        self.workspace_root.mkdir(mode=0o700)
        self.mapping = self.root / "bindings.json"
        self.mapping.write_text(json.dumps({"version": 1, "bindings": {"owner-1": str(self.source)}}))
        self.mapping.chmod(0o600)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.source), *args], check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()

    def resolve(self, conversation: str, *, subject: str = "owner-1", scope: str = "owner"):
        return resolve_session_workspace(
            subject=subject, scope=scope, conversation_id=conversation,
            bindings_file=self.mapping, workspace_root=self.workspace_root,
        )

    def test_one_conversation_reuses_its_clone(self) -> None:
        first = self.resolve("conversation-one")
        self.assertNotEqual(first.root, self.source)
        (first.root / "app.py").write_text("def answer(): return 43\n", encoding="utf-8")
        second = self.resolve("conversation-one")
        self.assertEqual(first.root, second.root)
        self.assertEqual(
            (second.root / "app.py").read_text(encoding="utf-8"),
            "def answer(): return 43\n",
        )
        self.assertEqual(
            (self.source / "app.py").read_text(encoding="utf-8"),
            "def answer(): return 42\n",
        )
        result = subprocess.run(
            ["git", "-C", str(first.root), "config", "user.name"],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(result.stdout.strip(), "Fixture Owner")

    def test_distinct_conversations_get_independent_clones(self) -> None:
        first = self.resolve("conversation-one")
        second = self.resolve("conversation-two")
        self.assertNotEqual(first.root, second.root)
        (first.root / "app.py").write_text("def answer(): return 43\n", encoding="utf-8")
        self.assertEqual((second.root / "app.py").read_text(encoding="utf-8"), "def answer(): return 42\n")
        self.assertEqual((self.source / "app.py").read_text(encoding="utf-8"), "def answer(): return 42\n")

    def test_unknown_and_household_subjects_fail_closed(self) -> None:
        with self.assertRaises(WorkspaceDenied):
            self.resolve("conversation-one", subject="unknown")
        with self.assertRaises(WorkspaceDenied):
            self.resolve("conversation-one", scope="household")

    def test_protected_source_is_denied(self) -> None:
        with self.assertRaises(WorkspaceDenied):
            resolve_session_workspace(
                subject="owner-1", scope="owner", conversation_id="conversation-one",
                bindings_file=self.mapping, workspace_root=self.workspace_root,
                forbidden_roots=(self.source,),
            )

    def test_missing_conversation_identity_is_denied_and_path_text_is_hashed(self) -> None:
        with self.assertRaises(WorkspaceDenied):
            self.resolve("")
        binding = self.resolve("../outside")
        self.assertTrue(binding.root.is_relative_to(self.workspace_root))


if __name__ == "__main__":
    unittest.main(verbosity=2)
