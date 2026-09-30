#!/usr/bin/env python3
"""Synthetic contract for the future Agent Zero private proxy identity gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "operator_session_auth", ROOT / "integrations/operator-access/session_auth.py"
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class SessionEndpoint:
    def __init__(self, body: bytes | None = None, error: Exception | None = None) -> None:
        self.body = body or json.dumps(
            {"id": "webui-owner-01", "email": "owner@example.test", "role": "user"}
        ).encode()
        self.error = error
        self.requests = []

    def open(self, request, timeout: float) -> Response:  # type: ignore[no-untyped-def]
        self.requests.append(request)
        assert timeout == 4.0
        if self.error:
            raise self.error
        return Response(self.body)


def denied(call, contains: str) -> None:  # type: ignore[no-untyped-def]
    try:
        call()
    except module.OperatorAuthorizationError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError("authorization unexpectedly passed")


def main() -> None:
    owner = SimpleNamespace(
        subject="webui-owner-01", role="owner", active=True, resources=frozenset()
    )
    endpoint = SessionEndpoint()
    calls: list[str] = []

    def authority(subject: str):
        calls.append(subject)
        return owner

    headers = {
        "Cookie": "session=unrelated; token=abc.def_123",
        # These spoofed values must not affect authorization or be forwarded.
        "X-Hades-Authenticated-User": "attacker",
        "X-Hades-Authenticated-Groups": "hades-owner",
    }
    result = module.authorize_request(
        headers,
        webui_endpoint="http://127.0.0.1:8080",
        directory_authority=authority,
        opener=endpoint,
    )
    assert result == {"subject": "webui-owner-01"}
    assert calls == ["webui-owner-01"]
    assert len(endpoint.requests) == 1
    request = endpoint.requests[0]
    assert request.full_url == "http://127.0.0.1:8080/api/v1/auths/"
    assert request.get_header("Cookie") == "token=abc.def_123"
    assert request.get_header("X-hades-authenticated-groups") is None
    assert module.agent_zero_cookie({
        "Cookie": "token=webui.secret; session_runtime-01=agent.session; csrf_token_runtime-01=csrf.value; unrelated=drop"
    }) == "session_runtime-01=agent.session; csrf_token_runtime-01=csrf.value"
    assert module.agent_zero_cookie({"Cookie": "token=webui.secret; unrelated=drop"}) == ""
    assert module.webui_cookie({
        "Cookie": "token=webui.secret; session_runtime-01=agent.session; csrf_token_runtime-01=csrf.value; preference=dark"
    }) == "token=webui.secret; preference=dark"
    for raw_cookie, reason in (
        ("session_runtime-01=one; session_runtime-01=two", "cookie header"),
        ("session_runtime-01=bad value", "cookie header"),
        ("x" * (module.MAX_TOKEN_CHARS * 2 + 1), "authenticated Operator"),
    ):
        denied(
            lambda value=raw_cookie: module.agent_zero_cookie({"Cookie": value}),
            reason,
        )
    # Repeated invocations repeat the live directory resolution; there is no cache.
    module.authorize_request(
        headers,
        webui_endpoint="http://127.0.0.1:8080",
        directory_authority=authority,
        opener=endpoint,
    )
    assert calls == ["webui-owner-01", "webui-owner-01"]

    denied(
        lambda: module.authorize_request(
            {"X-Hades-Authenticated-Groups": "hades-owner"},
            webui_endpoint="http://127.0.0.1:8080",
            directory_authority=authority,
            opener=endpoint,
        ),
        "authenticated Operator session required",
    )
    denied(
        lambda: module.authorize_request(
            {"Cookie": "token=one; token=two"},
            webui_endpoint="http://127.0.0.1:8080",
            directory_authority=authority,
            opener=endpoint,
        ),
        "authenticated Operator session required",
    )

    household = SimpleNamespace(
        subject="webui-owner-01", role="household", active=True, resources=frozenset()
    )
    denied(
        lambda: module.authorize_request(
            {"Authorization": "Bearer abc.def_123"},
            webui_endpoint="http://localhost:8080/",
            directory_authority=lambda _subject: household,
            opener=SessionEndpoint(),
        ),
        "current owner authorization",
    )
    stale = SimpleNamespace(
        subject="webui-owner-01", role="owner", active=False, resources=frozenset()
    )
    denied(
        lambda: module.authorize_request(
            {"Authorization": "Bearer abc.def_123"},
            webui_endpoint="http://localhost:8080",
            directory_authority=lambda _subject: stale,
            opener=SessionEndpoint(),
        ),
        "current owner authorization",
    )
    foreign = SimpleNamespace(
        subject="different-user", role="owner", active=True, resources=frozenset()
    )
    denied(
        lambda: module.authorize_request(
            {"Authorization": "Bearer abc.def_123"},
            webui_endpoint="http://localhost:8080",
            directory_authority=lambda _subject: foreign,
            opener=SessionEndpoint(),
        ),
        "current owner authorization",
    )
    denied(
        lambda: module.authorize_request(
            {"Authorization": "Bearer abc.def_123"},
            webui_endpoint="http://localhost:8080",
            directory_authority=authority,
            opener=SessionEndpoint(error=HTTPError("http://127.0.0.1", 401, "unauthorized", {}, None)),
        ),
        "current Operator authority is unavailable",
    )
    for value in ("http://webui.internal", "https://user:pass@example.test"):
        try:
            module.authorize_request(
                {"Cookie": "token=abc"},
                webui_endpoint=value,
                directory_authority=authority,
                opener=SessionEndpoint(),
            )
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe Open WebUI endpoint was accepted")

    print("PASS Operator requires a verified Open WebUI session")
    print("PASS caller-supplied identity/group headers do not grant or cross the trust boundary")
    print("PASS current LLDAP owner/admin role and subject binding are required per request")
    print("PASS household, stale, mismatched, unauthenticated, and upstream-error cases fail closed")
    print("PASS Open WebUI session tokens are sent only to a validated HTTPS/loopback endpoint")
    print("PASS cookie allowlists prevent cross-forwarding between WebUI and Agent Zero")


if __name__ == "__main__":
    main()
