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
        return "UNKNOWN"
    return "FRESH" if now - observed <= max_age else "STALE"


def _compact(row: dict[str, Any] | None, fields: tuple[str, ...]) -> dict[str, Any] | None:
    """Keep upstream rows bounded and omit unrelated API/configuration fields."""
    if not isinstance(row, dict):
        return None
    return {key: row[key] for key in fields if key in row}


def _bounded_ping_ms(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value > 60000 or value != value:
        return None
    if value in (float("inf"), float("-inf")):
        return None
    return value


def _identity(source: str, row: dict[str, Any], index: int) -> str:
    provided = row.get("_hades_identity")
    if isinstance(provided, str) and provided:
        return provided
    object_id = row.get("id")
    if source == "netbox" and object_id is not None:
        return f"netbox:device:{object_id}"
    if source == "kuma" and object_id is not None:
        return f"kuma:monitor:{object_id}"
    # Source-local sequence identities deliberately never join to another
    # source. Callers that need a cross-source join must provide a stable ID.
    return f"{source}:unidentified:{index}"


def _display_name(source: str, row: dict[str, Any]) -> str:
    value = row.get("name")
    if not value and source == "proxmox":
        value = row.get("node")
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())[:160]
    return f"Unnamed {source} record"


def summarize(
    proxmox: dict[str, Any] | None,
    netbox: dict[str, Any] | None,
    kuma: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    identity_links: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compose observations, joining authorities only through stable IDs.

    NetBox device IDs are the canonical identity for linked hosts. Proxmox and
    Kuma records remain source-local unless a protected, explicit link maps
    their stable source identity to a NetBox device ID. Display names never
    cause records from different systems to merge.
    """
    now = now or datetime.now(timezone.utc)
    links = identity_links or {}
    runtime_rows = (proxmox or {}).get("data", [])
    inventory_rows = (netbox or {}).get("results", [])
    availability_rows = (kuma or {}).get("monitors", [])
    groups: dict[str, dict[str, Any]] = {}
    source_counts = {"proxmox": 0, "netbox": 0, "kuma": 0}

    def add_rows(source: str, rows: Any) -> None:
        if not isinstance(rows, list):
            return
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            source_counts[source] += 1
            source_identity = _identity(source, row, index)
            canonical_identity = (
                source_identity
                if source == "netbox" and source_identity.startswith("netbox:device:")
                else links.get(source_identity)
            )
            group_key = canonical_identity or f"source-local:{source_identity}"
            group = groups.setdefault(group_key, {
                "canonical_identity": canonical_identity,
                "source_records": {"proxmox": [], "netbox": [], "kuma": []},
                "source_identities": {"proxmox": [], "netbox": [], "kuma": []},
                "names": {"proxmox": [], "netbox": [], "kuma": []},
                "conflicts": [],
            })
            group["source_records"][source].append(row)
            if source_identity not in group["source_identities"][source]:
                group["source_identities"][source].append(source_identity)
            name = _display_name(source, row)
            if name not in group["names"][source]:
                group["names"][source].append(name)

    add_rows("proxmox", runtime_rows)
    add_rows("netbox", inventory_rows)
    add_rows("kuma", availability_rows)

    resources: list[dict[str, Any]] = []
    availability_summary: list[dict[str, Any]] = []
    for group_key, group in groups.items():
        runtime_records = group["source_records"]["proxmox"]
        inventory_records = group["source_records"]["netbox"]
        monitor_records = group["source_records"]["kuma"]
        conflicts: list[str] = []
        runtime_row = runtime_records[0] if len(runtime_records) == 1 else None
        inventory_row = inventory_records[0] if len(inventory_records) == 1 else None
        monitor_row = monitor_records[0] if len(monitor_records) == 1 else None
        for label, records in (
            ("Proxmox", runtime_records),
            ("NetBox", inventory_records),
            ("Uptime Kuma", monitor_records),
        ):
            if len(records) > 1:
                conflicts.append(f"Multiple {label} records map to one canonical identity")
        if group["canonical_identity"] and not inventory_row:
            conflicts.append("Linked NetBox device ID is absent from the current inventory response")
        if (
            runtime_row
            and inventory_row
            and runtime_row.get("type") in {"qemu", "lxc"}
            and runtime_row.get("node")
            and inventory_row.get("planned_node")
            and runtime_row["node"] != inventory_row["planned_node"]
        ):
            conflicts.append("NetBox intended node differs from Proxmox runtime node")

        runtime_state = (
            runtime_row.get("status") if runtime_row
            else "CONTRADICTORY" if len(runtime_records) > 1
            else "NOT_OBSERVED"
        )
        if runtime_row and runtime_state in {"online", "running"}:
            currently_online: bool | None = True
        elif runtime_row and runtime_state in {"offline", "stopped"}:
            currently_online = False
        else:
            currently_online = None

        name = (
            (inventory_row or {}).get("name")
            or (runtime_row or {}).get("name")
            or (runtime_row or {}).get("node")
            or (monitor_row or {}).get("name")
            or next((values[0] for values in group["names"].values() if values), "Unnamed resource")
        )
        identity_status = (
            "CONTRADICTORY" if conflicts and group["canonical_identity"] and not inventory_row
            else "LINKED" if group["canonical_identity"] and len(
                [source for source, records in group["source_records"].items() if records]
            ) > 1
            else "CANONICAL" if group["canonical_identity"]
            else "UNLINKED"
        )
        availability = _compact(
            monitor_row, ("id", "name", "status", "last_updated", "monitor_type"),
        )
        monitor_observations = []
        for monitor_index, candidate in enumerate(monitor_records):
            observed_at = candidate.get("last_updated")
            freshness = _freshness(
                observed_at, now=now, max_age=timedelta(minutes=5),
            )
            row = _compact(
                candidate, ("id", "name", "status", "last_updated", "monitor_type"),
            ) or {}
            row["freshness"] = freshness
            row["source_identity"] = _identity("kuma", candidate, monitor_index)
            monitor_observations.append(row)
            availability_summary.append({
                "name": row.get("name") or name,
                "status": row.get("status"),
                "freshness": freshness,
                "source_identity": row["source_identity"],
                **({"ping_ms": _bounded_ping_ms(candidate.get("ping_ms"))}
                   if _bounded_ping_ms(candidate.get("ping_ms")) is not None else {}),
            })
        monitor_freshness = (
            monitor_observations[0]["freshness"] if len(monitor_observations) == 1
            else "UNKNOWN"
        )
        resource = {
            "name": name,
            "identity": {
                "status": identity_status,
                "canonical_id": group["canonical_identity"],
                "source_identities": group["source_identities"],
            },
            "runtime": _compact(
                runtime_row,
                ("name", "node", "type", "vmid", "status", "cpu", "maxcpu", "mem", "maxmem", "disk", "maxdisk", "uptime"),
            ),
            "runtime_status": runtime_state,
            "currently_online": currently_online,
            "inventory": _compact(
                inventory_row,
                ("id", "name", "planned_node", "role", "status", "primary_ip", "site"),
            ),
            "availability": availability if len(monitor_records) == 1 else None,
            "availability_observations": monitor_observations,
            "probe_ping_ms": (
                _bounded_ping_ms(monitor_row.get("ping_ms"))
                if monitor_row and len(monitor_records) == 1 else None
            ),
            "availability_freshness": monitor_freshness,
            "conflicts": conflicts,
        }
        resources.append(resource)

    # Same display names from separate authorities are useful clues for an
    # operator but are not identity evidence. Surface them explicitly.
    names_to_sources: dict[str, list[tuple[str, str, str]]] = {}
    for group_key, group in groups.items():
        for source, names in group["names"].items():
            for name in names:
                names_to_sources.setdefault(name.casefold(), []).append(
                    (group_key, source, name)
                )
    identity_warnings = []
    for claims in names_to_sources.values():
        group_ids = {claim[0] for claim in claims}
        if len(group_ids) < 2:
            continue
        display_names = sorted({claim[2] for claim in claims})
        sources = sorted({claim[1] for claim in claims})
        identity_warnings.append({
            "type": "SAME_NAME_NOT_LINKED" if len(sources) > 1 else "DUPLICATE_NAME_WITHIN_SOURCE",
            "names": display_names,
            "sources": sources,
            "meaning": (
                "Display-name agreement is not a confirmed identity link."
                if len(sources) > 1 else
                "Multiple records in one source share a display name but have separate stable identities."
            ),
        })
    identity_unlinked_count = sum(
        1 for group in groups.values()
        if not group["canonical_identity"] and any(
            group["source_records"][source] for source in ("proxmox", "kuma")
        )
    )

    online_names = sorted({
        resource["name"] for resource in resources
        if resource["currently_online"] is True
    })
    inventory_only_names = sorted({
        resource["name"] for resource in resources
        if resource["inventory"] is not None and resource["runtime_status"] == "NOT_OBSERVED"
    })
    conflicts = [
        {"name": resource["name"], "reasons": resource["conflicts"]}
        for resource in resources if resource["conflicts"]
    ]
    observed_sources = sum(bool(source_counts[key]) for key in source_counts)
    status = "OK" if proxmox is not None and netbox is not None and kuma is not None else "PARTIAL"
    if observed_sources > 1 and (identity_unlinked_count or identity_warnings):
        status = "PARTIAL"
    if conflicts:
        status = "PARTIAL"
    return {
        "status": status,
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
            "identity_unlinked_resources": identity_unlinked_count,
        },
        "availability_summary": availability_summary,
        "identity_warnings": identity_warnings,
        "conflicts": conflicts,
        "answer_contract": {
            "currently_online_source": "Proxmox runtime only",
            "inventory_only_source": "NetBox record with no explicitly linked Proxmox runtime row",
            "availability_source": "Uptime Kuma monitor status and freshness",
            "cross_source_identity_source": "explicit source ID to NetBox device ID link only",
            "display_names_are_identity": False,
            "memory_is_not_authority": True,
            "writes_performed": False,
        },
        "liveness_rule": (
            "Only runtime_status=online (hosts) or running (guests) sets "
            "currently_online=true. Explicit offline/stopped states set false; "
            "missing or unrecognized runtime states leave currently_online=null. "
            "NetBox records without an explicitly linked Proxmox row are not "
            "evidence that the device is offline."
        ),
        "resources": sorted(resources, key=lambda item: (item["name"].casefold(), str(item["identity"]["canonical_id"] or ""))),
        "retrieved_at": now.isoformat(),
    }
