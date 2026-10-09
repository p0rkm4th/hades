#!/usr/bin/env python3
"""Contract-check the fail-closed JWT adapter's complete auth surface."""

from __future__ import annotations

import ast
import os
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "webui" / "auth_revocation_fail_closed_compat.py"
UPSTREAM_SHAPE = '''import requests
from fastapi import HTTPException
from redis.exceptions import RedisError

async def is_valid_token(decoded, redis=None) -> bool:
    """Check whether a JWT has been revoked."""
    return True

async def invalidate_token(request, token):
    return None

async def revoke_user_tokens(request, user_id: str):
    return None
'''


def function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    nodes = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    assert len(nodes) == 1, f"expected one {name} function"
    return ast.get_source_segment(source, nodes[0]) or ""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hades-auth-revocation-contract-") as raw:
        auth_file = pathlib.Path(raw) / "auth.py"
        auth_file.write_text(UPSTREAM_SHAPE, encoding="utf-8")
        os.environ["HADES_OPEN_WEBUI_AUTH_FILE"] = str(auth_file)

        namespace = {"__name__": "auth_adapter"}
        exec(compile(ADAPTER.read_text(encoding="utf-8"), str(ADAPTER), "exec"), namespace)
        namespace["apply"]()
        first = auth_file.read_text(encoding="utf-8")

        namespace = {"__name__": "auth_adapter"}
        exec(compile(ADAPTER.read_text(encoding="utf-8"), str(ADAPTER), "exec"), namespace)
        namespace["apply"]()
        assert auth_file.read_text(encoding="utf-8") == first, "adapter must be idempotent"
        ast.parse(first)

        valid = function_source(first, "is_valid_token")
        signout = function_source(first, "invalidate_token")
        revoke = function_source(first, "revoke_user_tokens")
        assert "HADES_FAIL_CLOSED_TOKEN_REVOCATION" in valid
        assert "if redis is None:" in valid and "HTTPException(503" in valid
        assert "except RedisError as error:" in valid and "HTTPException(503" in valid
        assert "except (TypeError, ValueError):" in valid and "return False" in valid
        assert "Fail open" not in valid and "accepting token" not in valid
        assert "Session revocation unavailable" in signout
        assert "await redis.set" in signout
        assert "Session revocation unavailable" in revoke
        assert "await redis.set" in revoke
        assert "repr(revoked_at)" in revoke
        assert "disconnect_user_sessions" in revoke

    print("PASS token validation, sign-out, and account-wide revocation fail closed")


if __name__ == "__main__":
    main()
