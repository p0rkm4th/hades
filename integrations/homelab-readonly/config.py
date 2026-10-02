"""Pure configuration shaping for the read-only homelab adapter."""

from __future__ import annotations

import os
import json
import re
from pathlib import Path
from urllib.parse import urljoin


MAX_IDENTITY_LINK_BYTES = 65536
MAX_IDENTITY_LINKS = 1024


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


def proxmox_source_ids(
    specs: tuple[tuple[str, str], ...] | None = None,
) -> tuple[str, ...]:
    """Return stable configured identities for independent Proxmox APIs."""
    specs = specs if specs is not None else proxmox_specs()
    configured = _split("HADES_PROXMOX_SOURCE_IDS")
    if configured:
        if len(configured) != len(specs):
            raise ValueError("Proxmox source-ID count must match endpoint count")
        ids = configured
    else:
        # Ordinals are source-local labels only. Cross-source links involving
        # Proxmox require explicit stable IDs in HADES_PROXMOX_SOURCE_IDS.
        ids = tuple(f"endpoint-{index + 1}" for index in range(len(specs)))
    if any(not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value) for value in ids):
        raise ValueError("Proxmox source IDs contain an invalid identifier")
    if len(set(ids)) != len(ids):
        raise ValueError("Proxmox source IDs must be unique")
    return tuple(ids)


def identity_links_file() -> str:
    """Return the optional protected source-identity link file path."""
    return os.environ.get("HADES_HOMELAB_IDENTITY_LINKS_FILE", "").strip()


def load_identity_links() -> dict[str, str]:
    """Load source-to-NetBox ID links without introducing inventory fields.

    The file contains only stable source identifiers and canonical NetBox
    device IDs. It cannot override names, addresses, roles, health, or state.
    """
    path_value = identity_links_file()
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.is_file() or path.is_symlink():
        raise ValueError("homelab identity-link file must be a regular non-symlink file")
    if path.stat().st_mode & 0o777 not in {0o600, 0o640}:
        raise ValueError("homelab identity-link file must be mode 0600 or 0640")
    if path.stat().st_size > MAX_IDENTITY_LINK_BYTES:
        raise ValueError("homelab identity-link file exceeds the bounded size")
    document = json.loads(path.read_text(encoding="utf-8"))
    entries = document.get("links") if isinstance(document, dict) else None
    if not isinstance(entries, list) or len(entries) > MAX_IDENTITY_LINKS:
        raise ValueError("homelab identity-link file must contain a bounded links list")
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("homelab identity-link entry must be an object")
        source = entry.get("source_identity")
        device_id = entry.get("netbox_device_id")
        if not isinstance(source, str) or not source or len(source) > 256:
            raise ValueError("homelab source identity is invalid")
        if not source.startswith(("proxmox:", "kuma:monitor:")):
            raise ValueError("homelab identity links may only bind Proxmox or Kuma sources")
        if not re.fullmatch(
            r"(?:proxmox:[A-Za-z0-9._-]{1,128}:[A-Za-z0-9._-]{1,32}:[A-Za-z0-9._-]{1,128}|kuma:monitor:[1-9][0-9]{0,19})",
            source,
        ):
            raise ValueError("homelab source identity has an invalid format")
        if isinstance(device_id, bool) or not str(device_id).isdigit() or int(device_id) < 1:
            raise ValueError("homelab identity link requires a positive NetBox device ID")
        if source in result:
            raise ValueError("homelab source identity is linked more than once")
        result[source] = f"netbox:device:{int(device_id)}"
    return result


def source_specs() -> tuple[tuple[str, str], ...]:
    """Resolve documented base inputs to the adapter's bounded GET paths."""
    proxmox_base = os.environ.get("HADES_PROXMOX_URL", "").rstrip("/")
    netbox_base = os.environ.get("HADES_NETBOX_URL", "").rstrip("/")
    kuma_base = os.environ.get("HADES_UPTIME_KUMA_URL", "").rstrip("/")
    kuma_slug = os.environ.get("HADES_UPTIME_KUMA_STATUS_SLUG", "").strip("/")
    try:
        proxmox = proxmox_specs()
    except ValueError:
        # A bad Proxmox endpoint list must not prevent independent NetBox or
        # Kuma reads. homelab_summary reports the Proxmox configuration error
        # separately while continuing with these sources.
        proxmox = ()
    return (
        proxmox[0] if proxmox else ("", ""),
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


def netbox_services_spec() -> tuple[str, str]:
    """Resolve the optional read-only NetBox application-services endpoint."""
    base = os.environ.get("HADES_NETBOX_URL", "").rstrip("/")
    url = os.environ.get("HADES_NETBOX_SERVICES_URL", "")
    if not url and base:
        url = urljoin(f"{base}/", "api/ipam/services/")
    return url, os.environ.get("HADES_NETBOX_TOKEN_FILE", "")


def capability_matrix_file() -> str:
    """Return the optional local, observed hardware capability manifest."""
    return os.environ.get("HADES_CAPABILITY_MATRIX_FILE", "").strip()
