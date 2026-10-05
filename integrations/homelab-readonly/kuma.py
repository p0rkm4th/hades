"""Read-only normalization for Uptime Kuma's public status responses."""

from __future__ import annotations

import math
from typing import Any


def normalize_public_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert heartbeat status-page data into bounded monitor observations.

    Kuma remains an availability observation only. This function does not
    claim host reachability, service health, or application readiness.
    """
    if isinstance(payload.get("monitors"), list):
        return payload
    groups = payload.get("publicGroupList")
    heartbeats = payload.get("heartbeatList")
    if not isinstance(groups, list) or not isinstance(heartbeats, dict):
        raise ValueError("Uptime Kuma heartbeat response has an unsupported shape")
    monitors = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        monitor_rows = group.get("monitorList", [])
        if not isinstance(monitor_rows, list):
            raise ValueError("Uptime Kuma monitor list has an unsupported shape")
        for monitor in monitor_rows:
            if not isinstance(monitor, dict) or not monitor.get("name"):
                continue
            monitor_id = str(monitor.get("id", ""))
            history = heartbeats.get(monitor_id, [])
            latest = history[-1] if isinstance(history, list) and history else {}
            if not isinstance(latest, dict):
                latest = {}
            raw_status = latest.get("status")
            status = (
                "up" if type(raw_status) is int and raw_status == 1
                else "down" if type(raw_status) is int and raw_status == 0
                else "unknown"
            )
            row = {
                "name": monitor["name"],
                "status": status,
                "last_updated": latest.get("time"),
                "monitor_type": monitor.get("type"),
            }
            if monitor.get("id") is not None:
                row["id"] = str(monitor["id"])
                row["source_identity"] = f"kuma:monitor:{monitor['id']}"
            # This is a single monitor's bounded ping sample, not a network
            # measurement or historical baseline.
            ping = latest.get("ping")
            if isinstance(ping, (int, float)) and not isinstance(ping, bool):
                try:
                    finite = math.isfinite(ping)
                except (OverflowError, TypeError):
                    finite = False
                if finite and 0 <= ping <= 60000:
                    row["ping_ms"] = ping
            monitors.append(row)
    return {"monitors": monitors}
