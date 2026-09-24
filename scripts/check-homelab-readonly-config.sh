#!/usr/bin/env bash
set -euo pipefail

# Validate the minimum read-only homelab configuration without contacting any
# external service. Values are deliberately never printed because credentials
# may be present in the environment.

missing=0
invalid=0

require_value() {
  local name=$1 value=${!1-}
  if [[ -z "$value" ]]; then
    printf 'BLOCKED %s is not configured\n' "$name"
    missing=1
  fi
}

require_https_url() {
  local name=$1 value=${!1-}
  [[ -z "$value" ]] && return
  if [[ ! "$value" =~ ^https://[^[:space:]]+$ || "$value" == *example.invalid* || "$value" == *'<private>'* ]]; then
    printf 'FAIL %s is not a real HTTPS endpoint\n' "$name"
    invalid=1
  fi
}

require_value HADES_PROXMOX_URL
require_value HADES_PROXMOX_TOKEN_ID
require_value HADES_PROXMOX_TOKEN_SECRET
require_value HADES_NETBOX_URL
require_value HADES_NETBOX_TOKEN
require_value HADES_UPTIME_KUMA_URL
require_value HADES_UPTIME_KUMA_STATUS_SLUG
require_value HADES_DISCOVERY_ALLOWED_NETWORKS

require_https_url HADES_PROXMOX_URL
require_https_url HADES_NETBOX_URL
require_https_url HADES_UPTIME_KUMA_URL

if [[ -n "${HADES_PROXMOX_URL-}" && "${HADES_PROXMOX_URL}" != */api2/json ]]; then
  printf 'FAIL HADES_PROXMOX_URL must end in /api2/json\n'
  invalid=1
fi
if [[ -n "${HADES_UPTIME_KUMA_STATUS_SLUG-}" &&
      ! "${HADES_UPTIME_KUMA_STATUS_SLUG}" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  printf 'FAIL HADES_UPTIME_KUMA_STATUS_SLUG must be an alphanumeric slug\n'
  invalid=1
fi

if [[ -n "${HADES_DISCOVERY_ALLOWED_NETWORKS-}" ]]; then
  if ! HADES_DISCOVERY_ALLOWED_NETWORKS="$HADES_DISCOVERY_ALLOWED_NETWORKS" python3 - <<'PY'
import ipaddress
import os

networks = [item.strip() for item in os.environ["HADES_DISCOVERY_ALLOWED_NETWORKS"].split(",") if item.strip()]
if not networks:
    raise SystemExit(1)
for value in networks:
    network = ipaddress.ip_network(value, strict=False)
    if network.version != 4 or network.num_addresses > 4096 or network.is_global:
        raise SystemExit(1)
PY
  then
    printf 'FAIL HADES_DISCOVERY_ALLOWED_NETWORKS must contain bounded private IPv4 CIDRs\n'
    invalid=1
  fi
fi

if (( invalid )); then
  exit 1
fi
if (( missing )); then
  printf 'Homelab read-only configuration is incomplete; no network probes were made\n'
  exit 2
fi

printf 'PASS homelab read-only configuration shape\n'
printf 'PASS no network probes performed\n'
