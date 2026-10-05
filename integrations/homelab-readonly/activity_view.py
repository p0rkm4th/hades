"""Pure presentation for bounded Proxmox and NetBox activity observations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime


def format_recent_activity(
    report: object, bounded_text: Callable[..., str | None]
) -> str:
    """Format bounded Proxmox and NetBox evidence without claiming complete history."""
    if not isinstance(report, dict) or not isinstance(report.get("endpoints"), list):
        return "I couldn't read recent homelab activity."
    status = str(report.get("status") or "UNKNOWN").upper()
    if status == "NOT_CONFIGURED":
        return "No recent Proxmox or NetBox activity source is configured, so I can't verify recent homelab changes."
    if status == "INVALID_REQUEST":
        return "Choose a recent activity window from 1 to 168 hours."
    if status in {"SOURCE_UNAVAILABLE", "CONFIGURATION_ERROR", "UNKNOWN"}:
        return "I couldn't read the configured Proxmox or NetBox activity sources, so recent homelab changes are unknown."
    events = [
        event for endpoint in report["endpoints"]
        if isinstance(endpoint, dict)
        for event in endpoint.get("events", [])
        if isinstance(event, dict)
    ]
    source_status = report.get("source_status") if isinstance(report.get("source_status"), dict) else {}
    proxmox_status = str(source_status.get("proxmox") or ("READABLE" if report.get("endpoints") else "NOT_CONFIGURED"))
    netbox = report.get("netbox") if isinstance(report.get("netbox"), dict) else {}
    netbox_status = str(source_status.get("netbox") or netbox.get("status") or "NOT_CONFIGURED")
    netbox_objects = netbox.get("objects") if isinstance(netbox.get("objects"), list) else []
    window_hours = report.get("window_hours")
    window = f"the last {window_hours} hours" if type(window_hours) is int and 1 <= window_hours <= 168 else "the requested time window"
    retrieved_at = bounded_text(report.get("retrieved_at"), 40)
    read_stamp = f" Read at {retrieved_at}." if retrieved_at else " Read time unavailable."
    timeline = [(event.get("starttime", 0), "proxmox", event) for event in events]
    for obj in netbox_objects:
        if not isinstance(obj, dict):
            continue
        try:
            updated = datetime.fromisoformat(str(obj.get("last_updated", "")).replace("Z", "+00:00"))
            timestamp = updated.timestamp()
        except (ValueError, OverflowError):
            timestamp = 0
        timeline.append((timestamp, "netbox", obj))
    if timeline:
        summaries = []
        for _, source, item in sorted(timeline, key=lambda row: row[0], reverse=True)[:8]:
            if source == "netbox":
                kind = bounded_text(item.get("object_type"), 24) or "inventory record"
                name = bounded_text(item.get("name"), 100) or "an unnamed record"
                updated_at = bounded_text(item.get("last_updated"), 40) or "time unavailable"
                summaries.append(f"NetBox {kind} {name} was last updated at {updated_at}")
                continue
            event = item
            guest = bounded_text(event.get("guest_id"), 24) or "an audited guest"
            node = bounded_text(event.get("node"), 64) or "a Proxmox node"
            task = bounded_text(event.get("task_type"), 32) or "unknown task"
            state = str(event.get("status") or "UNKNOWN").casefold()
            summaries.append(f"{task} for guest {guest} on {node} ({state})")
        answer = "Recent recorded activity: " + "; ".join(summaries) + "."
        if len(timeline) > 8:
            answer += f" {len(timeline) - 8} additional records were omitted from this summary."
    else:
        empty = []
        if proxmox_status == "READABLE":
            empty.append("no archived Proxmox guest tasks were returned")
        elif proxmox_status == "PARTIAL":
            empty.append("no archived guest tasks were returned in the readable Proxmox scope")
        if netbox_status == "READABLE":
            empty.append("no recently updated NetBox device/service records were returned")
        answer = f"In {window}, " + " and ".join(empty) + "." if empty else "No configured activity source returned usable recent-change data."
    if proxmox_status in {"PARTIAL", "SOURCE_UNAVAILABLE", "NOT_CONFIGURED"}:
        detail = "not configured" if proxmox_status == "NOT_CONFIGURED" else "partial" if proxmox_status == "PARTIAL" else "unavailable"
        answer += f" Proxmox task coverage is {detail}."
    if netbox_status in {"PARTIAL", "SOURCE_UNAVAILABLE"}:
        detail = "partial" if netbox_status == "PARTIAL" else "unavailable"
        answer += f" NetBox inventory-update coverage is {detail}."
    elif netbox_status == "NOT_CONFIGURED":
        answer += " NetBox inventory-update reads are not configured."
    answer += read_stamp + (
        " This is bounded activity evidence, not a complete homelab change log. "
        "HADES has no saved prior snapshot for a before/after comparison; NetBox "
        "field differences and deletions are not included, and completed Proxmox "
        "tasks don't prove resulting guest configuration or application health. "
        "Host operating-system, package/driver, and in-guest service events aren't "
        "included in these sources."
    )
    return answer
