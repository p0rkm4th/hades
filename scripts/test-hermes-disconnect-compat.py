#!/usr/bin/env python3
"""Focused contract tests for Hermes' disconnected-stream hard cancel hook."""

import asyncio
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hermes import session_disconnect_compat


class HermesDisconnectCompatTests(unittest.TestCase):
    def test_active_agent_receives_hard_interrupt(self):
        class Adapter:
            async def _drain_session_stream_task_on_disconnect(
                self, run_id, task, *, interrupt_message, shield_wait
            ):
                pass

            def __init__(self, agent):
                self._active_run_agents = {"run-1": agent}

        class Agent:
            def __init__(self):
                self.calls = []

            def interrupt(self, message, *, hard_cancel=False):
                self.calls.append((message, hard_cancel))

        self.assertEqual(session_disconnect_compat.install(SimpleNamespace(APIServerAdapter=Adapter)), "installed")
        agent = Agent()

        async def scenario():
            task = asyncio.create_task(asyncio.sleep(0))
            await Adapter(agent)._drain_session_stream_task_on_disconnect(
                "run-1", task, interrupt_message="client disconnected", shield_wait=False
            )
            return task.done()

        self.assertTrue(asyncio.run(scenario()))
        self.assertEqual(agent.calls, [("client disconnected", True)])

    def test_missing_agent_cancels_pending_task(self):
        class Adapter:
            _active_run_agents = {}

            async def _drain_session_stream_task_on_disconnect(
                self, run_id, task, *, interrupt_message, shield_wait
            ):
                pass

        self.assertEqual(session_disconnect_compat.install(SimpleNamespace(APIServerAdapter=Adapter)), "installed")

        async def scenario():
            task = asyncio.create_task(asyncio.sleep(60))
            try:
                await Adapter()._drain_session_stream_task_on_disconnect(
                    "run-1", task, interrupt_message="client disconnected", shield_wait=False
                )
            except asyncio.CancelledError:
                pass
            self.assertTrue(task.cancelled())

        asyncio.run(scenario())

    def test_install_is_idempotent_and_native_hard_cancel_is_preserved(self):
        class Adapter:
            async def _drain_session_stream_task_on_disconnect(
                self, run_id, task, *, interrupt_message, shield_wait
            ):
                agent = self._active_run_agents.get(run_id)
                if agent is not None:
                    agent.interrupt(interrupt_message, hard_cancel=True)

        module = SimpleNamespace(APIServerAdapter=Adapter)
        self.assertEqual(session_disconnect_compat.install(module), "native")

        class SoftAdapter:
            async def _drain_session_stream_task_on_disconnect(self, run_id, task, *, interrupt_message, shield_wait):
                pass

        module = SimpleNamespace(APIServerAdapter=SoftAdapter)
        self.assertEqual(session_disconnect_compat.install(module), "installed")
        patched = SoftAdapter._drain_session_stream_task_on_disconnect
        self.assertEqual(session_disconnect_compat.install(module), "installed")
        self.assertIs(SoftAdapter._drain_session_stream_task_on_disconnect, patched)


if __name__ == "__main__":
    unittest.main()
