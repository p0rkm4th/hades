"""Pure, source-independent views of normalized homelab observations."""

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
    conflicts = summary.get("conflicts", []) if isinstance(summary, dict) else []
    if not isinstance(conflicts, list) or not conflicts:
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
        return "The source read reported conflict rows in an unreadable form; I can't safely summarize them."
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
    return response
