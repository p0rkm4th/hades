#!/usr/bin/env python3
"""Contract-check fail-closed Open WebUI Socket.IO session eviction."""

from __future__ import annotations

import ast
import os
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "webui" / "socket_disconnect_fail_closed_compat.py"
UPSTREAM = '''import logging
log = logging.getLogger(__name__)

def get_session_ids_by_user_id(user_id: str):
    return []

class Socket:
    async def disconnect(self, sid):
        return None
sio = Socket()

async def disconnect_user_sessions(user_id: str):
    """Disconnect all Socket.IO sessions belonging to a user.

    Call this when a user's role is changed or the user is deleted so that
    stale role/permission data cached in SESSION_POOL is invalidated.
    The client will automatically reconnect and re-authenticate with
    fresh data from the database.
    """
    session_ids = get_session_ids_by_user_id(user_id)
    for sid in session_ids:
        try:
            await sio.disconnect(sid)
        except Exception:
            log.exception('Failed to disconnect session %s for user %s', sid, user_id)

    if session_ids:
        log.info('Requested disconnect of %s session(s) for user %s', len(session_ids), user_id)
'''


def function(source: str) -> str:
    tree = ast.parse(source)
    nodes = [node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "disconnect_user_sessions"]
    assert len(nodes) == 1
    return ast.get_source_segment(source, nodes[0]) or ""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hades-socket-revoke-contract-") as raw:
        target = pathlib.Path(raw) / "main.py"
        target.write_text(UPSTREAM, encoding="utf-8")
        os.environ["HADES_OPEN_WEBUI_SOCKET_MAIN"] = str(target)
        namespace = {"__name__": "socket_adapter"}
        exec(compile(ADAPTER.read_text(encoding="utf-8"), str(ADAPTER), "exec"), namespace)
        namespace["replace"]()
        first = target.read_text(encoding="utf-8")
        namespace = {"__name__": "socket_adapter"}
        exec(compile(ADAPTER.read_text(encoding="utf-8"), str(ADAPTER), "exec"), namespace)
        namespace["replace"]()
        assert target.read_text(encoding="utf-8") == first
        ast.parse(first)
        body = function(first)
        assert "HADES_SOCKET_DISCONNECT_FAIL_CLOSED_COMPAT" in body
        assert "Could not enumerate Socket.IO sessions" in body
        assert "if failures:" in body
        assert "HTTPException(503" in body
        assert "Requested disconnect" not in body
    print("PASS Socket.IO enumeration and disconnect failures propagate as HTTP 503")


if __name__ == "__main__":
    main()
