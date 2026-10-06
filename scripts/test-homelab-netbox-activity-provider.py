#!/usr/bin/env python3
"""Synthetic contract for the read-only NetBox activity provider."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations" / "homelab-readonly"))

from netbox_activity import read_recent_inventory_updates


now = int(datetime.now(timezone.utc).timestamp())
calls: list[tuple[str, str, dict]] = []


def fetch(url: str, token_file: str = "", **kwargs: object) -> dict:
    calls.append((url, token_file, kwargs))
    path = urlsplit(url).path
    if path.endswith("/devices/"):
        return {"count": 1, "results": [{
            "id": 17, "name": "node\nalpha", "last_updated": datetime.fromtimestamp(
                now, timezone.utc,
            ).isoformat(),
            "secret": "provider payload fields are intentionally discarded",
        }]}
    if path.endswith("/services/"):
        return {"count": 2, "results": [{
            "id": 29, "name": "service-alpha", "last_updated": datetime.fromtimestamp(
                now, timezone.utc,
            ).isoformat(),
        }]}
    raise AssertionError("provider requested an unexpected path")


healthy = read_recent_inventory_updates(
    now - 1,
    device_spec=("https://netbox.example.test/api/dcim/devices/", "/protected/device-token"),
    service_spec=("https://netbox.example.test/api/ipam/services/", "/protected/service-token"),
    fetch=fetch,
)
assert healthy["status"] == "PARTIAL", healthy  # service count exceeds this page
assert healthy["coverage"] == ["device", "service"]
assert healthy["read_only"] is True
assert len(healthy["objects"]) == 2
assert {row["object_type"] for row in healthy["objects"]} == {"device", "service"}
assert next(row for row in healthy["objects"] if row["object_type"] == "device")["name"] == "node alpha"
assert "secret" not in repr(healthy)
assert len(calls) == 2
for url, token_file, kwargs in calls:
    query = parse_qs(urlsplit(url).query)
    assert query["limit"] == ["100"]
    assert query["last_updated__gte"]
    assert token_file.startswith("/protected/")
    assert kwargs == {"timeout_seconds": 8}


old_only = read_recent_inventory_updates(
    now,
    device_spec=("https://netbox.example.test/api/dcim/devices/", ""),
    service_spec=("", ""),
    fetch=lambda *_args, **_kwargs: {"count": 1, "results": [{
        "id": 18, "name": "old", "last_updated": "2020-01-01T00:00:00+00:00",
    }]},
)
assert old_only["status"] == "READABLE", old_only
assert old_only["objects"] == []


malformed = read_recent_inventory_updates(
    now - 1,
    device_spec=("https://netbox.example.test/api/dcim/devices/", ""),
    service_spec=("", ""),
    fetch=lambda *_args, **_kwargs: {"count": 1, "results": [{
        "id": True, "name": "invalid", "last_updated": "not-a-time",
    }]},
)
assert malformed["status"] == "PARTIAL", malformed
assert malformed["endpoints"][0]["status"] == "PARTIAL"
assert malformed["objects"] == []


outage = read_recent_inventory_updates(
    now - 1,
    device_spec=("https://netbox.example.test/api/dcim/devices/", ""),
    service_spec=("https://netbox.example.test/api/ipam/services/", ""),
    fetch=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("secret URL and token")),
)
assert outage["status"] == "SOURCE_UNAVAILABLE", outage
assert outage["error_codes"] == ["SOURCE_IO_ERROR"]
assert "secret URL" not in repr(outage)


def one_endpoint_outage(url: str, *_args: object, **_kwargs: object) -> dict:
    if urlsplit(url).path.endswith("/services/"):
        raise OSError("service endpoint credential must not escape")
    return {"count": 1, "results": [{
        "id": 19, "name": "surviving-device", "last_updated": datetime.fromtimestamp(
            now, timezone.utc,
        ).isoformat(),
    }]}


mixed = read_recent_inventory_updates(
    now - 1,
    device_spec=("https://netbox.example.test/api/dcim/devices/", ""),
    service_spec=("https://netbox.example.test/api/ipam/services/", ""),
    fetch=one_endpoint_outage,
)
assert mixed["status"] == "PARTIAL", mixed
assert [row["status"] for row in mixed["endpoints"]] == ["HEALTHY", "UNAVAILABLE"]
assert [row["name"] for row in mixed["objects"]] == ["surviving-device"]
assert mixed["error_codes"] == ["SOURCE_IO_ERROR"]
assert "credential" not in repr(mixed)


contradictory_endpoint = read_recent_inventory_updates(
    now - 1,
    device_spec=("https://user:password@netbox.example.test/api/dcim/devices/", ""),
    service_spec=("", ""),
    fetch=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("invalid endpoint must not reach transport")
    ),
)
assert contradictory_endpoint["status"] == "SOURCE_UNAVAILABLE"
assert contradictory_endpoint["error_codes"] == ["INVALID_RESPONSE_OR_CONFIGURATION"]


not_configured = read_recent_inventory_updates(
    now,
    device_spec=("", ""),
    service_spec=("", ""),
    fetch=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("unconfigured sources must not call transport")
    ),
)
assert not_configured["status"] == "NOT_CONFIGURED"
assert not_configured["objects"] == []

print("PASS NetBox provider endpoint isolation, bounds, partials, and redacted failures")
