"""Make Socket.IO session eviction errors visible to security-sensitive callers.

Open WebUI 0.11.4 logs and suppresses disconnect failures, and Redis-backed
session enumeration can raise before its per-session handler. Authority changes
must not proceed unless every discovered socket was disconnected.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


SOCKET_MAIN = Path(
    os.environ.get("HADES_OPEN_WEBUI_SOCKET_MAIN", "/app/backend/open_webui/socket/main.py")
)
MARKER = "HADES_SOCKET_DISCONNECT_FAIL_CLOSED_COMPAT"
OLD = '''async def disconnect_user_sessions(user_id: str):
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
NEW = '''async def disconnect_user_sessions(user_id: str):
    """Disconnect every known session or fail the caller closed."""
    from fastapi import HTTPException

    # HADES_SOCKET_DISCONNECT_FAIL_CLOSED_COMPAT
    try:
        session_ids = get_session_ids_by_user_id(user_id)
    except Exception as error:
        log.exception('Could not enumerate Socket.IO sessions for user %s', user_id)
        raise HTTPException(503, detail='Session revocation incomplete; retry the operation.') from error

    failures = []
    for sid in session_ids:
        try:
            await sio.disconnect(sid)
        except Exception as error:
            failures.append((sid, error))
            log.exception('Failed to disconnect session %s for user %s', sid, user_id)

    if failures:
        raise HTTPException(503, detail='Session revocation incomplete; retry the operation.')
    if session_ids:
        log.info('Disconnected %s session(s) for user %s', len(session_ids), user_id)
'''


def replace() -> None:
    source = SOCKET_MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "disconnect_user_sessions"
    ]
    if len(functions) != 1:
        raise RuntimeError("Expected one pinned Open WebUI disconnect_user_sessions function")
    node = functions[0]
    lines = source.splitlines(keepends=True)
    start, end = node.lineno - 1, node.end_lineno
    segment = "".join(lines[start:end])
    if MARKER in segment:
        return
    if segment != OLD:
        raise RuntimeError("Open WebUI socket disconnect source changed; review this adapter")
    lines[start:end] = [NEW + "\n"]
    patched = "".join(lines)
    ast.parse(patched)
    SOCKET_MAIN.write_text(patched, encoding="utf-8")


if __name__ == "__main__":
    replace()
