"""Pure, source-independent views of normalized homelab observations."""

import math
import re

def _hades_homelab_availability_groups(availability):
    """Separate current Kuma probe outcomes from stale or unusable observations."""
    groups = {"up": [], "down": [], "unknown": []}
    for item in availability if isinstance(availability, list) else []:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("name") or "Unnamed check").split())[:100]
        status = str(item.get("status") or "unknown").casefold()
        freshness = str(item.get("freshness") or "UNKNOWN").upper()
        if freshness != "FRESH":
            groups["unknown"].append({"name": name, "last_status": status, "freshness": freshness})
        elif status in {"up", "online"}:
            groups["up"].append(name)
        elif status in {"down", "offline"}:
            groups["down"].append(name)
        else:
            groups["unknown"].append({"name": name, "last_status": status, "freshness": freshness})
    return groups

def _hades_homelab_health_summary_response(summary):
    """Summarize live coverage without treating power or probes as app health."""
    if not isinstance(summary, dict):
        return "I couldn't verify current homelab status because the live summary was unavailable."
    availability = summary.get("availability_summary", [])
    groups = _hades_homelab_availability_groups(availability)
    down = groups["down"]
    up = groups["up"]
    unknown = groups["unknown"]
    online = summary.get("online_names", [])
    online_count = len(online) if isinstance(online, list) else 0
    raw_conflicts = summary.get("conflicts", [])
    raw_conflicts = raw_conflicts if isinstance(raw_conflicts, list) else []
    conflicts = []
    label_collisions = []
    for row in raw_conflicts:
        if not isinstance(row, dict):
            continue
        reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
        only_label_collision = bool(reasons) and all(
            str(reason).casefold().startswith(("display label is shared", "display name is ambiguous"))
            for reason in reasons
        )
        if only_label_collision:
            label_collisions.append(row)
        else:
            conflicts.append(row)
    source_rows = summary.get("source_observations") or summary.get("sources") or []
    source_rows = source_rows if isinstance(source_rows, list) else []
    unavailable = [
        row for row in source_rows
        if isinstance(row, dict)
        and str(row.get("status") or "UNKNOWN").upper()
        not in {"AVAILABLE", "READABLE", "HEALTHY", "OK", "COMPLETE"}
    ]
    catalog = summary.get("service_catalog")
    catalog = catalog if isinstance(catalog, dict) else {}
    catalog_status = str(catalog.get("status") or "UNKNOWN").upper()
    catalog_coverage = str(catalog.get("coverage") or "UNKNOWN").upper()
    guest_visibility = summary.get("proxmox_guest_visibility")
    guest_visibility = guest_visibility if isinstance(guest_visibility, dict) else {}
    guest_visibility_status = str(guest_visibility.get("status") or "UNKNOWN").upper()
    guest_visibility_scope = str(guest_visibility.get("scope") or "UNKNOWN").upper()
    guest_scope_incomplete = guest_visibility_status not in {"COMPLETE", "NOT_CONFIGURED"}

    if down or conflicts:
        parts = ["Some configured homelab evidence needs attention."]
    elif unavailable or summary.get("status") != "OK" or guest_scope_incomplete:
        parts = ["I can't confirm that the whole homelab is okay; source coverage is partial or unavailable."]
    else:
        parts = ["No failure is reported by fresh configured availability checks."]

    if down:
        parts.append("Failing configured checks: " + ", ".join(down[:4]) + ".")
    elif conflicts or unavailable or guest_scope_incomplete:
        parts.append("No fresh configured probe is reporting a failure.")
    if up:
        parts.append(f"{len(up)} configured availability check(s) responded in this live read.")
    if unknown:
        parts.append(f"{len(unknown)} configured check(s) are stale or unknown.")
    if online_count:
        parts.append(
            f"Proxmox reports {online_count} guest(s) running; this is power/runtime state, not application health."
        )
    if conflicts:
        labels = [
            " ".join(str(row.get("name") or "Unnamed resource").split())[:80]
            for row in conflicts[:3] if isinstance(row, dict)
        ]
        if labels:
            parts.append("Sources disagree about " + ", ".join(labels) + ".")
    if label_collisions:
        parts.append("Some records share display labels but remain separate by stable source identity.")
    if guest_scope_incomplete:
        parts.append(
            f"Proxmox guest visibility is {guest_visibility_scope.casefold()}; unreported guest state remains unknown."
        )
    if unavailable:
        labels = [
            " ".join(str(row.get("source") or "A configured source").split())[:64]
            for row in unavailable[:3]
        ]
        parts.append("Could not verify " + ", ".join(labels) + " in this read.")
    if catalog_status != "OK" or catalog_coverage not in {"COMPLETE", "EMPTY"} or catalog_coverage == "EMPTY":
        parts.append("Application-service placement coverage is missing, empty, or incomplete.")
    if unknown or not availability or catalog_coverage != "COMPLETE" or guest_scope_incomplete:
        parts.append("Some unmonitored services remain unknown for application health.")
    parts.append("Backup contents and restoreability were not checked in this summary.")
    return " ".join(parts)

def _hades_homelab_service_coverage_response(summary):
    """Explain coverage gaps without treating a responding probe as app health."""
    if not isinstance(summary, dict):
        return "I couldn't read the current homelab service-check summary."
    parts = []
    catalog = summary.get("service_catalog") if isinstance(summary.get("service_catalog"), dict) else {}
    catalog_status = str(catalog.get("status") or "UNKNOWN").upper()
    catalog_coverage = str(catalog.get("coverage") or "UNKNOWN").upper()
    services = catalog.get("services") if isinstance(catalog.get("services"), list) else []
    if catalog_status == "OK" and catalog_coverage == "EMPTY" and services:
        parts.append("The service catalog metadata conflicts: it reports an empty catalog but includes records, so I can't confirm its coverage.")
    elif catalog_status == "OK" and catalog_coverage == "COMPLETE" and not services:
        parts.append("The service catalog reports complete coverage but returned no rows; that conflicts with its coverage state, so I can't confirm the catalog is empty.")
    elif catalog_status == "OK" and catalog_coverage == "EMPTY" and catalog.get("truncated") is not True:
        parts.append("The service catalog is reachable but empty, so expected application placement cannot be compared with current checks.")
    elif catalog_status == "OK" and (catalog_coverage == "PARTIAL" or catalog.get("truncated") is True):
        if services:
            service_word = "record" if len(services) == 1 else "records"
            parts.append(
                f"The service catalog returned {len(services)} service {service_word}, but the read is partial or truncated, "
                "so missing records cannot be treated as absent."
            )
        else:
            parts.append("The service catalog read is partial or truncated, so missing records cannot be treated as absent.")
    elif catalog_status == "OK" and catalog_coverage == "UNKNOWN":
        parts.append("The service catalog responded, but its total coverage is unknown, so I can't confirm that unlisted services are absent.")
    elif catalog_status in {"NOT_CONFIGURED", "UNAVAILABLE", "SOURCE_UNAVAILABLE", "ERROR"}:
        parts.append("The service catalog is not currently available, so expected application placement cannot be compared with current checks.")
    elif catalog_status == "OK" and catalog_coverage == "COMPLETE" and services:
        service_word = "service" if len(services) == 1 else "services"
        parts.append(f"The service catalog lists {len(services)} application {service_word}, but the catalog alone does not establish their current health.")
    else:
        parts.append("The service catalog status or completeness could not be confirmed, so unlisted services remain unknown.")
    visibility = summary.get("proxmox_guest_visibility") if isinstance(summary.get("proxmox_guest_visibility"), dict) else {}
    if str(visibility.get("status") or "").upper() in {"PARTIAL", "UNKNOWN"}:
        parts.append("Guest visibility is partial or unknown, so services on unreported guests remain unverified.")
    availability = summary.get("availability_summary") if isinstance(summary.get("availability_summary"), list) else []
    groups = _hades_homelab_availability_groups(availability)
    if groups["down"]:
        parts.append("Fresh configured probes are failing for: " + ", ".join(groups["down"][:8]) + ".")
    if groups["unknown"]:
        parts.append("Current probe state is unknown or stale for: " + ", ".join(
            item["name"] for item in groups["unknown"][:8]
        ) + ".")
    if groups["up"]:
        parts.append(f"{len(groups['up'])} configured probes responded, but that does not confirm application login or workload readiness.")
    if not availability:
        parts.append("No configured service-check observations were returned.")
    if summary.get("retrieved_at"):
        parts.append(f"The source read completed at {str(summary['retrieved_at'])[:80]}.")
    return " ".join(parts) or "I don't have enough current service evidence to identify coverage."

def _hades_homelab_provenance_response(summary):
    rows = (
        summary.get("sources") or summary.get("source_observations") or []
        if isinstance(summary, dict) else []
    )
    sources = [
        row for row in rows if isinstance(row, dict) and row.get("source")
    ] if isinstance(rows, list) else []
    if not sources:
        return "I refreshed the homelab view, but the current source reads did not include provenance details."
    details = []
    for row in sources[:8]:
        name = " ".join(str(row.get("source") or "").split())[:100]
        status = " ".join(str(row.get("status") or "UNKNOWN").replace("_", " ").lower().split())
        stamp = " ".join(str(row.get("retrieved_at") or "").split())[:64]
        details.append(f"{name}: {status}; " + (f"read at {stamp}" if stamp else "read time unavailable"))
    return (
        "I refreshed the configured homelab sources for this answer. "
        + "; ".join(details)
        + ". These are source-read times, not proof that older observations remain live. "
        "NetBox describes intended inventory, Proxmox reports runtime state, and configured probes report availability; those sources are not interchangeable."
    )

def _hades_homelab_conflict_response(summary):
    if not isinstance(summary, dict):
        return "I couldn't determine whether the current homelab sources conflict because the live summary is unavailable."
    conflicts = summary.get("conflicts", [])
    invalid_conflicts = not isinstance(conflicts, list)
    conflicts = conflicts if isinstance(conflicts, list) else []
    source_rows = summary.get("source_observations") or summary.get("sources") or []
    source_rows = source_rows if isinstance(source_rows, list) else []
    unavailable_sources = [
        row for row in source_rows
        if isinstance(row, dict)
        and str(row.get("status") or "UNKNOWN").upper()
        not in {"AVAILABLE", "READABLE", "HEALTHY", "OK", "COMPLETE"}
    ]
    incomplete = []
    if summary.get("status") not in (None, "OK", "COMPLETE"):
        incomplete.append("the overall source read is partial or unavailable")
    if invalid_conflicts:
        incomplete.append("the conflict records were unavailable or malformed")
    if unavailable_sources:
        labels = [
            " ".join(str(row.get("source") or "A configured source").split())[:64]
            for row in unavailable_sources[:4]
        ]
        incomplete.append("could not read " + ", ".join(labels))
    visibility = summary.get("proxmox_guest_visibility")
    if isinstance(visibility, dict):
        visibility_status = str(visibility.get("status") or "UNKNOWN").upper()
        if visibility_status not in {"COMPLETE", "NOT_CONFIGURED"}:
            incomplete.append("Proxmox guest visibility is partial or unknown")
    def incomplete_clause():
        if not incomplete:
            return ""
        return (
            " The comparison is incomplete because " + "; ".join(incomplete[:4])
            + ". The absence of a reported disagreement does not mean the sources agree."
        )

    if not conflicts:
        if incomplete:
            return (
                "I can't confirm whether the sources disagree because "
                + "; ".join(incomplete[:4])
                + ". No linked-record conflict was reported from the available data; that does not establish that the sources agree."
            )
        return (
            "The current bounded source read reported no linked-record conflicts. "
            "That does not prove inventory coverage is complete; unlinked or unreported records remain unknown."
        )
    details = []
    label_collisions = []
    for item in conflicts[:8]:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("name") or "Unnamed resource").split())[:100]
        reasons = item.get("reasons") if isinstance(item.get("reasons"), list) else []
        clean_reasons = [
            " ".join(str(reason).split())[:180]
            for reason in reasons[:4] if isinstance(reason, str) and reason.strip()
        ]
        if clean_reasons and all(
            reason.casefold().startswith(("display label is shared", "display name is ambiguous"))
            for reason in clean_reasons
        ):
            label_collisions.append(f"{name}: {clean_reasons[0]}")
        else:
            details.append(f"{name}: {'; '.join(clean_reasons) or 'sources do not align'}")
    if not details and not label_collisions:
        return "The source read reported conflict rows in an unreadable form; I can't safely summarize them." + incomplete_clause()
    if details:
        response = (
            "The current sources report these inventory/runtime disagreements: "
            + ". ".join(details)
            + ". I kept those records separate instead of choosing one source as universal truth."
        )
    else:
        response = "I found no cross-source inventory disagreement among the records compared in this read."
    if label_collisions:
        response += " Shared display labels remain separate by stable source identity: " + ". ".join(label_collisions) + "."
    return response + incomplete_clause()


def _hades_homelab_node_metrics_ranking_response(node_metrics):
    """Rank only current Proxmox host/node samples, separate from guests."""
    import math

    endpoints = node_metrics.get("endpoints") if isinstance(node_metrics.get("endpoints"), list) else []
    online_nodes = []

    def finite_number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        try:
            converted = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) else None

    for endpoint in endpoints:
        if not isinstance(endpoint, dict) or str(endpoint.get("status") or "").upper() != "AVAILABLE":
            continue
        nodes = endpoint.get("nodes") if isinstance(endpoint.get("nodes"), list) else []
        for node in nodes:
            if not isinstance(node, dict) or str(node.get("status") or "").upper() != "ONLINE":
                continue
            name = " ".join(str(node.get("name") or "Unnamed Proxmox node").split())[:100]
            cpu = finite_number(node.get("cpu_fraction"))
            cpu_percent = cpu * 100 if cpu is not None and 0 <= cpu <= 1 else None
            used = finite_number(node.get("memory_used_bytes"))
            total = finite_number(node.get("memory_total_bytes"))
            memory = (used, total) if used is not None and total is not None and 0 <= used <= total and total > 0 else None
            online_nodes.append((name, cpu_percent, memory, node.get("observed_at")))

    if not online_nodes:
        if str(node_metrics.get("status") or "UNKNOWN").upper() == "UNKNOWN":
            error_codes = {
                str(endpoint.get("error_code") or "").upper()
                for endpoint in endpoints if isinstance(endpoint, dict)
            }
            if "MISSING_SOURCE_TIMESTAMP" in error_codes:
                return (
                    "Current Proxmox host/node status and load are unknown because a source read "
                    "timestamp is missing; I can't rank host load."
                )
            if "UNSTABLE_SOURCE_IDENTITY" in error_codes:
                return (
                    "Current Proxmox host/node status and load are unknown because a source identity "
                    "is unstable; I can't rank host load."
                )
            return (
                "Current Proxmox host/node status and load are unknown; I can't rank host load."
            )
        return (
            "The Proxmox metrics read returned no observed online host/node samples, "
            "so I can't rank host load; this does not establish that no machines are online."
        )
    parts = []
    cpu_rows = [row for row in online_nodes if row[1] is not None]
    memory_rows = [row for row in online_nodes if row[2] is not None]
    if cpu_rows:
        highest = max(row[1] for row in cpu_rows)
        leaders = [row for row in cpu_rows if abs(row[1] - highest) < 1e-9]
        labels = ", ".join(sorted(row[0] for row in leaders)[:4])
        checked = sorted({str(row[3]) for row in leaders if row[3]})
        timestamp = f" (sampled {', '.join(checked)})" if checked else ""
        parts.append(
            f"Highest current Proxmox host CPU reading: {labels} at {highest:.1f}%{timestamp} "
            f"among {len(cpu_rows)} observed online nodes with valid CPU data."
        )
    else:
        parts.append("No comparable current Proxmox host CPU values were returned.")
    if memory_rows:
        ratios = [(row[2][0] / row[2][1], row) for row in memory_rows]
        highest = max(ratio for ratio, _row in ratios)
        leaders = [row for ratio, row in ratios if abs(ratio - highest) < 1e-9]
        labels = ", ".join(sorted(row[0] for row in leaders)[:4])
        if len(leaders) == 1:
            used, total = leaders[0][2]
            detail = f"{used / (1024 ** 3):.1f} / {total / (1024 ** 3):.1f} GiB"
        else:
            detail = f"{highest * 100:.1f}% (tied)"
        checked = sorted({str(row[3]) for row in leaders if row[3]})
        timestamp = f" (sampled {', '.join(checked)})" if checked else ""
        parts.append(
            f"Highest current Proxmox host memory use: {labels} at {detail} "
            f"({highest * 100:.1f}%){timestamp} among {len(memory_rows)} observed online nodes with valid memory data."
        )
    else:
        parts.append("No comparable current Proxmox host memory values were returned.")
    parts.append(
        f"This ranks {len(online_nodes)} observed online Proxmox host/node sample(s) only. "
        "Guest readings are separate and may overlap; this does not measure GPU load or process-level use."
    )
    state = str(node_metrics.get("status") or "UNKNOWN").upper()
    if state in {"PARTIAL", "UNAVAILABLE", "UNKNOWN"} or any(
        endpoint.get("truncated") is True for endpoint in endpoints if isinstance(endpoint, dict)
    ):
        parts.append("One or more Proxmox node feeds were unavailable, unknown, or truncated; this is not a complete host ranking.")
    return " ".join(parts)


def _hades_homelab_resource_ranking_response(summary):
    """Rank current Proxmox guest readings without implying host or GPU load."""
    node_metrics = summary.get("proxmox_node_metrics") if isinstance(summary, dict) else None
    if isinstance(node_metrics, dict):
        return _hades_homelab_node_metrics_ranking_response(node_metrics)
    resources = summary.get("resources", []) if isinstance(summary, dict) else []
    if not isinstance(resources, list):
        resources = []
    cpu_rows = []
    memory_rows = []
    online_records = []
    status_conflict = False

    def finite_number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if isinstance(value, int):
            return value
        try:
            converted = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) else None

    def finite_float(value):
        try:
            converted = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
        return converted if math.isfinite(converted) else None

    for item in resources[:256]:
        if not isinstance(item, dict):
            continue
        runtime = item.get("runtime") or item.get("runtime_detail")
        runtime = runtime if isinstance(runtime, dict) else {}
        runtime_status = str(item.get("runtime_status") or runtime.get("status") or "").casefold()
        currently_online = item.get("currently_online")
        runtime_positive = runtime_status in {"running", "online"}
        runtime_negative = runtime_status in {"stopped", "offline"}
        if (currently_online is False and runtime_positive) or (currently_online is True and runtime_negative):
            status_conflict = True
            continue
        if currently_online is False or runtime_negative:
            continue
        if currently_online is not True and not runtime_positive:
            continue
        name = " ".join(str(item.get("name") or runtime.get("name") or "Unnamed runtime").split())[:100]
        online_records.append(name)
        cpu = finite_number(runtime.get("cpu"))
        if cpu is not None and 0 <= cpu <= 1:
            cpu_rows.append((cpu * 100, name))
        memory, maximum = finite_number(runtime.get("mem")), finite_number(runtime.get("maxmem"))
        if memory is not None and maximum is not None and 0 <= memory <= maximum and maximum > 0:
            memory_value, maximum_value = finite_float(memory), finite_float(maximum)
            if memory_value is not None and maximum_value is not None:
                memory_rows.append((memory_value / maximum_value, memory_value, maximum_value, name))
    if not online_records:
        response = (
            "The current Proxmox metrics read returned no rows with an explicit online/running status, "
            "so I can't rank server load; this does not establish that no machines are online."
        )
        if status_conflict:
            response += " A record with conflicting current-status fields was excluded from the ranking."
        return response
    parts = []
    if cpu_rows:
        usage, name = max(cpu_rows)
        parts.append(f"Highest current Proxmox CPU reading: {name} at {usage:.1f}% among {len(cpu_rows)} online records with CPU data")
    if memory_rows:
        ratio, memory, maximum, name = max(memory_rows)
        gib = 1024 ** 3
        parts.append(
            f"Highest current Proxmox memory use: {name} at {memory / gib:.1f} / {maximum / gib:.1f} GiB "
            f"({ratio * 100:.1f}%) among {len(memory_rows)} online records with valid memory data"
        )
    if not parts:
        return "The current Proxmox records are online, but they contain no comparable CPU or memory readings."
    parts.append(
        f"This compares {len(online_records)} currently online Proxmox runtime record(s); "
        "host and guest readings are separate and may overlap. "
        "It does not measure process-level use, guest filesystem use, GPU load, or inference hosts not represented in Proxmox"
    )
    if status_conflict:
        parts.append("A record with conflicting current-status fields was excluded from the ranking.")
    observations = summary.get("source_observations") or summary.get("sources") or []
    proxmox_rows = [
        row for row in observations if isinstance(row, dict)
        and str(row.get("source") or "").casefold().startswith("proxmox")
        and row.get("retrieved_at")
    ] if isinstance(observations, list) else []
    if proxmox_rows:
        parts.append("Proxmox source read completed at " + str(proxmox_rows[0]["retrieved_at"])[:64])
    return ". ".join(parts) + "."


def _hades_homelab_proxmox_node_load_response(summary, target):
    """Answer a named host-load question from a unique current node identity."""
    import math
    import re

    node_metrics = summary.get("proxmox_node_metrics") if isinstance(summary, dict) else None
    if not isinstance(node_metrics, dict):
        return None
    target_key = re.sub(r"[^a-z0-9]+", "", str(target or "").casefold())
    if not target_key:
        return None
    def identity_keys(value):
        keys = {re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())}
        # Reconciled NetBox display labels can append an ordinal to separate
        # duplicate inventory names. Treat the base name as an alias only;
        # the normal unique-match check below still fails closed on collisions.
        base = re.sub(r"\s+\([^()]{1,40}\)\s*$", "", str(value or "")).strip()
        if base and base != value:
            keys.add(re.sub(r"[^a-z0-9]+", "", base.casefold()))
        return keys
    matches = [
        node for endpoint in node_metrics.get("endpoints", [])
        if isinstance(endpoint, dict) and endpoint.get("status") == "AVAILABLE"
        for node in endpoint.get("nodes", []) if isinstance(node, dict)
        and target_key in identity_keys(node.get("name")) | identity_keys(node.get("node"))
    ]
    if len(matches) > 1:
        return f"I can't verify current load for {str(target)[:100]}: multiple Proxmox node records match that name."
    if not matches:
        return (
            f"I can't verify current load for {str(target)[:100]}: no current Proxmox node sample "
            "uniquely matched that machine."
        )
    node = matches[0]
    label = (
        " ".join(str(target).split())[:100]
        if target_key in identity_keys(node.get("name")) | identity_keys(node.get("node"))
        else " ".join(str(node.get("name") or target).split())[:100]
    )
    state = str(node.get("status") or "UNKNOWN").upper()
    observed_at = str(node.get("observed_at") or "time unavailable")[:80]
    if state != "ONLINE":
        return f"Proxmox node status for {label} is {state.casefold()} as of {observed_at}; current host load is unverified."
    parts = [f"Proxmox reports {label} online; node metrics sampled at {observed_at}."]
    cpu = node.get("cpu_fraction")
    if isinstance(cpu, (int, float)) and not isinstance(cpu, bool) and math.isfinite(float(cpu)) and 0 <= cpu <= 1:
        parts.append(f"Host CPU reading is {float(cpu) * 100:.1f}%.")
    used, total = node.get("memory_used_bytes"), node.get("memory_total_bytes")
    if (
        isinstance(used, int) and not isinstance(used, bool) and used >= 0
        and isinstance(total, int) and not isinstance(total, bool) and total > 0 and used <= total
    ):
        parts.append(f"Host memory is {used / (1024 ** 3):.1f} / {total / (1024 ** 3):.1f} GiB.")
    if len(parts) == 1:
        parts.append("No comparable current host CPU or memory values were returned.")
    parts.append("These are host/node readings; guest readings may overlap. GPU and process-level use are separate.")
    return " ".join(parts)

def _hades_homelab_guest_inventory_response(summary):
    """List bounded current guest states without treating partial scope as empty."""
    inventory = summary.get("proxmox_guest_inventory") if isinstance(summary, dict) else None
    endpoints = inventory.get("endpoints") if isinstance(inventory, dict) else None
    if not isinstance(endpoints, list) or not endpoints:
        return "I can't verify configured Proxmox guest sources right now, so I can't list current guest power states."
    complete = bool(
        str(inventory.get("status") or "").upper() == "COMPLETE"
        and all(
            isinstance(endpoint, dict)
            and str(endpoint.get("status") or "").upper() == "COMPLETE"
            and str(endpoint.get("visibility_status") or "").upper() == "COMPLETE"
            and str(endpoint.get("visibility_scope") or "").upper() == "ALL_GUESTS"
            and endpoint.get("truncated") is not True
            for endpoint in endpoints
        )
    )
    guests = {}
    ambiguous = set()
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        source_id = str(endpoint.get("source_id") or "")
        rows = endpoint.get("guests") if isinstance(endpoint.get("guests"), list) else []
        for row in rows[:512]:
            if not isinstance(row, dict):
                continue
            identity = row.get("source_identity")
            kind = row.get("guest_type")
            guest_id = str(row.get("guest_id") or "")
            if (
                not isinstance(identity, str)
                or not re.fullmatch(rf"proxmox:{re.escape(source_id)}:(?:qemu|lxc):[1-9][0-9]{{0,19}}", identity)
                or kind not in {"qemu", "lxc"}
                or not re.fullmatch(r"[1-9][0-9]{0,19}", guest_id)
            ):
                continue
            if identity in guests:
                ambiguous.add(identity)
            else:
                guests[identity] = row
    if ambiguous:
        for identity in ambiguous:
            guests[identity] = {"guest_type": "unknown", "guest_id": identity.rsplit(":", 1)[-1], "status": "UNKNOWN"}
    states = {"RUNNING": [], "STOPPED": [], "UNKNOWN": []}
    for row in guests.values():
        kind = "VM" if row.get("guest_type") == "qemu" else "CT" if row.get("guest_type") == "lxc" else "guest"
        guest_id = str(row.get("guest_id") or "")
        name = " ".join(str(row.get("name") or "").split())[:100]
        label = f"{name} ({kind} {guest_id})" if name else f"{kind} {guest_id}"
        node = " ".join(str(row.get("node") or "").split())[:100]
        if node:
            label += f" on {node}"
        state = str(row.get("status") or "UNKNOWN").upper()
        states[state if state in {"RUNNING", "STOPPED"} else "UNKNOWN"].append(label)
    parts = [
        "Complete effective VM.Audit scope covers every configured Proxmox source."
        if complete else
        "This lists only guests visible in the configured Proxmox reads; combined guest scope is incomplete or unknown."
    ]
    if not guests and complete:
        parts.append("Proxmox reports no VM or container guests.")
    elif not guests:
        parts.append("No visible guest rows were returned; that does not establish an empty cluster.")
    for state, heading in (("RUNNING", "Running"), ("STOPPED", "Stopped"), ("UNKNOWN", "State unknown")):
        labels = states[state]
        if labels:
            parts.append(f"{heading}: " + "; ".join(labels[:20]) + (f"; and {len(labels) - 20} more" if len(labels) > 20 else "."))
    times = [str(row.get("retrieved_at"))[:64] for row in endpoints if isinstance(row, dict) and row.get("retrieved_at")]
    if times:
        parts.append("Proxmox guest reads completed at " + "; ".join(times[:8]) + ".")
    else:
        parts.append("Proxmox guest-read timestamps were not reported.")
    parts.append("This is VM/container power state, not application or service health.")
    return " ".join(parts)


def _hades_homelab_guest_index_workloads_view(
    *, node_label, node_state, guest_labels, coverage_complete, source_label, retrieved_at
):
    """Render prefiltered, owner-authorized Proxmox node workload values."""
    response = f"Proxmox reports node {node_label} as {node_state}. "
    if guest_labels:
        response += "Visible guests: " + "; ".join(guest_labels[:20]) + (
            f"; and {len(guest_labels) - 20} more." if len(guest_labels) > 20 else "."
        )
    elif coverage_complete:
        response += "The complete current guest inventory shows no VM/container guests on this node."
    else:
        response += (
            "No matching visible guest rows were returned; node guest inventory is incomplete, "
            "so this does not establish that the node is empty."
        )
    if not coverage_complete and guest_labels:
        response += " Guest visibility or node coverage is incomplete, so additional guests may be unreported."
    response += (
        f" Proxmox source {source_label} was read at {retrieved_at}."
        if retrieved_at else " The Proxmox read timestamp was not reported."
    )
    response += " Node state and VM/container power state do not establish application health."
    return response


def _hades_homelab_guest_visibility_response(summary):
    """Render effective Proxmox permission scope without inferring completeness."""
    visibility = summary.get("proxmox_guest_visibility") if isinstance(summary, dict) else None
    if not isinstance(visibility, dict):
        return "I couldn't verify current Proxmox guest-visibility scope."
    status = str(visibility.get("status") or "UNKNOWN").upper()
    scope = str(visibility.get("scope") or "UNKNOWN").upper()
    if status == "COMPLETE" and scope == "ALL_GUESTS":
        answer = "The latest read-only permission checks report all guests in scope at each configured Proxmox source."
    elif status == "PARTIAL" and scope == "SELECTED_GUESTS":
        answer = "The permission checks show selected guests only; HADES cannot verify other guest state."
    elif status == "PARTIAL" and scope == "ALL_GUESTS_WITH_EXCLUSIONS":
        answer = "The permission checks show broad guest scope with explicit exclusions, so the guest view is not complete."
    elif status == "PARTIAL" and scope == "NO_GUEST_AUDIT":
        answer = "At least one configured Proxmox source has no guest-audit visibility, so HADES cannot verify all guest state."
    elif status == "PARTIAL" or scope == "MIXED":
        answer = "Configured Proxmox guest-visibility scopes are mixed or incomplete, so HADES cannot claim a complete guest view."
    elif status == "NOT_CONFIGURED":
        answer = "Proxmox guest-visibility checks are not configured, so HADES cannot verify guest scope."
    else:
        answer = "HADES could not verify effective Proxmox permissions, so it cannot confirm complete guest visibility."
    answer += " This comes from read-only effective-permission data, not from assuming the returned guest list is exhaustive."
    rows = summary.get("source_observations") or summary.get("sources") or []
    times = [
        " ".join(str(row.get("retrieved_at") or "").split())[:64]
        for row in rows if isinstance(row, dict)
        and str(row.get("source") or "").startswith("Proxmox guest visibility")
        and row.get("retrieved_at")
    ] if isinstance(rows, list) else []
    if times:
        answer += " Permission-scope reads completed at " + ", ".join(times[:4]) + "."
    return answer
