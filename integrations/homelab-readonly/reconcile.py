"""Authority-aware reconciliation for read-only homelab sources."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _freshness(value: Any, *, now: datetime, max_age: timedelta) -> str:
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "UNKNOWN"
    return "FRESH" if now - observed <= max_age else "STALE"


def summarize(
    proxmox: dict[str, Any] | None,
    netbox: dict[str, Any] | None,
    kuma: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compose source results without allowing one authority to replace another."""
    now = now or datetime.now(timezone.utc)
    runtime_rows = (proxmox or {}).get("data", [])
    inventory_rows = (netbox or {}).get("results", [])
    availability_rows = (kuma or {}).get("monitors", [])
    runtime = {
        str(row.get("name")): row for row in runtime_rows
        if isinstance(row, dict) and row.get("name")
    }
    runtime.update({
        str(row.get("node")): row for row in runtime_rows
        if isinstance(row, dict) and row.get("type") == "node" and row.get("node")
    })
    inventory = {
        str(row.get("name")): row for row in inventory_rows
        if isinstance(row, dict) and row.get("name")
    }
    observed = {
        str(row.get("name")): row for row in availability_rows
        if isinstance(row, dict) and row.get("name")
    }
    names = sorted(set(runtime) | set(inventory) | set(observed))
    resources: list[dict[str, Any]] = []
    for name in names:
        current = runtime.get(name)
        planned = inventory.get(name)
        monitor = observed.get(name)
        conflicts: list[str] = []
        if current and planned and current.get("node") and planned.get("planned_node") and current["node"] != planned["planned_node"]:
            conflicts.append("NetBox intended node differs from Proxmox runtime node")
        resources.append({
            "name": name,
            "runtime": current,
            "inventory": planned,
            "availability": monitor,
            "availability_freshness": _freshness(
                monitor.get("last_updated") if monitor else None,
                now=now,
                max_age=timedelta(minutes=5),
            ) if monitor else "UNKNOWN",
            "conflicts": conflicts,
        })
    return {
        "status": "OK" if proxmox is not None and netbox is not None and kuma is not None else "PARTIAL",
        "authority": {
            "runtime": "Proxmox",
            "inventory": "NetBox",
            "availability": "Uptime Kuma",
        },
        "resources": resources,
        "retrieved_at": now.isoformat(),
    }
