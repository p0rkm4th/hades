"""Bounded read-only projection of NetBox application-service records."""

from __future__ import annotations

import ipaddress
from typing import Any


MAX_SERVICES = 100


def _rows(payload: Any, label: str) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, dict):
        raise ValueError(f"NetBox {label} response must be an object")
    values = payload.get("results", [])
    if not isinstance(values, list):
        raise ValueError(f"NetBox {label} results must be a list")
    if len(values) > 10000:
        raise ValueError(f"NetBox {label} results exceed the bounded input size")
    return [value for value in values if isinstance(value, dict)]


def _short_text(value: Any, limit: int = 120) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:limit] or None


def _ip(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("address")
    if not isinstance(value, str):
        return None
    try:
        return str(ipaddress.ip_interface(value.strip()).ip)
    except ValueError:
        return None


def _port_mappings(row: dict[str, Any]) -> list[str]:
    values = row.get("port_mappings")
    if not isinstance(values, list):
        protocol, ports = row.get("protocol"), row.get("ports")
        values = [f"{protocol}/{port}" for port in ports] if (
            isinstance(protocol, str) and isinstance(ports, list)
        ) else []
    result: list[str] = []
    for value in values[:64]:
        if not isinstance(value, str):
            continue
        protocol, separator, port = value.strip().lower().partition("/")
        if not separator or protocol not in {"tcp", "udp", "sctp"} or not port.isdigit():
            continue
        number = int(port)
        if 1 <= number <= 65535:
            result.append(f"{protocol}/{number}")
    return sorted(set(result))


def project_netbox_services(
    services_payload: Any,
    devices_payload: Any,
) -> dict[str, Any]:
    """Return service names, parent, declared endpoint, and mappings only.

    NetBox is intended inventory, not a liveness source. This projection never
    claims a service is running or reachable.
    """
    services = _rows(services_payload, "services")
    reported_total = (
        services_payload.get("count")
        if isinstance(services_payload, dict)
        and type(services_payload.get("count")) is int
        and services_payload["count"] >= 0
        else None
    )
    has_next_page = bool(
        isinstance(services_payload, dict) and services_payload.get("next")
    )
    devices = _rows(devices_payload, "devices")
    by_id: dict[str, dict[str, Any]] = {}
    for device in devices:
        if device.get("id") is not None:
            by_id[str(device["id"])] = device

    projected = []
    for row in services[:MAX_SERVICES]:
        name = _short_text(row.get("name"))
        if not name:
            continue
        parent_type = "unknown"
        parent = None
        for key, kind in (
            ("device", "device"),
            ("virtual_machine", "virtual_machine"),
            ("fhrp_group", "fhrp_group"),
        ):
            candidate = row.get(key)
            if isinstance(candidate, dict):
                parent_type, parent = kind, candidate
                break

        parent_id = str(parent.get("id")) if parent and parent.get("id") is not None else None
        parent_name = _short_text(parent.get("name")) if parent else None
        # A parent carrying an ID must resolve by that stable ID only. A
        # same-name device is not proof that it is the service's parent.
        inventory_parent = by_id.get(parent_id) if parent_id else None

        bound_addresses = row.get("ipaddresses", row.get("ip_addresses", []))
        addresses = []
        if isinstance(bound_addresses, list):
            for item in bound_addresses[:16]:
                address = _ip(item)
                if address and address not in addresses:
                    addresses.append(address)
        address_source = "NetBox service-bound IP" if addresses else None
        if not addresses and inventory_parent:
            for field in ("primary_ip4", "primary_ip", "primary_ip6"):
                address = _ip(inventory_parent.get(field))
                if address:
                    addresses.append(address)
                    address_source = "NetBox parent primary IP"
                    break

        projected.append({
            "name": name,
            "parent_type": parent_type,
            "parent_name": parent_name,
            "addresses": addresses,
            "address_source": address_source,
            "port_mappings": _port_mappings(row),
            "runtime_status": "UNKNOWN",
        })

    truncated = (
        len(services) > MAX_SERVICES
        or has_next_page
        or (reported_total is not None and reported_total > len(services))
    )
    if reported_total == 0 and not services and not has_next_page:
        coverage = "EMPTY"
    elif reported_total is not None and reported_total == len(services) and not has_next_page:
        coverage = "COMPLETE"
    elif truncated or (reported_total is not None and reported_total != len(services)):
        coverage = "PARTIAL"
    else:
        coverage = "UNKNOWN"

    return {
        "status": "OK",
        "source": "NetBox application services",
        "coverage": coverage,
        "records_returned": min(len(services), MAX_SERVICES),
        "source_total": reported_total,
        "inventory_is_not_liveness": True,
        "writes_performed": False,
        "services": projected,
        "truncated": truncated,
        "limitation": "NetBox describes intended service endpoints; runtime and reachability require separate live evidence.",
    }
