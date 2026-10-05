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


def _bounded_ping_ms(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0 or value > 60000:
        return None
    # Avoid NaN/Infinity in serialized output.
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def _stable_source_key(source: str, row: dict[str, Any]) -> str:
    """Return a source-local identity for rows that cannot safely join by name."""
    source_identity = row.get("source_identity")
    if isinstance(source_identity, str) and source_identity:
        return source_identity
    if source == "proxmox":
        node = row.get("node")
        kind = row.get("type")
        vmid = row.get("vmid")
        if node and kind and vmid is not None:
            return f"proxmox:{node}:{kind}:{vmid}"
        if kind == "node" and node:
            return f"proxmox:node:{node}"
    source_id = row.get("id")
    if source_id is not None:
        return f"{source}:{source_id}"
    label = row.get("name") or (row.get("node") if row.get("type") == "node" else "unidentified")
    return f"{source}:name:{str(label).casefold()}"


def _has_stable_identity(source: str, row: dict[str, Any]) -> bool:
    if source == "proxmox":
        return bool(
            row.get("id") is not None
            or (row.get("node") and row.get("type") and row.get("vmid") is not None)
            or (row.get("type") == "node" and row.get("node"))
        )
    if source == "netbox":
        return row.get("id") is not None
    return row.get("id") is not None or bool(row.get("source_identity"))


def summarize(
    proxmox: dict[str, Any] | None,
    netbox: dict[str, Any] | None,
    kuma: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    identity_links: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Compose source results without allowing one authority to replace another."""
    now = now or datetime.now(timezone.utc)
    runtime_rows = (proxmox or {}).get("data", [])
    inventory_rows = (netbox or {}).get("results", [])
    availability_rows = (kuma or {}).get("monitors", [])
    # Display names are labels, not identities. Keep the simple legacy join
    # only when a label is unique within each source. A duplicate in any one
    # source switches all rows with that label to source-local stable keys, so
    # response order can never choose which VM or monitor survives.
    source_rows = {
        "proxmox": [row for row in runtime_rows if isinstance(row, dict)],
        "netbox": [row for row in inventory_rows if isinstance(row, dict)],
        "kuma": [row for row in availability_rows if isinstance(row, dict)],
    }
    identity_links = identity_links or {}
    netbox_ids = {
        int(row["id"])
        for row in source_rows["netbox"]
        if isinstance(row.get("id"), int) and not isinstance(row.get("id"), bool)
    }
    name_counts_by_source: dict[str, dict[str, int]] = {}
    for source, rows in source_rows.items():
        counts: dict[str, int] = {}
        for row in rows:
            label = row.get("name") or (row.get("node") if row.get("type") == "node" else None)
            if label:
                folded = str(label).casefold()
                counts[folded] = counts.get(folded, 0) + 1
        name_counts_by_source[source] = counts

    ambiguous_names = {
        name
        for counts in name_counts_by_source.values()
        for name, count in counts.items()
        if count > 1
    }
    sources_by_name: dict[str, set[str]] = {}
    stable_names: set[str] = set()
    for source, rows in source_rows.items():
        for row in rows:
            label = row.get("name") or (row.get("node") if row.get("type") == "node" else None)
            if label:
                folded = str(label).casefold()
                sources_by_name.setdefault(folded, set()).add(source)
                if _has_stable_identity(source, row):
                    stable_names.add(folded)
    unlinked_names = {
        name for name, sources in sources_by_name.items()
        if len(sources) > 1 and name in stable_names
    }

    indexed: dict[str, dict[str, dict[str, Any]]] = {
        "proxmox": {}, "netbox": {}, "kuma": {}
    }
    labels: dict[str, str] = {}
    ambiguous: set[str] = set()
    unlinked: set[str] = set()
    related_inventory_ids: dict[str, int] = {}
    missing_link_targets: set[str] = set()
    proxmox_linked_netbox_ids = {
        linked_id
        for row in source_rows["proxmox"]
        if isinstance(row.get("source_identity"), str)
        and (linked_id := identity_links.get(row["source_identity"])) is not None
        and isinstance(linked_id, int) and not isinstance(linked_id, bool)
    }
    for source, rows in source_rows.items():
        for row in rows:
            label_value = row.get("name") or (row.get("node") if row.get("type") == "node" else None)
            if not label_value:
                continue
            label = str(label_value)
            folded = label.casefold()
            source_identity = row.get("source_identity")
            linked_id = identity_links.get(source_identity) if isinstance(source_identity, str) else None
            if source == "proxmox" and linked_id is not None:
                key = f"netbox-device:{linked_id}"
                if linked_id not in netbox_ids:
                    missing_link_targets.add(key)
            elif source == "kuma" and linked_id is not None:
                # The proposed link identifies the monitored device, not
                # necessarily the monitored service. Keep the monitor as an
                # independent observation and expose only its parent link.
                key = _stable_source_key(source, row)
                related_inventory_ids[key] = linked_id
                if linked_id not in netbox_ids:
                    missing_link_targets.add(f"netbox-device:{linked_id}")
            elif source == "netbox" and isinstance(row.get("id"), int) and not isinstance(row.get("id"), bool):
                key = f"netbox-device:{row['id']}"
            else:
                stable = _has_stable_identity(source, row)
                if folded not in ambiguous_names and folded not in unlinked_names and not stable:
                    key = f"name:{folded}"
                else:
                    key = _stable_source_key(source, row)
                    if folded in ambiguous_names:
                        ambiguous.add(key)
                    if folded in unlinked_names:
                        unlinked.add(key)
            # A Proxmox-to-NetBox link identifies the same host on both sides.
            # Mark the NetBox row as linked too; otherwise its matching name
            # is incorrectly reported as an unresolved conflict. Kuma links
            # identify a monitor's parent host, not the monitor itself.
            has_explicit_link = (
                (source == "proxmox" and linked_id is not None)
                or (
                    source == "netbox"
                    and isinstance(row.get("id"), int)
                    and not isinstance(row.get("id"), bool)
                    and row["id"] in proxmox_linked_netbox_ids
                )
            )
            if folded in ambiguous_names or (folded in unlinked_names and not has_explicit_link):
                if folded in unlinked_names and not has_explicit_link:
                    unlinked.add(key)
                if source == "proxmox" and row.get("node") and row.get("type"):
                    suffix = row.get("vmid") if row.get("vmid") is not None else row.get("id")
                    label = f"{label} ({row['node']} {row['type']} {suffix})"
                elif source == "netbox" and row.get("id") is not None:
                    label = f"{label} (NetBox {row['id']})"
                elif source == "netbox":
                    label = f"{label} (unlinked NetBox record)"
                elif source == "kuma" and row.get("id") is not None:
                    label = f"{label} (Kuma monitor {row['id']})"
                elif source == "kuma":
                    label = f"{label} (unlinked Kuma monitor)"
            # A duplicated source ID is itself malformed. Preserve the first
            # row deterministically and surface the collision below.
            if key in indexed[source]:
                ambiguous.add(key)
                duplicate_key = _stable_source_key(source, row)
                if duplicate_key in indexed[source]:
                    duplicate_key = f"{duplicate_key}:duplicate:{len(indexed[source]) + 1}"
                key = duplicate_key
            indexed[source][key] = row
            labels[key] = label

    runtime, inventory, observed = (
        indexed["proxmox"], indexed["netbox"], indexed["kuma"]
    )
    keys = sorted(set(runtime) | set(inventory) | set(observed))
    resources: list[dict[str, Any]] = []
    for key in keys:
        current = runtime.get(key)
        planned = inventory.get(key)
        monitor = observed.get(key)
        name = labels[key]
        source_identities: dict[str, list[str]] = {}
        proxmox_identity = current.get("source_identity") if current else None
        netbox_id = planned.get("id") if planned else None
        kuma_identity = monitor.get("source_identity") if monitor else None
        if isinstance(proxmox_identity, str) and proxmox_identity:
            source_identities["proxmox"] = [proxmox_identity]
        if isinstance(netbox_id, int) and not isinstance(netbox_id, bool) and netbox_id > 0:
            source_identities["netbox"] = [f"netbox:device:{netbox_id}"]
        if isinstance(kuma_identity, str) and kuma_identity:
            source_identities["kuma"] = [kuma_identity]
        related_device_id = related_inventory_ids.get(key)
        canonical_id = (
            f"netbox:device:{netbox_id}"
            if key.startswith("netbox-device:")
            and isinstance(netbox_id, int) and not isinstance(netbox_id, bool) and netbox_id > 0
            else None
        )
        identity = {
            "canonical_id": canonical_id,
            "source_identities": source_identities,
            "link_status": (
                "STABLE" if canonical_id else
                "LINK_TARGET_MISSING" if key in missing_link_targets else
                "RELATED_PARENT" if related_device_id is not None else
                "NAME_MATCH_ONLY" if sum(
                    value is not None for value in (current, planned, monitor)
                ) > 1 else
                "SOURCE_LOCAL"
            ),
        }
        conflicts: list[str] = (
            ["Display label is shared by multiple records; they remain separate by stable source identity"]
            if key in ambiguous else []
        )
        if key in unlinked:
            conflicts.append("Another source has the same display name, but no stable identity link confirms it is the same resource")
        if key in missing_link_targets:
            conflicts.append("Configured stable identity link points to a NetBox device not returned by the current inventory read")
        if related_device_id is not None and related_device_id not in netbox_ids:
            conflicts.append("Configured monitor parent link points to a NetBox device not returned by the current inventory read")
        if current and planned and current.get("node") and planned.get("planned_node") and current["node"] != planned["planned_node"]:
            conflicts.append("NetBox intended node differs from Proxmox runtime node")
        resources.append({
            "name": name,
            "identity": identity,
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
                ("id", "name", "planned_node", "role", "status", "primary_ip", "site"),
            ),
            "availability": _compact(
                monitor,
                ("name", "status", "last_updated", "monitor_type"),
            ),
            "probe_ping_ms": _bounded_ping_ms(monitor.get("ping_ms")) if monitor else None,
            "availability_freshness": _freshness(
                monitor.get("last_updated") if monitor else None,
                now=now,
                max_age=timedelta(minutes=5),
            ) if monitor else "UNKNOWN",
            "related_inventory_device_id": related_device_id,
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
            **(
                {"observed_at": (resource["availability"] or {}).get("last_updated")}
                if (resource["availability"] or {}).get("last_updated")
                else {}
            ),
            **({"ping_ms": resource["probe_ping_ms"]} if resource["probe_ping_ms"] is not None else {}),
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
        "status": "OK" if (
            proxmox is not None and netbox is not None and kuma is not None
            and not any(
                isinstance(source, dict) and source.get("errors")
                for source in (proxmox, netbox, kuma)
            )
        ) else "PARTIAL",
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
            # Count Proxmox/Kuma source-local records lacking a verified
            # cross-source identity. A NetBox device's own stable ID does not
            # make it an unlinked runtime/monitor record.
            "identity_unlinked_resources": sum(
                1 for key in unlinked if key in runtime or key in observed
            ),
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
