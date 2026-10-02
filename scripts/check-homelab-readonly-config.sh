#!/usr/bin/env bash
set -euo pipefail

# Validate the configured read-only source contract without contacting a host.
# Credential contents and endpoint values are never printed.
python3 - <<'PY'
import ipaddress
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit

missing: list[str] = []
invalid: list[str] = []
warnings: list[str] = []


def split(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw:
        return []
    values = [part.strip() for part in raw.split(",")]
    if any(not part for part in values):
        invalid.append(f"{name} contains an empty list item")
        return []
    return values


def urls_for_proxmox() -> list[str]:
    urls = split("HADES_PROXMOX_RESOURCES_URLS")
    if urls:
        return urls
    resource_url = os.environ.get("HADES_PROXMOX_RESOURCES_URL", "")
    if resource_url:
        return [resource_url]
    api_url = os.environ.get("HADES_PROXMOX_URL", "").rstrip("/")
    return [f"{api_url}/cluster/resources"] if api_url else []


def valid_https(name: str, value: str) -> bool:
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.fragment
            and "example.invalid" not in parsed.hostname
        )
    except ValueError:
        valid = False
    if not valid:
        invalid.append(f"{name} must contain valid HTTPS endpoint(s) without embedded credentials")
    return valid


def protected_files(name: str, values: list[str], *, expected: int) -> None:
    if len(values) not in {1, expected}:
        invalid.append(f"{name} count must be one or match its endpoint count")
        return
    for value in values:
        path = Path(value)
        try:
            info = path.lstat()
            mode = stat.S_IMODE(info.st_mode)
            if not stat.S_ISREG(info.st_mode) or mode not in {0o600, 0o640}:
                raise ValueError
            if info.st_size <= 0 or info.st_size > 8192 or not path.read_bytes().strip():
                raise ValueError
        except (OSError, ValueError):
            invalid.append(f"{name} must reference regular, nonempty files with mode 0600 or 0640")
            return


pve_urls = urls_for_proxmox()
if not pve_urls:
    missing.append("HADES_PROXMOX_RESOURCES_URLS")
for url in pve_urls:
    if valid_https("Proxmox endpoint", url):
        if not urlsplit(url).path.endswith("/api2/json/cluster/resources"):
            invalid.append("Proxmox resource URLs must end in /api2/json/cluster/resources")

pve_ids = split("HADES_PROXMOX_TOKEN_IDS")
if not pve_ids:
    missing.append("HADES_PROXMOX_TOKEN_IDS")
elif len(pve_ids) not in {1, len(pve_urls)}:
    invalid.append("HADES_PROXMOX_TOKEN_IDS count must be one or match the Proxmox endpoint count")
elif any(not re.fullmatch(r"[A-Za-z0-9._-]+@[A-Za-z0-9._-]+![A-Za-z0-9._-]+", item) for item in pve_ids):
    invalid.append("HADES_PROXMOX_TOKEN_IDS contains an invalid token identity")

pve_files = split("HADES_PROXMOX_TOKEN_FILES")
if not pve_files:
    single = os.environ.get("HADES_PROXMOX_TOKEN_FILE", "")
    pve_files = [single] if single else []
if not pve_files:
    missing.append("HADES_PROXMOX_TOKEN_FILES")
else:
    protected_files("HADES_PROXMOX_TOKEN_FILES", pve_files, expected=len(pve_urls))

# The retired inline-secret names are not consumed by the read-only adapter.
if os.environ.get("HADES_PROXMOX_TOKEN_SECRET") or os.environ.get("HADES_PROXMOX_TOKEN_ID"):
    invalid.append("use HADES_PROXMOX_TOKEN_IDS and protected token files; inline Proxmox credentials are unsupported")

netbox_url = os.environ.get("HADES_NETBOX_URL", "")
if not netbox_url:
    missing.append("HADES_NETBOX_URL")
else:
    valid_https("HADES_NETBOX_URL", netbox_url)
netbox_file = os.environ.get("HADES_NETBOX_TOKEN_FILE", "")
if not netbox_file:
    missing.append("HADES_NETBOX_TOKEN_FILE")
else:
    protected_files("HADES_NETBOX_TOKEN_FILE", [netbox_file], expected=1)
if os.environ.get("HADES_NETBOX_TOKEN"):
    invalid.append("use HADES_NETBOX_TOKEN_FILE; inline NetBox credentials are unsupported")

kuma_url = os.environ.get("HADES_UPTIME_KUMA_URL", "")
if not kuma_url:
    missing.append("HADES_UPTIME_KUMA_URL")
else:
    valid_https("HADES_UPTIME_KUMA_URL", kuma_url)
slug = os.environ.get("HADES_UPTIME_KUMA_STATUS_SLUG", "")
if not slug:
    missing.append("HADES_UPTIME_KUMA_STATUS_SLUG")
elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", slug):
    invalid.append("HADES_UPTIME_KUMA_STATUS_SLUG must be an alphanumeric slug")

networks = os.environ.get("HADES_DISCOVERY_ALLOWED_NETWORKS", "")
if not networks:
    missing.append("HADES_DISCOVERY_ALLOWED_NETWORKS")
else:
    try:
        values = [ipaddress.ip_network(item.strip(), strict=False) for item in networks.split(",")]
        if not values or any(n.version != 4 or n.num_addresses > 4096 or n.is_global for n in values):
            raise ValueError
    except ValueError:
        invalid.append("HADES_DISCOVERY_ALLOWED_NETWORKS must contain bounded private IPv4 CIDRs")

source_ids = split("HADES_PROXMOX_SOURCE_IDS")
if source_ids and (
    len(source_ids) != len(pve_urls)
    or len(set(source_ids)) != len(source_ids)
    or any(not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", item) for item in source_ids)
):
    invalid.append("HADES_PROXMOX_SOURCE_IDS must contain unique valid IDs matching the endpoint count")
if not source_ids:
    warnings.append("Proxmox source IDs are not configured; runtime records cannot use durable cross-source links")
if not os.environ.get("HADES_HOMELAB_IDENTITY_LINKS_FILE"):
    warnings.append("homelab identity links are not configured; sources remain separate observations")
if not os.environ.get("HADES_INFERENCE_ENDPOINTS_JSON"):
    warnings.append("provider-native inference inventory is not configured")

for message in invalid:
    print(f"FAIL {message}")
if invalid:
    raise SystemExit(1)
for name in missing:
    print(f"BLOCKED {name} is not configured")
if missing:
    print("Homelab read-only configuration is incomplete; no network probes were made")
    raise SystemExit(2)
for message in warnings:
    print(f"WARN {message}")
print("PASS homelab read-only configuration shape")
print("PASS no network probes performed")
PY
