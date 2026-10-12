#!/usr/bin/env python3
"""Focused intent boundary tests for the isolated coding lane."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.coding_worker import (  # noqa: E402
    coding_worker_conversation_allowed,
    should_route_to_coding_worker,
)


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

    def test_dogfood_allowlist_is_owner_conversation_and_domain_scoped(self) -> None:
        env = {
            "HADES_CODING_WORKER_ENABLED": "1",
            "HADES_CODING_WORKER_CONVERSATION_ID": "chat-123",
        }
        self.assertTrue(coding_worker_conversation_allowed(
            scope="owner", conversation_id="chat-123",
            prompt="Show the diff in this repository.", environ=env,
        ))
        self.assertFalse(coding_worker_conversation_allowed(
            scope="owner", conversation_id="other-chat",
            prompt="Show the diff in this repository.", environ=env,
        ))
        self.assertFalse(coding_worker_conversation_allowed(
            scope="household", conversation_id="chat-123",
            prompt="Show the diff in this repository.", environ=env,
        ))
        for prompt in (
            "what's in my kitchen?",
            "remember this repository setting",
            "what's in my network?",
            "calculate my bank spending",
        ):
            with self.subTest(prompt=prompt):
                self.assertFalse(coding_worker_conversation_allowed(
                    scope="owner", conversation_id="chat-123",
                    prompt=prompt, environ=env,
                ))


if __name__ == "__main__":
    unittest.main(verbosity=2)
