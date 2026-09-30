"""Authenticated, bounded request contract for the Phase 3 runner."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from http.server import BaseHTTPRequestHandler
from typing import Callable
from typing import Any, Mapping

from .phase3_self_service import Phase3AuthorizationError, Phase3Error, Phase3Runner


RUN_PATH = "/v1/epsilon/phase3/run"
DUE_PATH = "/v1/epsilon/phase3/due"
RESULTS_PATH = "/v1/epsilon/phase3/results"
MAX_BODY_BYTES = 2048
MAX_CLOCK_SKEW_SECONDS = 120


class Phase3RequestError(Phase3Error):
    """Request authentication or shape is invalid."""


def sign_request(secret: bytes, timestamp: str, raw_body: bytes) -> str:
    """Return a path-bound signature; callers must send this exact body."""
    return _sign_path(secret, RUN_PATH, timestamp, raw_body)


def sign_due_request(secret: bytes, timestamp: str, raw_body: bytes) -> str:
    """Sign the fixed due-batch poll with the scheduler's separate run key."""
    return _sign_path(secret, DUE_PATH, timestamp, raw_body)


def _sign_path(secret: bytes, path: str, timestamp: str, raw_body: bytes) -> str:
    message = b"POST\n" + path.encode() + b"\n" + timestamp.encode() + b"\n" + raw_body
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def sign_results_request(secret: bytes, timestamp: str, raw_body: bytes) -> str:
    """Sign a requester-scoped recent-results query with the HADES-only key."""
    return _sign_path(secret, RESULTS_PATH, timestamp, raw_body)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise Phase3RequestError("duplicate JSON key")
        value[key] = item
    return value


def parse_run_request(raw_body: bytes) -> tuple[str, str]:
    if not raw_body or len(raw_body) > MAX_BODY_BYTES:
        raise Phase3RequestError("request body is empty or too large")
    try:
        value = json.loads(raw_body, object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3RequestError("request body is not valid JSON") from exc
    if not isinstance(value, Mapping) or set(value) != {"automation_id", "execution_key"}:
        raise Phase3RequestError("request fields are not the fixed runner contract")
    automation_id = value.get("automation_id")
    execution_key = value.get("execution_key")
    if not isinstance(automation_id, str) or not re.fullmatch(r"p3-[A-Za-z0-9_-]{8,40}", automation_id):
        raise Phase3RequestError("automation identity is invalid")
    if not isinstance(execution_key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", execution_key):
        raise Phase3RequestError("execution identity is invalid")
    return automation_id, execution_key


def parse_results_request(raw_body: bytes) -> str:
    if not raw_body or len(raw_body) > MAX_BODY_BYTES:
        raise Phase3RequestError("request body is empty or too large")
    try:
        value = json.loads(raw_body, object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3RequestError("request body is not valid JSON") from exc
    if not isinstance(value, Mapping) or set(value) != {"requester_subject_id"}:
        raise Phase3RequestError("request fields are not the fixed results contract")
    requester = value.get("requester_subject_id")
    if not isinstance(requester, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", requester):
        raise Phase3RequestError("requester identity is invalid")
    return requester


def parse_due_request(raw_body: bytes) -> str | None:
    if not raw_body or len(raw_body) > MAX_BODY_BYTES:
        raise Phase3RequestError("request body is empty or too large")
    try:
        value = json.loads(raw_body, object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3RequestError("request body is not valid JSON") from exc
    if not isinstance(value, Mapping) or set(value) not in (set(), {"template_type"}):
        raise Phase3RequestError("request fields are not the fixed due contract")
    template = value.get("template_type")
    if template is not None and (not isinstance(template, str) or template not in {
        "server-health-watch", "low-inventory-summary", "weekly-household-summary",
        "hades-backup-verification",
    }):
        raise Phase3RequestError("schedule template is outside the fixed catalog")
    return template


def verify_signed_due_request(
    *, secret: bytes, timestamp: str, signature: str, raw_body: bytes,
    now: int | None = None,
) -> str | None:
    """Verify a bounded due poll before opening scheduler state."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise Phase3RequestError("runner signing key is unavailable")
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp):
        raise Phase3RequestError("request timestamp is invalid")
    current = int(time.time()) if now is None else int(now)
    if abs(current - int(timestamp)) > MAX_CLOCK_SKEW_SECONDS:
        raise Phase3RequestError("request timestamp is outside the accepted window")
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise Phase3RequestError("request signature is invalid")
    if not hmac.compare_digest(sign_due_request(secret, timestamp, raw_body), signature):
        raise Phase3RequestError("request signature is invalid")
    return parse_due_request(raw_body)


def verify_signed_request(
    *, secret: bytes, timestamp: str, signature: str, raw_body: bytes,
    now: int | None = None,
) -> tuple[str, str]:
    """Authenticate and validate a request before opening runner state."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise Phase3RequestError("runner signing key is unavailable")
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp):
        raise Phase3RequestError("request timestamp is invalid")
    current = int(time.time()) if now is None else int(now)
    if abs(current - int(timestamp)) > MAX_CLOCK_SKEW_SECONDS:
        raise Phase3RequestError("request timestamp is outside the accepted window")
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise Phase3RequestError("request signature is invalid")
    expected = sign_request(secret, timestamp, raw_body)
    if not hmac.compare_digest(expected, signature):
        raise Phase3RequestError("request signature is invalid")
    return parse_run_request(raw_body)


def verify_signed_results_request(
    *, secret: bytes, timestamp: str, signature: str, raw_body: bytes,
    now: int | None = None,
) -> tuple[str, str]:
    """Verify an internal result read before resolving an identity or opening state."""
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise Phase3RequestError("result-query signing key is unavailable")
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{10}", timestamp):
        raise Phase3RequestError("request timestamp is invalid")
    current = int(time.time()) if now is None else int(now)
    if abs(current - int(timestamp)) > MAX_CLOCK_SKEW_SECONDS:
        raise Phase3RequestError("request timestamp is outside the accepted window")
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise Phase3RequestError("request signature is invalid")
    expected = sign_results_request(secret, timestamp, raw_body)
    if not hmac.compare_digest(expected, signature):
        raise Phase3RequestError("request signature is invalid")
    return parse_results_request(raw_body)


def execute_signed_run(
    *,
    secret: bytes,
    timestamp: str,
    signature: str,
    raw_body: bytes,
    runner: Phase3Runner,
    now: int | None = None,
) -> dict[str, Any]:
    """Authenticate one run request and delegate to the authority-checking runner.

    Duplicate signed requests are safe because ``execution_key`` is the
    durable idempotency key in ``Phase3Store``. The timestamp bounds captured
    request replay; a valid retry of a completed request returns its stored
    outcome and does not repeat the fixed source read.
    """
    automation_id, execution_key = verify_signed_request(
        secret=secret, timestamp=timestamp, signature=signature, raw_body=raw_body, now=now,
    )
    return runner.run(automation_id, execution_key)


def execute_signed_results_request(
    *, secret: bytes, timestamp: str, signature: str, raw_body: bytes,
    runner: Phase3Runner, now: int | None = None,
) -> dict[str, Any]:
    """Return only recent results visible under current requester and owner grants."""
    requester_subject = verify_signed_results_request(
        secret=secret, timestamp=timestamp, signature=signature, raw_body=raw_body, now=now,
    )
    return {"results": runner.recent_results_for(requester_subject)}


def execute_signed_due_request(
    *, secret: bytes, timestamp: str, signature: str, raw_body: bytes,
    runner: Phase3Runner, now: int | None = None,
) -> dict[str, Any]:
    template_type = verify_signed_due_request(
        secret=secret, timestamp=timestamp, signature=signature, raw_body=raw_body, now=now,
    )
    return {"due": runner.store.due_schedule_items(template_type=template_type, now=now)}


def make_phase3_http_handler(
    secret_provider: Callable[[], bytes],
    runner_provider: Callable[[], Phase3Runner],
    result_secret_provider: Callable[[], bytes] | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Build fixed run and optional HADES-only recent-results routes."""

    class Phase3Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {RUN_PATH, DUE_PATH, RESULTS_PATH}:
                self._respond(404, {"error": "not found"})
                return
            if self.path == RESULTS_PATH and result_secret_provider is None:
                self._respond(404, {"error": "not found"})
                return
            raw_length = self.headers.get("Content-Length", "")
            if not raw_length.isdigit() or int(raw_length) < 1:
                self._respond(400, {"error": "invalid request"})
                return
            length = int(raw_length)
            if length > MAX_BODY_BYTES:
                self._respond(413, {"error": "request too large"})
                return
            raw_body = self.rfile.read(length)
            if len(raw_body) != length:
                self._respond(400, {"error": "invalid request"})
                return
            try:
                timestamp = self.headers.get("X-HADES-Timestamp", "")
                signature = self.headers.get("X-HADES-Signature", "")
                if self.path == DUE_PATH:
                    template_type = verify_signed_due_request(
                        secret=secret_provider(), timestamp=timestamp,
                        signature=signature, raw_body=raw_body,
                    )
                    result = {"due": runner_provider().store.due_schedule_items(template_type=template_type)}
                elif self.path == RUN_PATH:
                    automation_id, execution_key = verify_signed_request(
                        secret=secret_provider(), timestamp=timestamp,
                        signature=signature, raw_body=raw_body,
                    )
                    result = runner_provider().run(automation_id, execution_key)
                else:
                    assert result_secret_provider is not None
                    requester_subject = verify_signed_results_request(
                        secret=result_secret_provider(), timestamp=timestamp,
                        signature=signature, raw_body=raw_body,
                    )
                    result = runner_provider().recent_results_for(requester_subject)
                    result = {"results": result}
            except Phase3RequestError:
                self._respond(401, {"error": "request authentication or contract failed"})
            except Phase3AuthorizationError:
                self._respond(403, {"error": "current automation authority denied"})
            except Phase3Error:
                self._respond(404, {"error": "automation request unavailable"})
            except Exception:
                self._respond(503, {"error": "runner temporarily unavailable"})
            else:
                self._respond(200, result)

        def do_GET(self) -> None:  # noqa: N802
            self._respond(405, {"error": "method not allowed"})

        def _respond(self, status: int, payload: Mapping[str, Any]) -> None:
            body = json.dumps(dict(payload), separators=(",", ":"), sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            # Requests include private automation identifiers and outcomes.
            return

    return Phase3Handler
