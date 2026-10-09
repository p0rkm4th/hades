"""Fail closed when Open WebUI cannot check or persist JWT revocation.

This build-time adapter targets the pinned Open WebUI 0.11.4 source. It is
intentionally strict: a source shape change fails the image build so upstream
can be reviewed before this compatibility layer is changed or removed.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path


AUTH_FILE = Path(
    os.environ.get("HADES_OPEN_WEBUI_AUTH_FILE", "/app/backend/open_webui/utils/auth.py")
)
MARKER = "# HADES_FAIL_CLOSED_TOKEN_REVOCATION"


REPLACEMENTS = {
    "is_valid_token": '''async def is_valid_token(decoded, redis=None) -> bool:
    """Raise service-unavailable when revocation state cannot be checked."""
    if redis is None:
        raise HTTPException(503, detail='Session verification unavailable.')

    try:
        jti = decoded.get('jti')
        if jti and await redis.get(f'{REDIS_KEY_PREFIX}:auth:token:{jti}:revoked'):
            return False

        user_id = decoded.get('id')
        if user_id:
            revoked_at = await redis.get(f'{REDIS_KEY_PREFIX}:auth:user:{user_id}:revoked_at')
            if revoked_at:
                revoked_at_ts = float(revoked_at)
                token_iat = decoded.get('iat')
                if token_iat is None or float(token_iat) <= revoked_at_ts:
                    return False
    except RedisError as error:
        log.error('Revocation check unavailable; rejecting token.')
        raise HTTPException(503, detail='Session verification unavailable.') from error
    except (TypeError, ValueError):
        log.error('Revocation marker is invalid; rejecting token.')
        return False

    return True
''',
    "invalidate_token": '''async def invalidate_token(request, token):
    decoded = decode_token(token)
    if not decoded:
        return

    redis = getattr(request.app.state, 'redis', None)
    if redis is None:
        raise HTTPException(503, detail='Session revocation unavailable; retry sign-out.')

    jti = decoded.get('jti')
    exp = decoded.get('exp')
    user_id = decoded.get('id')
    if not jti or not exp:
        raise HTTPException(503, detail='Session revocation unavailable; token metadata is incomplete.')

    ttl = exp - int(datetime.now(UTC).timestamp())
    if ttl <= 0:
        return

    try:
        # A repeated sign-out still retries socket disconnect after a prior
        # partial failure, but never rewrites a valid newer token's marker.
        if await is_valid_token(decoded, redis):
            await redis.set(f'{REDIS_KEY_PREFIX}:auth:token:{jti}:revoked', '1', ex=ttl)
    except RedisError as error:
        raise HTTPException(503, detail='Session revocation unavailable; retry sign-out.') from error

    if user_id:
        from open_webui.socket.main import disconnect_user_sessions

        await disconnect_user_sessions(user_id)
''',
    "revoke_user_tokens": '''async def revoke_user_tokens(request, user_id: str):
    """Durably invalidate a user's tokens or fail before authority changes."""
    redis = getattr(request.app.state, 'redis', None)
    if redis is None:
        raise HTTPException(503, detail='Session revocation unavailable; retry the operation.')

    expires_delta = parse_duration(await Config.get('auth.jwt_expiry'))
    # NumericDate in JWTs has one-second precision. The fractional marker
    # rejects existing same-second tokens; the login adapter waits until the
    # next second before issuing a replacement token after group reconciliation.
    revoked_at = datetime.now(UTC).timestamp()
    try:
        await redis.set(
            f'{REDIS_KEY_PREFIX}:auth:user:{user_id}:revoked_at',
            repr(revoked_at),
            ex=int(expires_delta.total_seconds()) if expires_delta else None,
        )
    except RedisError as error:
        raise HTTPException(503, detail='Session revocation unavailable; retry the operation.') from error

    from open_webui.socket.main import disconnect_user_sessions

    await disconnect_user_sessions(user_id)
''',
}


def replace_function(source: str, name: str, replacement: str) -> str:
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(functions) != 1:
        raise RuntimeError(f"Expected exactly one top-level {name} in pinned Open WebUI source")
    function = functions[0]
    lines = source.splitlines(keepends=True)
    start, end = function.lineno - 1, function.end_lineno
    lines[start:end] = [replacement.rstrip() + "\n\n"]
    return "".join(lines)


def apply() -> None:
    source = AUTH_FILE.read_text(encoding="utf-8")
    if MARKER in source:
        return
    if "from redis.exceptions import RedisError" not in source:
        anchor = "import requests\n"
        if source.count(anchor) != 1:
            raise RuntimeError("Open WebUI auth import layout changed; review this adapter")
        source = source.replace(anchor, anchor + "from redis.exceptions import RedisError\n", 1)

    # The exact pin currently contains these definitions in this order.
    for name, replacement in REPLACEMENTS.items():
        source = replace_function(source, name, replacement)

    if "from fastapi import HTTPException" not in source:
        tree = ast.parse(source)
        imports = [
            node for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "fastapi"
        ]
        if len(imports) != 1:
            raise RuntimeError("Open WebUI FastAPI import layout changed; review this adapter")
        node = imports[0]
        lines = source.splitlines(keepends=True)
        line = lines[node.lineno - 1]
        if "HTTPException" not in line:
            line = line.rstrip("\n")
            if line.endswith(")"):
                line = line[:-1] + ", HTTPException)\n"
            else:
                line = line + "\nfrom fastapi import HTTPException\n"
            lines[node.lineno - 1] = line
            source = "".join(lines)

    # The marker is included in the validation function contract for verifier checks.
    source = source.replace(
        "async def is_valid_token(decoded, redis=None) -> bool:\n",
        "async def is_valid_token(decoded, redis=None) -> bool:\n    " + MARKER + "\n",
        1,
    )
    ast.parse(source)
    AUTH_FILE.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    apply()
