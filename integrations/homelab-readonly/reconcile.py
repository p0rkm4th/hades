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
    if observed > now:
        # A future observation is not evidence of current availability; it
        # usually indicates clock skew or malformed upstream data.
        return "UNKNOWN"
    return "FRESH" if now - observed <= max_age else "STALE"


def _compact(row: dict[str, Any] | None, fields: tuple[str, ...]) -> dict[str, Any] | None:
    """Keep the composed answer bounded and expose only decision fields.

    Upstream API rows can contain large plugin/config blobs. Returning those
    verbatim made the owner tool answer needlessly large and encouraged weak
    models to summarize or invent details instead of following the authority
    fields below.
    """
    if not isinstance(row, dict):
        return None
    return {key: row[key] for key in fields if key in row}


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
            "runtime": _compact(
                current,
                ("name", "node", "type", "vmid", "status", "cpu", "maxcpu", "mem", "maxmem", "disk", "maxdisk", "uptime"),
            ),
            # Inventory presence is not liveness. Keep an explicit field so a
            # consumer cannot interpret a NetBox-only record as online when
            # Proxmox has not observed it.
            "runtime_status": current.get("status") if current else "NOT_OBSERVED",
            "currently_online": bool(
                current and current.get("status") in {"online", "running"}
            ),
            "inventory": _compact(
                planned,
                ("name", "planned_node", "role", "status", "primary_ip", "site"),
            ),
            "availability": _compact(
                monitor,
                ("name", "status", "last_updated", "monitor_type"),
            ),
            "availability_freshness": _freshness(
                monitor.get("last_updated") if monitor else None,
                now=now,
                max_age=timedelta(minutes=5),
            ) if monitor else "UNKNOWN",
            "conflicts": conflicts,
        })
    online_names = [
        resource["name"] for resource in resources
        if resource["currently_online"]
    ]
    inventory_only_names = [
        resource["name"] for resource in resources
        if resource["runtime_status"] == "NOT_OBSERVED"
        and resource["inventory"] is not None
    ]
    availability_summary = [
        {
            "name": resource["name"],
            "status": (resource["availability"] or {}).get("status"),
            "freshness": resource["availability_freshness"],
        }
        for resource in resources
        if resource["availability"] is not None
    ]
    conflicts = [
        {"name": resource["name"], "reasons": resource["conflicts"]}
        for resource in resources
        if resource["conflicts"]
    ]
    return {
        "status": "OK" if proxmox is not None and netbox is not None and kuma is not None else "PARTIAL",
        "authority": {
            "runtime": "Proxmox",
            "inventory": "NetBox",
            "availability": "Uptime Kuma",
        },
        "online_names": online_names,
        "inventory_only_names": inventory_only_names,
        "source_counts": {
            "proxmox_runtime_rows": len(runtime_rows),
            "netbox_inventory_rows": len(inventory_rows),
            "kuma_monitor_rows": len(availability_rows),
            "composed_resources": len(resources),
        },
        "availability_summary": availability_summary,
        "conflicts": conflicts,
        "answer_contract": {
            "currently_online_source": "Proxmox runtime only",
            "inventory_only_source": "NetBox records not observed in Proxmox",
            "availability_source": "Uptime Kuma monitor status and freshness",
            "memory_is_not_authority": True,
            "writes_performed": False,
        },
        "liveness_rule": "Only resources with runtime_status=online (hosts) or running (guests) are currently live; inventory_only_names are not observed by Proxmox.",
        "resources": resources,
        "retrieved_at": now.isoformat(),
    }
