"""Bounded, read-only Nmap XML evidence normalization.

This module parses scanner output supplied by an operator or disposable
fixture. It does not invoke Nmap, probe a network, or write inventory.
"""

from __future__ import annotations

import ipaddress
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

MAX_XML_BYTES = 2 * 1024 * 1024
MAX_HOSTS = 1024
MAX_PORTS_PER_HOST = 256


def _network(value: str) -> ipaddress._BaseNetwork:
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise ValueError("scan scope must be a valid IP network") from exc


def parse_nmap_xml(
    document: str | bytes,
    *,
    target: str,
    allowed_networks: list[str],
    retrieved_at: str,
) -> dict[str, Any]:
    raw = document.encode() if isinstance(document, str) else document
    if not raw or len(raw) > MAX_XML_BYTES:
        raise ValueError("Nmap evidence is empty or exceeds the bounded size")
    requested = _network(target)
    if not retrieved_at:
        raise ValueError("Nmap evidence requires a retrieval timestamp")
    try:
        datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Nmap evidence retrieval timestamp is invalid") from exc
    allowed = [_network(value) for value in allowed_networks]
    if not any(requested.subnet_of(scope) for scope in allowed):
        raise ValueError("Nmap target is outside the allowed discovery scope")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("Nmap evidence is not valid XML") from exc

    hosts: list[dict[str, Any]] = []
    for host in root.findall("host"):
        if len(hosts) >= MAX_HOSTS:
            raise ValueError("Nmap evidence exceeds the host bound")
        status = host.find("status")
        if status is not None and status.get("state") != "up":
            continue
        address = next(
            (node.get("addr") for node in host.findall("address") if node.get("addrtype") in {"ipv4", "ipv6"}),
            None,
        )
        if not address:
            continue
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("Nmap host has an invalid address") from exc
        if ip not in requested or not any(ip in scope for scope in allowed):
            raise ValueError("Nmap host falls outside the allowed discovery scope")
        hostname = next((node.get("name") for node in host.findall("hostnames/hostname") if node.get("name")), None)
        ports: list[dict[str, Any]] = []
        for port in host.findall("ports/port"):
            state = port.find("state")
            if state is None or state.get("state") != "open":
                continue
            try:
                port_id = int(port.get("portid", ""))
            except ValueError as exc:
                raise ValueError("Nmap port is not numeric") from exc
            if not 1 <= port_id <= 65535:
                raise ValueError("Nmap port is outside the valid range")
            service = port.find("service")
            row = {"port": port_id, "protocol": port.get("protocol", "tcp")}
            if service is not None and service.get("name"):
                row["service"] = service.get("name")
            ports.append(row)
            if len(ports) > MAX_PORTS_PER_HOST:
                raise ValueError("Nmap evidence exceeds the port bound")
        hosts.append({"ip": str(ip), "hostname": hostname, "ports": ports})
    return {
        "source": "nmap.xml", "target": str(requested),
        "retrieved_at": retrieved_at, "hosts": hosts,
    }
