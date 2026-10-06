"""Read-only NetBox device/service change-time provider."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from source_utils import bounded_text, retrieved_at, source_error_code


def read_recent_inventory_updates(
    since: int,
    *,
    device_spec: tuple[str, str],
    service_spec: tuple[str, str],
    fetch: Callable[..., dict],
) -> dict:
    """Fetch bounded NetBox timestamps and preserve endpoint-level coverage.

    Endpoint configuration and the bounded HTTP transport are explicit inputs;
    this provider owns NetBox URL/query validation, row normalization, and
    partial/unavailable semantics. It performs GETs only and never returns
    arbitrary change payloads.
    """
    configured = [
        ("device", device_spec[0], device_spec[1]),
        ("service", service_spec[0], service_spec[1]),
    ]
    configured = [(kind, endpoint, token) for kind, endpoint, token in configured if endpoint]
    if not configured:
        return {
            "status": "NOT_CONFIGURED", "retrieved_at": None,
            "coverage": [], "objects": [], "truncated": False,
            "error_codes": [], "read_only": True,
        }

    since_text = datetime.fromtimestamp(since, timezone.utc).isoformat()
    objects = []
    endpoints = []
    for kind, endpoint, token_file in configured:
        started = time.monotonic()
        try:
            parsed = urlsplit(endpoint)
            if (
                parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
            ):
                raise ValueError("invalid NetBox inventory endpoint")
            query = urlencode({"limit": 100, "last_updated__gte": since_text})
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
            payload = fetch(url, token_file, timeout_seconds=8)
            rows = payload.get("results")
            count = payload.get("count")
            if not isinstance(rows, list) or type(count) is not int or count < 0:
                raise ValueError("NetBox inventory update response has an unsupported shape")
            invalid_rows = False
            for row in rows[:100]:
                if not isinstance(row, dict):
                    invalid_rows = True
                    continue
                raw_id = row.get("id")
                raw_name = row.get("name")
                raw_updated = row.get("last_updated")
                if (
                    isinstance(raw_id, bool)
                    or not isinstance(raw_id, (str, int))
                    or not re.fullmatch(r"[1-9][0-9]{0,19}", str(raw_id))
                    or not isinstance(raw_name, str)
                    or not isinstance(raw_updated, str)
                ):
                    invalid_rows = True
                    continue
                try:
                    updated = datetime.fromisoformat(raw_updated.replace("Z", "+00:00"))
                    if updated.tzinfo is None:
                        raise ValueError("NetBox update timestamp is not timezone-aware")
                    updated = updated.astimezone(timezone.utc)
                except (ValueError, OverflowError):
                    invalid_rows = True
                    continue
                if int(updated.timestamp()) < since:
                    continue
                name = bounded_text(raw_name, 100)
                if not name:
                    invalid_rows = True
                    continue
                objects.append({
                    "object_type": kind,
                    "object_id": str(raw_id),
                    "name": name,
                    "last_updated": updated.isoformat(),
                })
            truncated = count > len(rows) or len(rows) > 100
            status = "PARTIAL" if truncated or invalid_rows else "HEALTHY"
            endpoints.append({
                "object_type": kind, "status": status,
                "retrieved_at": retrieved_at(),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "returned": min(len(rows), 100), "total": count,
                "truncated": truncated,
                "error_codes": [],
            })
        except (OSError, ValueError, UnicodeError, OverflowError) as exc:
            endpoints.append({
                "object_type": kind, "status": "UNAVAILABLE",
                "retrieved_at": retrieved_at(),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "returned": 0, "total": None, "truncated": False,
                "error_codes": [source_error_code(exc)],
            })

    states = [row["status"] for row in endpoints]
    status = "READABLE" if all(state == "HEALTHY" for state in states) else (
        "SOURCE_UNAVAILABLE" if all(state == "UNAVAILABLE" for state in states)
        else "PARTIAL"
    )
    objects.sort(key=lambda row: row["last_updated"], reverse=True)
    truncated = any(row["truncated"] for row in endpoints) or len(objects) > 200
    return {
        "status": status,
        "retrieved_at": retrieved_at(),
        "coverage": [row["object_type"] for row in endpoints],
        "endpoints": endpoints,
        "objects": objects[:200],
        "truncated": truncated,
        "error_codes": sorted({
            code for row in endpoints for code in row.get("error_codes", [])
        }),
        "read_only": True,
    }
