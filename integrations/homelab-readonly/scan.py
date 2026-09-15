"""Bounded, read-only Nmap evidence producer.

The worker is deliberately separate from the homelab MCP adapter.  It may
produce evidence for review, but it has no inventory or management client and
never writes a discovered device anywhere.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import subprocess
from pathlib import Path
from typing import Any

from discovery import parse_nmap_xml

MAX_SCAN_SECONDS = 60
DEFAULT_PORTS = "22,53,80,443,445,631,8080,8443"


def _validate_ports(ports: str) -> str:
    if not ports or len(ports) > 256:
        raise ValueError("scan ports must be a bounded non-empty list")
    pieces = ports.split(",")
    if not pieces or len(pieces) > 128:
        raise ValueError("scan ports exceed the bounded list size")
    normalized: list[str] = []
    for piece in pieces:
        if "-" in piece:
            values = piece.split("-")
            if len(values) != 2:
                raise ValueError("scan port range is invalid")
            try:
                start, end = (int(value) for value in values)
            except ValueError as exc:
                raise ValueError("scan ports must be numeric") from exc
            if not 1 <= start <= end <= 65535:
                raise ValueError("scan port range is outside the valid range")
            normalized.append(f"{start}-{end}")
        else:
            try:
                value = int(piece)
            except ValueError as exc:
                raise ValueError("scan ports must be numeric") from exc
            if not 1 <= value <= 65535:
                raise ValueError("scan port is outside the valid range")
            normalized.append(str(value))
    return ",".join(normalized)


def run_bounded_scan(
    target: str,
    *,
    allowed_networks: list[str],
    nmap_binary: str = "/usr/bin/nmap",
    ports: str = DEFAULT_PORTS,
    timeout_seconds: int = MAX_SCAN_SECONDS,
) -> dict[str, Any]:
    """Run a constrained TCP-connect scan and normalize its XML evidence.

    Target authorization is checked before starting the process.  The command
    uses an argv list (never a shell), disables scripts/OS/version probing,
    emits XML only to stdout, and cannot mutate an inventory system.
    """

    try:
        requested = ipaddress.ip_network(target, strict=False)
    except ValueError as exc:
        raise ValueError("scan target must be a valid IP network") from exc
    allowed = []
    for value in allowed_networks:
        try:
            allowed.append(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise ValueError("allowed discovery scope is invalid") from exc
    if not allowed or not any(requested.subnet_of(scope) for scope in allowed):
        raise ValueError("scan target is outside the allowed discovery scope")
    if not Path(nmap_binary).is_file():
        raise ValueError("configured Nmap binary is missing")
    if not 1 <= timeout_seconds <= MAX_SCAN_SECONDS:
        raise ValueError("scan timeout exceeds the bounded limit")
    normalized_ports = _validate_ports(ports)
    command = [
        nmap_binary,
        "-n",
        "-Pn",
        "-sT",
        "--open",
        "--max-retries",
        "1",
        "--host-timeout",
        f"{timeout_seconds}s",
        "-T2",
        "-p",
        normalized_ports,
        "-oX",
        "-",
        str(requested),
    ]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Nmap scan timed out; outcome is unknown") from exc
    if completed.returncode != 0:
        raise RuntimeError("Nmap scan failed; no inventory mutation was attempted")
    retrieved_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return parse_nmap_xml(
        completed.stdout,
        target=str(requested),
        allowed_networks=[str(scope) for scope in allowed],
        retrieved_at=retrieved_at,
    )
