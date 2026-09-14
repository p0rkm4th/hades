"""Validate the public-safe response contract for future read-only domains.

This is fixture-level evidence only. It does not contact Proxmox, NetBox,
Uptime Kuma, or Home Assistant and it does not define a shadow state store.
"""

from __future__ import annotations

from datetime import datetime
from copy import deepcopy


NOW = datetime.fromisoformat("2026-09-13T12:00:00+00:00")


def validate(result: dict) -> None:
    assert isinstance(result, dict)
    assert result.get("status") in {"succeeded", "partial", "failed"}
    assert isinstance(result.get("source"), str) and result["source"].strip()
    retrieved = datetime.fromisoformat(result["retrieved_at"].replace("Z", "+00:00"))
    assert retrieved <= NOW
    assert isinstance(result.get("freshness_seconds"), int)
    assert result["freshness_seconds"] >= 0
    assert isinstance(result.get("coverage"), list) and result["coverage"]
    assert result.get("read_only") is True
    if result["status"] == "partial":
        assert isinstance(result.get("failures"), list) and result["failures"]
    if result["status"] == "failed":
        assert isinstance(result.get("error"), str) and result["error"].strip()


PROXMOX = {
    "status": "succeeded",
    "source": "proxmox.synthetic",
    "retrieved_at": "2026-09-13T11:59:00Z",
    "freshness_seconds": 60,
    "coverage": ["nodes", "guests", "resource_usage"],
    "items": [{"node": "pve-synthetic", "status": "online"}],
    "read_only": True,
}

NETBOX = {
    "status": "succeeded",
    "source": "netbox.synthetic",
    "retrieved_at": "2026-09-13T11:58:00Z",
    "freshness_seconds": 120,
    "coverage": ["sites", "devices", "interfaces", "ip_prefixes"],
    "items": [{"device": "router-synthetic", "site": "lab"}],
    "read_only": True,
}

UPTIME_KUMA = {
    "status": "partial",
    "source": "uptime-kuma.synthetic-status-page",
    "retrieved_at": "2026-09-13T11:57:00Z",
    "freshness_seconds": 180,
    "coverage": ["approved-monitors"],
    "items": [{"monitor": "web-synthetic", "status": "up"}],
    "failures": [{"monitor": "db-synthetic", "reason": "source unavailable"}],
    "read_only": True,
}

HOME_ASSISTANT = {
    "status": "partial",
    "source": "home-assistant.synthetic",
    "retrieved_at": "2026-09-13T11:56:00Z",
    "freshness_seconds": 240,
    "coverage": ["sensor.indoor_temperature", "climate.living_room"],
    "items": [
        {"entity_id": "sensor.indoor_temperature", "state": "21.5"},
        {"entity_id": "climate.living_room", "state": "unavailable"},
    ],
    "failures": [{"entity_id": "climate.living_room", "reason": "unavailable"}],
    "read_only": True,
}


for fixture in (PROXMOX, NETBOX, UPTIME_KUMA, HOME_ASSISTANT):
    validate(fixture)

invalid = deepcopy(PROXMOX)
del invalid["source"]
try:
    validate(invalid)
except (AssertionError, KeyError):
    pass
else:
    raise AssertionError("missing source must fail closed")

invalid = deepcopy(HOME_ASSISTANT)
invalid["status"] = "failed"
invalid.pop("error", None)
try:
    validate(invalid)
except AssertionError:
    pass
else:
    raise AssertionError("failed result without an error must fail closed")

print("PASS synthetic read-only response contracts")
