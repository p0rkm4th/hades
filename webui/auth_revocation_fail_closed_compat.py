"""Keep Open WebUI session revocation fail-closed for HADES.

Open WebUI 0.11.4 accepts a JWT when its Redis revocation lookup fails. That
availability choice violates HADES's account/session revocation contract. This
build-time adapter makes a missing store reject tokens, preserves Redis errors
through validation, returns a visible 503 from sign-out when revocation cannot
be recorded, and disconnects the user's local live sessions on that failure.

Delete this adapter when upstream provides an equivalent fail-closed option.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


AUTH_FILE = Path(
    os.environ.get(
        "HADES_OPEN_WEBUI_AUTH_FILE",
        "/app/backend/open_webui/utils/auth.py",
    )
)
MARKER = "# HADES_FAIL_CLOSED_TOKEN_REVOCATION"


def function_bounds(lines: list[str], name: str) -> tuple[int, int]:
    tree = ast.parse("".join(lines))
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ),
        None,
    )
    if function is None:
        raise RuntimeError(f"Open WebUI auth function {name} is missing")
    return function.lineno - 1, function.end_lineno


def patch_valid_token(lines: list[str]) -> None:
    start, end = function_bounds(lines, "is_valid_token")
    body = lines[start:end]
    if any(MARKER in line for line in body):
        return

    tree = ast.parse("".join(lines))
    function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "is_valid_token"
    )
    doc = function.body[0] if function.body and isinstance(function.body[0], ast.Expr) else None
    if doc is None or not isinstance(getattr(doc, "value", None), ast.Constant) or not isinstance(doc.value.value, str):
        raise RuntimeError("Open WebUI token validator docstring changed; review adapter")

    insert_at = doc.end_lineno
    guard = [
        f"    {MARKER}: reject authentication without a revocation store.\n",
        "    if redis is None:\n",
        "        return False\n",
        "\n",
    ]
    lines[insert_at:insert_at] = guard

    tree = ast.parse("".join(lines))
    function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "is_valid_token"
    )
    handlers = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "RedisError"
    ]
    if len(handlers) > 1:
        raise RuntimeError("Open WebUI token validator has multiple RedisError handlers")
    if handlers:
        handler = handlers[0]
        if any(isinstance(node, ast.Raise) for node in ast.walk(handler)):
            raise RuntimeError("Open WebUI RedisError handler already raises; review adapter state")
        log_calls = [
            node for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"warning", "error"}
        ]
        if not log_calls:
            raise RuntimeError("Open WebUI RedisError handler changed; review adapter")
        # Upstream logs the Redis failure and then falls through to its final
        # `return True`. Return an explicit service-unavailable response so
        # callers see a transient auth-store outage instead of success or 500.
        lines[handler.end_lineno:handler.end_lineno] = [
            "        raise HTTPException(503, detail='Session verification unavailable.') from e\n"
        ]
        for index, line in enumerate(lines):
            lines[index] = line.replace(
                "Fail open on Redis errors to preserve availability; revoked tokens may be accepted.",
                "HADES fails closed when token-revocation storage is unavailable.",
            )

    # In the HADES 0.11.4 candidate this branch is now unreachable because of
    # the guard above. Change it too so the upstream source stays unambiguous.
    start, end = function_bounds(lines, "is_valid_token")
    segment = lines[start:end]
    if any("if not redis:" in line for line in segment):
        joined = "".join(segment)
        old = "    if not redis:\n        return True\n"
        if old in joined:
            joined = joined.replace(old, "    if not redis:\n        return False\n", 1)
            lines[start:end] = joined.splitlines(keepends=True)
    for index, line in enumerate(lines):
        lines[index] = line.replace(
            "Revocation check failed; accepting token:",
            "Revocation check failed; rejecting token:",
        )


def patch_invalidate_token(lines: list[str]) -> None:
    start, end = function_bounds(lines, "invalidate_token")
    segment = lines[start:end]
    if any(MARKER in line for line in segment):
        return

    source = "".join(segment)
    decoded_guard = "    if not decoded:\n        return\n"
    if source.count(decoded_guard) != 1:
        raise RuntimeError("Open WebUI invalidation entry guard changed; review adapter")

    fail_closed_block = (
        f"    {MARKER}: fail sign-out when the revocation store is absent.\n"
        "    if request.app.state.redis is None:\n"
        "        user_id = decoded.get('id')\n"
        "        if user_id:\n"
        "            from open_webui.socket.main import disconnect_user_sessions\n"
        "\n"
        "            await disconnect_user_sessions(user_id)\n"
        "        raise HTTPException(503, detail='Session revocation unavailable; retry sign-out.')\n"
        "\n"
    )
    source = source.replace(decoded_guard, decoded_guard + fail_closed_block, 1)

    # Redis failures must not turn a sign-out into a successful response while
    # leaving the JWT usable. Add one outer guard around the version-specific
    # Redis write/read path and disconnect that user's local active sessions.
    lines_body = source.splitlines(keepends=True)
    guard_index = next(
        i for i, line in enumerate(lines_body)
        if line.startswith("    if request.app.state.redis is None:")
    )
    before = lines_body[:guard_index]
    after = lines_body[guard_index:]
    # Keep the explicit missing-store rejection outside the RedisError handler.
    missing_end = next(
        i for i, line in enumerate(after)
        if line.startswith("    # Require Redis") or line.startswith("    # If Redis")
    ) if any(line.startswith("    # Require Redis") or line.startswith("    # If Redis") for line in after) else len(after)
    missing_block = after[:missing_end]
    redis_body = after[missing_end:]
    wrapped = ["    try:\n"] + [
        "    " + line if line.strip() else line
        for line in redis_body
    ]
    if "await disconnect_user_sessions(user_id)" not in "".join(redis_body):
        wrapped.extend(
            [
                "        user_id = decoded.get('id')\n",
                "        if user_id:\n",
                "            from open_webui.socket.main import disconnect_user_sessions\n",
                "\n",
                "            await disconnect_user_sessions(user_id)\n",
            ]
        )
    wrapped.extend(
        [
            "    except HTTPException as error:\n",
            "        if error.status_code != 503:\n",
            "            raise\n",
            "        user_id = decoded.get('id')\n",
            "        if user_id:\n",
            "            from open_webui.socket.main import disconnect_user_sessions\n",
            "\n",
            "            await disconnect_user_sessions(user_id)\n",
            "        raise\n",
            "    except RedisError as error:\n",
            "        user_id = decoded.get('id')\n",
            "        if user_id:\n",
            "            from open_webui.socket.main import disconnect_user_sessions\n",
            "\n",
            "            await disconnect_user_sessions(user_id)\n",
            "        raise HTTPException(503, detail='Session revocation unavailable; retry sign-out.') from error\n",
        ]
    )

    lines[start:end] = before + missing_block + wrapped


def apply() -> None:
    source = AUTH_FILE.read_text(encoding="utf-8")
    if "from redis.exceptions import RedisError" not in source:
        if "import requests\n" not in source:
            raise RuntimeError("Open WebUI auth imports changed; review adapter")
        source = source.replace(
            "import requests\n",
            "import requests\nfrom redis.exceptions import RedisError\n",
            1,
        )
    lines = source.splitlines(keepends=True)
    patch_valid_token(lines)
    patch_invalidate_token(lines)
    patched = "".join(lines)
    ast.parse(patched)
    AUTH_FILE.write_text(patched, encoding="utf-8")


if __name__ == "__main__":
    apply()
