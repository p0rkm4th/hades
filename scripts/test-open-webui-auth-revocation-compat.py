#!/usr/bin/env python3
"""Contract-check the fail-closed auth adapter against both tracked baselines."""

from __future__ import annotations

import ast
import asyncio
import os
import pathlib
import tempfile
import types


ROOT = pathlib.Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "webui" / "auth_revocation_fail_closed_compat.py"

LEGACY = '''import requests
from fastapi import HTTPException

async def is_valid_token(decoded, redis=None) -> bool:
    """Check whether a JWT has been revoked."""
    if redis:
        jti = decoded.get('jti')
        if jti and await redis.get(jti):
            return False
    return True

async def invalidate_token(request, token):
    decoded = decode_token(token)
    if not decoded:
        return
    # Require Redis to store revoked tokens
    if request.app.state.redis:
        await request.app.state.redis.set(decoded['jti'], '1')
\n'''

CANDIDATE = '''import requests
from fastapi import HTTPException
from redis.exceptions import RedisError

async def is_valid_token(decoded, redis=None) -> bool:
    """Check whether a JWT has been revoked."""
    if not redis:
        return True
    try:
        if await redis.get(decoded['jti']):
            return False
    except RedisError as e:
        revocation_log.warning('Revocation check failed; accepting token: %s', e)
    return True

async def invalidate_token(request, token):
    decoded = decode_token(token)
    if not decoded:
        return
    # Require Redis to store revoked tokens
    if request.app.state.redis:
        if not await is_valid_token(decoded, request.app.state.redis):
            return
        await request.app.state.redis.set(decoded['jti'], '1')
        user_id = decoded.get('id')
        if user_id:
            from open_webui.socket.main import disconnect_user_sessions
            await disconnect_user_sessions(user_id)
\n'''


class RedisError(Exception):
    pass


class TestHTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code


class FakeRedis:
    def __init__(self, error: Exception | None = None):
        self.error = error

    async def get(self, _key: str):
        if self.error:
            raise self.error
        return None


def patched_function(source: str, function_name: str):
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == function_name
    )
    return node


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hades-auth-revocation-contract-") as raw:
        temp = pathlib.Path(raw)
        for label, original in (("legacy", LEGACY), ("candidate", CANDIDATE)):
            auth_file = temp / f"{label}-auth.py"
            auth_file.write_text(original, encoding="utf-8")
            os.environ["HADES_OPEN_WEBUI_AUTH_FILE"] = str(auth_file)
            adapter_ns = {"__name__": "adapter"}
            exec(compile(ADAPTER.read_text(encoding="utf-8"), str(ADAPTER), "exec"), adapter_ns)
            adapter_ns["apply"]()
            first = auth_file.read_text(encoding="utf-8")
            adapter_ns = {"__name__": "adapter"}
            exec(compile(ADAPTER.read_text(encoding="utf-8"), str(ADAPTER), "exec"), adapter_ns)
            adapter_ns["apply"]()
            if auth_file.read_text(encoding="utf-8") != first:
                raise SystemExit(f"FAIL {label}: adapter is not idempotent")
            compile(first, str(auth_file), "exec")
            fn = patched_function(first, "is_valid_token")
            namespace = {"REDIS_KEY_PREFIX": "open-webui", "RedisError": RedisError,
                         "HTTPException": TestHTTPException,
                         "revocation_log": types.SimpleNamespace(warning=lambda *_: None)}
            exec(compile(ast.Module(body=[fn], type_ignores=[]), str(auth_file), "exec"), namespace)
            validate = namespace["is_valid_token"]
            if asyncio.run(validate({"jti": "synthetic"}, None)) is not False:
                raise SystemExit(f"FAIL {label}: missing Redis did not reject the token")
            if asyncio.run(validate({"jti": "synthetic"}, FakeRedis())) is not True:
                raise SystemExit(f"FAIL {label}: valid token was rejected with a healthy store")
            error_type = RedisError if label == "candidate" else OSError
            try:
                asyncio.run(validate({"jti": "synthetic"}, FakeRedis(error_type("offline"))))
            except TestHTTPException as error:
                if error.status_code != 503 or label != "candidate":
                    raise SystemExit(f"FAIL {label}: unexpected HTTP error {error.status_code}")
            except error_type:
                if label != "legacy":
                    raise SystemExit(f"FAIL {label}: Redis error was not translated to 503")
            else:
                raise SystemExit(f"FAIL {label}: store errors were accepted")
            invalidator = patched_function(first, "invalidate_token")
            invalidator_source = ast.get_source_segment(first, invalidator) or ""
            if "Session revocation unavailable" not in invalidator_source:
                raise SystemExit(f"FAIL {label}: sign-out does not report unavailable storage")
            if "disconnect_user_sessions" not in invalidator_source:
                raise SystemExit(f"FAIL {label}: sign-out does not disconnect live sessions")
            print(f"PASS {label} fail-closed token validation and revocation guards")


if __name__ == "__main__":
    main()
