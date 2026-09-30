"""Resolve Operator access from a verified Open WebUI session and live LLDAP authority.

This is an authorization gate for a future private reverse proxy, not a proxy
or an authentication system. Browser identity and group headers are never
accepted as authority. The caller's session token is sent only to the
operator-configured Open WebUI session endpoint; its returned stable subject
is then resolved against current LLDAP membership on every request.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener, urlopen


MAX_TOKEN_CHARS = 4096
MAX_RESPONSE_BYTES = 64 * 1024
_SUBJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}\Z")
_COOKIE_TOKEN = re.compile(r"[A-Za-z0-9._~-]{1,4096}\Z")
_AGENT_ZERO_COOKIE_NAME = re.compile(r"(?:session|csrf_token)_[A-Za-z0-9._~-]{1,64}\Z")
_COOKIE_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}\Z")
_COOKIE_VALUE = re.compile(r"[\x21\x23-\x2B\x2D-\x3A\x3C-\x5B\x5D-\x7E]{0,4096}\Z")


class OperatorAuthorizationError(Exception):
    """Access was denied or current authority could not be established."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_NO_REDIRECT = build_opener(_NoRedirect())


def _session_token(headers: Any) -> str:
    """Extract one WebUI token from the request, rejecting ambiguous cookies."""
    authorization = headers.get("Authorization", "")
    if authorization:
        scheme, separator, token = authorization.partition(" ")
        if scheme.casefold() == "bearer" and separator and _COOKIE_TOKEN.fullmatch(token):
            return token
        raise OperatorAuthorizationError("authenticated Operator session required")

    cookie = headers.get("Cookie", "")
    if not isinstance(cookie, str) or len(cookie) > MAX_TOKEN_CHARS * 2:
        raise OperatorAuthorizationError("authenticated Operator session required")
    found: list[str] = []
    for item in cookie.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator and name.strip() == "token":
            found.append(value.strip())
    if len(found) != 1 or not _COOKIE_TOKEN.fullmatch(found[0]):
        raise OperatorAuthorizationError("authenticated Operator session required")
    return found[0]


def agent_zero_cookie(headers: Any) -> str:
    """Return only native Agent Zero cookies; never include WebUI cookies.

    The browser shares a cookie jar across localhost ports. The reverse proxy
    uses this value for its Agent Zero upstream request, while its WebUI route
    separately removes every cookie in these two Agent Zero namespaces.
    """
    cookie = headers.get("Cookie", "")
    if not isinstance(cookie, str) or len(cookie) > MAX_TOKEN_CHARS * 2:
        raise OperatorAuthorizationError("authenticated Operator session required")
    pairs = _cookie_pairs(cookie)
    kept = [(name, value) for name, value in pairs if _AGENT_ZERO_COOKIE_NAME.fullmatch(name)]
    return "; ".join(f"{name}={value}" for name, value in kept)


def webui_cookie(headers: Any) -> str:
    """Return request cookies for Open WebUI after removing Agent Zero cookies."""
    cookie = headers.get("Cookie", "")
    if not isinstance(cookie, str) or len(cookie) > MAX_TOKEN_CHARS * 2:
        raise OperatorAuthorizationError("cookie header is invalid")
    pairs = _cookie_pairs(cookie)
    return "; ".join(
        f"{name}={value}" for name, value in pairs
        if not _AGENT_ZERO_COOKIE_NAME.fullmatch(name)
    )


def _cookie_pairs(cookie: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in cookie.split(";"):
        item = item.strip()
        if not item:
            continue
        name, separator, value = item.partition("=")
        name = name.strip()
        value = value.strip()
        if not separator or not _COOKIE_NAME.fullmatch(name) or not _COOKIE_VALUE.fullmatch(value):
            raise OperatorAuthorizationError("cookie header is invalid")
        if name in seen:
            raise OperatorAuthorizationError("cookie header is ambiguous")
        seen.add(name)
        pairs.append((name, value))
    return pairs


def _session_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise ValueError("Open WebUI session endpoint is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"})
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("Open WebUI session endpoint must use HTTPS or local loopback HTTP")
    return value.rstrip("/") + "/api/v1/auths/"


def authorize_request(
    headers: Any,
    *,
    webui_endpoint: str,
    directory_authority: Callable[[str], Any],
    opener: Any | None = None,
    timeout: float = 4.0,
) -> dict[str, str]:
    """Return a stable subject only when WebUI and live LLDAP both authorize.

    `directory_authority(subject)` must perform an uncached current directory
    lookup and return an object with `mapped` and `role` fields. This function
    deliberately ignores any caller-supplied identity or group assertion.
    """
    if not 0.1 <= timeout <= 15:
        raise ValueError("Open WebUI session timeout is outside the allowed range")
    token = _session_token(headers)
    endpoint = _session_endpoint(webui_endpoint)
    request = Request(
        endpoint,
        headers={"Accept": "application/json", "Cookie": f"token={token}"},
        method="GET",
    )
    try:
        client = opener or _NO_REDIRECT
        with client.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, URLError, HTTPError, TimeoutError, ValueError) as exc:
        raise OperatorAuthorizationError("current Operator authority is unavailable") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise OperatorAuthorizationError("current Operator authority is unavailable")
    try:
        session = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OperatorAuthorizationError("current Operator authority is unavailable") from exc
    if not isinstance(session, dict):
        raise OperatorAuthorizationError("current Operator authority is unavailable")
    subject = session.get("id")
    email = session.get("email")
    if (
        not isinstance(subject, str)
        or not _SUBJECT.fullmatch(subject)
        or not isinstance(email, str)
        or not email.strip()
        or len(email) > 254
    ):
        raise OperatorAuthorizationError("authenticated Operator session required")

    try:
        authority = directory_authority(subject)
    except Exception as exc:
        raise OperatorAuthorizationError("current Operator authority is unavailable") from exc
    if (
        getattr(authority, "active", False) is not True
        or getattr(authority, "subject", None) != subject
        or getattr(authority, "role", None) not in {"owner", "admin"}
    ):
        raise OperatorAuthorizationError("Operator requires current owner authorization")
    return {"subject": subject}
