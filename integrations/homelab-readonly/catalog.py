"""Review-only projections from network discovery evidence.

This module deliberately does not create a second inventory. It turns a
normalized Nmap result into short-lived candidates that an operator can
review against NetBox before any future, separately authorized reconciliation.
"""

from __future__ import annotations

from typing import Any


def _inventory_index(netbox: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if netbox is not None and not isinstance(netbox, dict):
        raise ValueError("NetBox context must be a JSON object")
    rows = (netbox or {}).get("results", [])
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return index
    for row in rows:
        if not isinstance(row, dict):
            continue
        keys = {str(row.get(key, "")).strip().casefold() for key in ("name", "hostname", "ip", "address")}
        for key in keys - {""}:
            index.setdefault(key, row)
    return index


def propose_inventory_candidates(
    evidence: dict[str, Any],
    netbox: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return review-only device candidates from normalized scan evidence."""
    if not isinstance(evidence, dict) or evidence.get("source") != "nmap.xml":
        raise ValueError("discovery evidence must be normalized Nmap evidence")
    hosts = evidence.get("hosts")
    if not isinstance(hosts, list):
        raise ValueError("discovery evidence hosts must be a list")
    index = _inventory_index(netbox)
    candidates: list[dict[str, Any]] = []
    for host in hosts:
        if not isinstance(host, dict) or not isinstance(host.get("ip"), str):
            raise ValueError("discovery host must include an IP address")
        ip = host["ip"].strip()
        hostname = host.get("hostname") if isinstance(host.get("hostname"), str) else None
        match = index.get((hostname or "").casefold()) or index.get(ip.casefold())
        candidates.append({
            "status": "REVIEW_REQUIRED",
            "name": hostname or ip,
            "observed_ip": ip,
            "open_ports": host.get("ports", []),
            "netbox_match": match,
            "source": "nmap.xml",
            "retrieved_at": evidence.get("retrieved_at"),
        })
    return {
        "status": "REVIEW_REQUIRED" if candidates else "NO_CANDIDATES",
        "target": evidence.get("target"),
        "retrieved_at": evidence.get("retrieved_at"),
        "candidates": candidates,
        "writes_performed": False,
        "authority": {"discovery": "Nmap evidence", "inventory": "NetBox"},
    }
