"""Pure configuration shaping for the read-only homelab adapter."""

from __future__ import annotations

import os
from urllib.parse import urljoin


def _split(name: str) -> list[str]:
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


def proxmox_specs() -> tuple[tuple[str, str], ...]:
    """Resolve one or more standalone Proxmox read endpoints."""
    base_urls = _split("HADES_PROXMOX_RESOURCES_URLS")
    if not base_urls:
        base = os.environ.get("HADES_PROXMOX_RESOURCES_URL", "")
        if not base:
            api_base = os.environ.get("HADES_PROXMOX_URL", "").rstrip("/")
            base = f"{api_base}/cluster/resources" if api_base else ""
        base_urls = [base] if base else []
    token_files = _split("HADES_PROXMOX_TOKEN_FILES")
    if not token_files:
        token = os.environ.get("HADES_PROXMOX_TOKEN_FILE", "")
        token_files = [token] if token else [""]
    if len(token_files) not in {1, len(base_urls)}:
        raise ValueError("Proxmox URL and token-file counts must match or use one shared token file")
    if len(token_files) == 1:
        token_files *= len(base_urls)
    return tuple(zip(base_urls, token_files, strict=True))


def proxmox_token_ids() -> tuple[str, ...]:
    ids = _split("HADES_PROXMOX_TOKEN_IDS")
    count = len(proxmox_specs())
    if not ids:
        return tuple("" for _ in range(count))
    if len(ids) not in {1, count}:
        raise ValueError("Proxmox token-ID count must match URL count or use one shared token ID")
    if len(ids) == 1:
        ids *= count
    return tuple(ids)


def source_specs() -> tuple[tuple[str, str], ...]:
    """Resolve documented base inputs to the adapter's bounded GET paths."""
    proxmox_base = os.environ.get("HADES_PROXMOX_URL", "").rstrip("/")
    netbox_base = os.environ.get("HADES_NETBOX_URL", "").rstrip("/")
    kuma_base = os.environ.get("HADES_UPTIME_KUMA_URL", "").rstrip("/")
    kuma_slug = os.environ.get("HADES_UPTIME_KUMA_STATUS_SLUG", "").strip("/")
    return (
        (
            proxmox_specs()[0][0] if proxmox_specs() else "",
            proxmox_specs()[0][1] if proxmox_specs() else "",
        ),
        (
            os.environ.get("HADES_NETBOX_DEVICES_URL", "")
            or (urljoin(f"{netbox_base}/", "api/dcim/devices/") if netbox_base else ""),
            os.environ.get("HADES_NETBOX_TOKEN_FILE", ""),
        ),
        (
            os.environ.get("HADES_KUMA_STATUS_URL", "")
            or (f"{kuma_base}/api/status-page/heartbeat/{kuma_slug}" if kuma_base and kuma_slug else ""),
            os.environ.get("HADES_KUMA_TOKEN_FILE", ""),
        ),
    )


def capability_matrix_file() -> str:
    """Return the optional local, observed hardware capability manifest."""
    return os.environ.get("HADES_CAPABILITY_MATRIX_FILE", "").strip()
