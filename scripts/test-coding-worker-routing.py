#!/usr/bin/env python3
"""Focused intent boundary tests for the isolated coding lane."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes.coding_worker import (  # noqa: E402
    CodingWorkerError,
    coding_worker_conversation_allowed,
    should_route_to_coding_worker,
    _workspace_mutation_authorized,
    _explicit_commit,
    _coding_trace_summary,
    _attach_worker_diagnostics,
    _validate_worker_result_identity,
)


class CodingWorkerRoutingTests(unittest.TestCase):
    def test_opt_in_worker_diagnostics_contain_only_tool_names_and_timing(self) -> None:
        result = {
            "tool_call_names": ["terminal", "read_file", "terminal"],
            "tool_trace": [{"tool_name": "read_file", "kind": "discovery",
                            "start_ms": 4, "elapsed_ms": 2,
                            "fingerprint": "a" * 64}],
        }
        with patch.dict("os.environ", {"HADES_CODING_WORKER_DIAGNOSTICS": "1"}), \
             patch("hermes.coding_worker._LOGGER.info") as log_info:
            enriched = _attach_worker_diagnostics(result, task_id="task-1", started_at=0.0)
        self.assertEqual(enriched["task_id"], "task-1")
        self.assertGreaterEqual(enriched["elapsed_ms"], 0)
        self.assertNotIn("tool_trace", enriched)
        self.assertNotIn("a" * 64, repr(enriched))
        self.assertIn("first_tool_ms=%s", log_info.call_args.args[0])
        self.assertEqual(log_info.call_args.args[-1], "terminal,read_file,terminal")

    def test_worker_diagnostics_are_silent_by_default(self) -> None:
        result = {
            "tool_call_names": ["terminal"],
            "tool_trace": [{"tool_name": "read_file", "fingerprint": "b" * 64}],
        }
        with patch.dict("os.environ", {"HADES_CODING_WORKER_DIAGNOSTICS": "0"}), \
             patch("hermes.coding_worker._LOGGER.info") as log_info:
            enriched = _attach_worker_diagnostics(result, task_id="task-1", started_at=0.0)
        log_info.assert_not_called()
        self.assertNotIn("tool_trace", enriched)
        self.assertNotIn("b" * 64, repr(enriched))

    def test_coding_trace_summary_measures_discovery_edit_and_test_without_arguments(self) -> None:
        summary = _coding_trace_summary({"tool_trace": [
            {"tool_name": "search_files", "kind": "discovery", "start_ms": 10,
             "elapsed_ms": 5, "fingerprint": "a" * 64},
            {"tool_name": "search_files", "kind": "discovery", "start_ms": 20,
             "elapsed_ms": 4, "fingerprint": "a" * 64},
            {"tool_name": "read_file", "kind": "discovery", "start_ms": 30,
             "elapsed_ms": 3, "fingerprint": "b" * 64},
            {"tool_name": "patch", "kind": "edit", "start_ms": 40, "elapsed_ms": 2},
            {"tool_name": "terminal", "kind": "test", "start_ms": 50, "elapsed_ms": 100},
        ]})
        self.assertEqual(summary, {
            "tool_calls": 5,
            "first_tool_ms": 10,
            "first_file_ms": 10,
            "first_edit_ms": 40,
            "first_test_ms": 50,
            "test_calls": 1,
            "test_ms": 100,
            "tool_ms": 114,
            "duplicate_discovery_calls": 1,
        })

    def test_commit_authority_respects_current_turn_negation(self) -> None:
        for prompt in (
            "Make a plausible correction, but do not commit yet.",
            "Make the change and don't commit it.",
            "Fix the test without committing the fix.",
            "Please hold off on committing until I review the diff.",
        ):
            with self.subTest(prompt=prompt):
                self.assertFalse(_explicit_commit(prompt))
        for prompt in (
            "Commit the fix.",
            "Make the change and commit it.",
            "Please commit this after the tests pass.",
            "Commit only calc.py now.",
            "Commit only calc.py now; leave __pycache__ out.",
        ):
            with self.subTest(prompt=prompt):
                self.assertTrue(_explicit_commit(prompt))

        for prompt in (
            "Should we commit only calc.py now?",
            "I could commit only calc.py now.",
            "The instruction was to commit only calc.py now.",
        ):
            with self.subTest(prompt=prompt):
                self.assertFalse(_explicit_commit(prompt))

    def test_worker_result_requires_hades_ids_but_not_hermes_turn_id(self) -> None:
        result = {
            "subject": "owner-1",
            "session_id": "conversation-1",
            "task_id": "task-1",
            "turn_id": "hades-turn-1",
            "completed": True,
        }
        self.assertIs(
            _validate_worker_result_identity(
                result,
                subject="owner-1",
                session_id="conversation-1",
                task_id="task-1",
                turn_id="hades-turn-1",
            ),
            result,
        )
        for key, value in (
            ("subject", "other-owner"),
            ("session_id", "other-conversation"),
            ("task_id", "other-task"),
            ("turn_id", "other-turn"),
        ):
            with self.subTest(key=key):
                mismatched = dict(result, **{key: value})
                with self.assertRaises(CodingWorkerError):
                    _validate_worker_result_identity(
                        mismatched,
                        subject="owner-1",
                        session_id="conversation-1",
                        task_id="task-1",
                        turn_id="hades-turn-1",
                    )

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

    def test_read_only_diagnosis_does_not_authorize_workspace_mutation(self) -> None:
        for prompt in (
            "Inspect this project and explain why the test fails.",
            "Why is this test failing?",
            "Show me what changed.",
            "Review the diff.",
        ):
            with self.subTest(prompt=prompt):
                self.assertFalse(_workspace_mutation_authorized(prompt, []))
        self.assertTrue(_workspace_mutation_authorized("Fix the failing test.", []))
        self.assertTrue(_workspace_mutation_authorized("Could you please fix this bug?", []))
        self.assertTrue(_workspace_mutation_authorized("I need you to change this function.", []))
        self.assertTrue(_workspace_mutation_authorized("Run the focused test.", []))
        self.assertTrue(_workspace_mutation_authorized(
            "Make a plausible first correction that remains incomplete.", []
        ))
        self.assertFalse(_workspace_mutation_authorized(
            "Tell me how to make a correction to this function.", []
        ))
        self.assertFalse(_workspace_mutation_authorized("Commit the fix.", []))
        self.assertFalse(_workspace_mutation_authorized("Do not edit anything; just inspect it.", []))

    def test_continuation_inherits_only_recent_edit_or_test_intent(self) -> None:
        self.assertTrue(_workspace_mutation_authorized(
            "continue after the failed command",
            [{"role": "user", "content": "Fix the failing test."}],
        ))
        self.assertFalse(_workspace_mutation_authorized(
            "continue after the failed command",
            [{"role": "user", "content": "Inspect this project and explain the failure."}],
        ))
        self.assertFalse(_workspace_mutation_authorized(
            "Show me what changed.",
            [{"role": "user", "content": "Fix the failing test."}],
        ))
        self.assertFalse(_workspace_mutation_authorized(
            "Review the diff.",
            [{"role": "user", "content": "Make the change and run the focused test."}],
        ))

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
