"""HADES compatibility for hard-cancelling disconnected Hermes gateway runs.

Hermes 0.21.6 drains a disconnected streaming task with a soft interrupt. That
can leave an executor-backed turn holding the session lease. Keep this repair
small and scoped to the gateway disconnect handler, and bypass it once Hermes
implements a hard interrupt natively.
"""

from __future__ import annotations

import asyncio
import ast
import inspect
import textwrap
from contextlib import suppress
from typing import Any


def _native_hard_interrupt(method: Any) -> bool:
    """Return true when this upstream handler already requests hard cancel."""
    try:
        source = textwrap.dedent(inspect.getsource(method))
    except (OSError, TypeError):
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = getattr(node.func, "attr", None)
        if function_name == "request_hard_interrupt":
            return True
        if function_name == "interrupt" and any(
            keyword.arg == "hard_cancel"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            return True
    return False


def install(api_server_module: Any, logger: Any = None) -> str:
    """Install the disconnect repair; return ``native``, ``installed`` or ``missing``."""
    adapter = getattr(api_server_module, "APIServerAdapter", None)
    if adapter is None:
        return "missing"

    current = getattr(adapter, "_drain_session_stream_task_on_disconnect", None)
    if current is None:
        return "missing"
    if getattr(current, "_hades_hard_disconnect", False):
        return "installed"
    if _native_hard_interrupt(current):
        return "native"

    async def drain_session_stream_task_on_disconnect(
        self: Any,
        run_id: str,
        task: "asyncio.Task[Any]",
        *,
        interrupt_message: str,
        shield_wait: bool,
    ) -> None:
        agent = self._active_run_agents.get(run_id)
        if agent is None:
            if not task.done():
                task.cancel()
                with suppress(Exception):
                    await task
            return
        with suppress(Exception):
            agent.interrupt(interrupt_message, hard_cancel=True)
        if not task.done():
            with suppress(Exception):
                await (asyncio.shield(task) if shield_wait else task)

    drain_session_stream_task_on_disconnect.__name__ = current.__name__
    drain_session_stream_task_on_disconnect.__qualname__ = current.__qualname__
    drain_session_stream_task_on_disconnect.__doc__ = current.__doc__
    drain_session_stream_task_on_disconnect._hades_hard_disconnect = True
    adapter._drain_session_stream_task_on_disconnect = drain_session_stream_task_on_disconnect
    if logger is not None:
        logger.info("HADES Hermes disconnect hard-cancel compatibility hook installed")
    return "installed"
