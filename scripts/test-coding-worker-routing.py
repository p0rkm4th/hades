#!/usr/bin/env python3
"""Focused intent boundary tests for the isolated coding lane."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.coding_worker import should_route_to_coding_worker  # noqa: E402


class CodingWorkerRoutingTests(unittest.TestCase):
    def test_workspace_requests_route(self) -> None:
        for prompt in (
            "inspect this repo and explain why the test is failing",
            "fix the failing test",
            "make the change and run the affected tests",
            "commit the fix",
        ):
            with self.subTest(prompt=prompt):
                self.assertTrue(should_route_to_coding_worker(prompt))

    def test_continuation_uses_recent_coding_context(self) -> None:
        history = [{"role": "user", "content": "Fix this repository test."}]
        self.assertTrue(should_route_to_coding_worker("continue after the failed command", history))
        self.assertTrue(should_route_to_coding_worker("check whether your last commit actually happened", history))
        self.assertTrue(should_route_to_coding_worker("revert the change you just made", history))

    def test_ordinary_chat_is_not_captured(self) -> None:
        for prompt in (
            "why do refrigerators get warm on the back?",
            "what is a neural network?",
            "what should I cook for dinner?",
        ):
            with self.subTest(prompt=prompt):
                self.assertFalse(should_route_to_coding_worker(prompt))

    def test_code_noun_alone_does_not_route(self) -> None:
        self.assertFalse(should_route_to_coding_worker("what is a Python snake?"))
        self.assertFalse(should_route_to_coding_worker("tell me about project management"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
