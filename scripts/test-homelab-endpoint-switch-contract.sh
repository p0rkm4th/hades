#!/usr/bin/env bash
set -euo pipefail

# Exercise endpoint switching without contacting any endpoint or loading
# credentials. The adapter must resolve a restored management plane from
# explicit URLs while preserving independent Proxmox source pairing.
python3 - <<'PY'
import importlib.util
import os
from pathlib import Path

path = Path("integrations/homelab-readonly/config.py")
spec = importlib.util.spec_from_file_location("hades_homelab_config", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

managed = (
    "HADES_PROXMOX_URL", "HADES_NETBOX_URL", "HADES_UPTIME_KUMA_URL",
    "HADES_UPTIME_KUMA_STATUS_SLUG", "HADES_PROXMOX_RESOURCES_URLS",
    "HADES_PROXMOX_TOKEN_FILES", "HADES_PROXMOX_TOKEN_IDS",
    "HADES_NETBOX_DEVICES_URL", "HADES_NETBOX_TOKEN_FILE",
    "HADES_KUMA_STATUS_URL", "HADES_KUMA_CONFIG_URL", "HADES_KUMA_TOKEN_FILE",
)
saved = {key: os.environ.get(key) for key in managed}
try:
    os.environ.update({
        "HADES_PROXMOX_URL": "https://pve-old.example.test:8006/api2/json",
        "HADES_NETBOX_URL": "https://netbox-old.example.test",
        "HADES_UPTIME_KUMA_URL": "https://kuma-old.example.test",
        "HADES_UPTIME_KUMA_STATUS_SLUG": "old-status",
    })
    assert module.source_specs() == (
        ("https://pve-old.example.test:8006/api2/json/cluster/resources", ""),
        ("https://netbox-old.example.test/api/dcim/devices/", ""),
        ("https://kuma-old.example.test/api/status-page/heartbeat/old-status", ""),
    )

    # Simulate a restored management plane and two independently addressed PVE
    # nodes. Explicit endpoint overrides must win without contacting either.
    os.environ.update({
        "HADES_PROXMOX_RESOURCES_URLS": "https://pve-new-a.example.test/r,https://pve-new-b.example.test/r",
        "HADES_PROXMOX_TOKEN_FILES": "/run/hades/a,/run/hades/b",
        "HADES_PROXMOX_TOKEN_IDS": "svc-a@pve!ro,svc-b@pve!ro",
        "HADES_NETBOX_DEVICES_URL": "https://netbox-new.example.test/api/dcim/devices/",
        "HADES_NETBOX_TOKEN_FILE": "/run/hades/netbox-ro",
        "HADES_KUMA_STATUS_URL": "https://kuma-new.example.test/api/status-page/heartbeat/restored",
        "HADES_KUMA_CONFIG_URL": "https://kuma-new.example.test/api/status-page/restored",
        "HADES_KUMA_TOKEN_FILE": "/run/hades/kuma-ro",
    })
    assert module.proxmox_specs() == (
        ("https://pve-new-a.example.test/r", "/run/hades/a"),
        ("https://pve-new-b.example.test/r", "/run/hades/b"),
    )
    assert module.proxmox_token_ids() == ("svc-a@pve!ro", "svc-b@pve!ro")
    assert module.source_specs() == (
        ("https://pve-new-a.example.test/r", "/run/hades/a"),
        ("https://netbox-new.example.test/api/dcim/devices/", "/run/hades/netbox-ro"),
        ("https://kuma-new.example.test/api/status-page/heartbeat/restored", "/run/hades/kuma-ro"),
    )

    os.environ["HADES_PROXMOX_TOKEN_FILES"] = "/run/hades/a,/run/hades/b,/run/hades/c"
    try:
        module.proxmox_specs()
    except ValueError as exc:
        assert "counts must match" in str(exc)
    else:
        raise AssertionError("mismatched restored Proxmox token files were accepted")
finally:
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

print("PASS homelab endpoint switching honors explicit restored URLs")
print("PASS multi-Proxmox endpoint/token pairing remains deterministic")
print("PASS mismatched endpoint credentials fail closed before network access")
PY
