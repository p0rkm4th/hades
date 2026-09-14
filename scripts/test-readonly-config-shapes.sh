#!/usr/bin/env bash
set -euo pipefail

# Secret-free regression tests for the credential-independent integration
# preflights. These cases never contact a configured endpoint.

expect_status() {
  local expected=$1 label=$2
  shift 2
  local actual
  set +e
  "$@" >/tmp/hades-readonly-config-test.out 2>&1
  actual=$?
  set -e
  [[ "$actual" -eq "$expected" ]] || {
    printf 'FAIL %s: expected exit %s, got %s\n' "$label" "$expected" "$actual"
    sed -n '1,20p' /tmp/hades-readonly-config-test.out >&2
    exit 1
  }
  printf 'PASS %s\n' "$label"
}

expect_status 0 'Home Assistant accepts benign indoor sensor' env \
  HADES_HOME_ASSISTANT_URL=https://ha.example.test \
  HADES_HOME_ASSISTANT_TOKEN=synthetic-token \
  HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST=sensor.indoor_temperature,climate.living_room \
  bash scripts/check-home-assistant-readonly-config.sh

expect_status 1 'Home Assistant rejects security entity' env \
  HADES_HOME_ASSISTANT_URL=https://ha.example.test \
  HADES_HOME_ASSISTANT_TOKEN=synthetic-token \
  HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST=lock.front_door \
  bash scripts/check-home-assistant-readonly-config.sh

expect_status 1 'Home Assistant rejects malformed entity' env \
  HADES_HOME_ASSISTANT_URL=https://ha.example.test \
  HADES_HOME_ASSISTANT_TOKEN=synthetic-token \
  HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST=sensor.bad-name \
  bash scripts/check-home-assistant-readonly-config.sh

expect_status 0 'homelab accepts bounded status slug' env \
  HADES_PROXMOX_URL=https://proxmox.example.test:8006/api2/json \
  HADES_PROXMOX_TOKEN_ID=svc-hades-ro@pve\!readonly \
  HADES_PROXMOX_TOKEN_SECRET=synthetic-secret \
  HADES_NETBOX_URL=https://netbox.example.test \
  HADES_NETBOX_TOKEN=synthetic-token \
  HADES_UPTIME_KUMA_URL=https://status.example.test \
  HADES_UPTIME_KUMA_STATUS_SLUG=hades-status \
  bash scripts/check-homelab-readonly-config.sh

expect_status 1 'homelab rejects malformed status slug' env \
  HADES_PROXMOX_URL=https://proxmox.example.test:8006/api2/json \
  HADES_PROXMOX_TOKEN_ID=svc-hades-ro@pve\!readonly \
  HADES_PROXMOX_TOKEN_SECRET=synthetic-secret \
  HADES_NETBOX_URL=https://netbox.example.test \
  HADES_NETBOX_TOKEN=synthetic-token \
  HADES_UPTIME_KUMA_URL=https://status.example.test \
  HADES_UPTIME_KUMA_STATUS_SLUG=bad/slug \
  bash scripts/check-homelab-readonly-config.sh

printf 'Readonly configuration shape regressions passed\n'
