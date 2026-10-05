"""Bounded presentation projection for composed homelab summaries."""

from __future__ import annotations


def project_summary_response(result: dict, errors: list[str]) -> dict:
    """Return the compact conversational view without changing source results."""
    response = dict(result)
    # Keep the common owner answer bounded. Preserve the authority and decision
    # fields needed for status/location questions while leaving the full
    # capability matrix to homelab_compute_capabilities().
    compact_resources = []
    for resource in result.get("resources", []):
        inventory = resource.get("inventory") or {}
        availability = resource.get("availability") or {}
        compact_resources.append({
            "name": resource.get("name"),
            "identity": resource.get("identity"),
            "runtime_status": resource.get("runtime_status"),
            "currently_online": resource.get("currently_online"),
            "runtime": resource.get("runtime"),
            "inventory_device_id": inventory.get("id"),
            "related_inventory_device_id": resource.get("related_inventory_device_id"),
            "primary_ip": inventory.get("primary_ip"),
            "role": inventory.get("role"),
            "availability_status": availability.get("status"),
            "availability_freshness": resource.get("availability_freshness"),
            "conflicts": resource.get("conflicts", []),
        })
    # The complete name/availability lists remain authoritative; this is only
    # the optional per-resource detail view.
    resource_limit = 4
    if len(compact_resources) > resource_limit:
        response["resources_truncated"] = {
            "returned": resource_limit,
            "total": len(compact_resources),
            "reason": "use homelab_compute_capabilities or a targeted follow-up for more detail",
        }
        compact_resources = compact_resources[:resource_limit]
    response["resources"] = compact_resources
    for field, limit in (
        ("online_names", 24),
        ("inventory_only_names", 12),
        ("availability_summary", 12),
    ):
        values = result.get(field)
        if isinstance(values, list) and len(values) > limit:
            response[f"{field}_truncated"] = {
                "returned": limit,
                "total": len(values),
            }
            response[field] = values[:limit]
    response["supplemental_hardware"] = {
        "status": "AVAILABLE",
        "source": "observed capability matrix",
        "availability_not_provided": True,
        "use_homelab_compute_capabilities_for_details": True,
    }
    if errors:
        response["errors"] = list(errors)
    return response
