#!/usr/bin/env bash
set -euo pipefail

# Secret-free regression tests for the credential-independent integration
# preflights. These cases never contact a configured endpoint.

expect_status() {
  local expected=$1 label=$2
  shift 2
  local actual output
  set +e
  output=$("$@" 2>&1)
  actual=$?
  set -e
  [[ "$actual" -eq "$expected" ]] || {
    printf 'FAIL %s: expected exit %s, got %s\n' "$label" "$expected" "$actual"
    printf '%s\n' "$output" >&2
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

expect_status 1 'Home Assistant rejects empty allowlist entry' env \
  HADES_HOME_ASSISTANT_URL=https://ha.example.test \
  HADES_HOME_ASSISTANT_TOKEN=synthetic-token \
  HADES_HOME_ASSISTANT_ENTITY_ALLOWLIST=sensor.temperature, \
  bash scripts/check-home-assistant-readonly-config.sh

private_fixture=$(mktemp -d)
chmod 700 "$private_fixture"
trap 'rm -rf "$private_fixture"' EXIT
printf 'synthetic-pve-a\n' > "$private_fixture/pve-a.token"
printf 'synthetic-pve-b\n' > "$private_fixture/pve-b.token"
printf 'synthetic-netbox\n' > "$private_fixture/netbox.token"
chmod 600 "$private_fixture"/*.token

homelab_env=(
  HADES_PROXMOX_RESOURCES_URLS=https://pve-a.example.test:8006/api2/json/cluster/resources,https://pve-b.example.test:8006/api2/json/cluster/resources
  HADES_PROXMOX_TOKEN_IDS=svc-hades-ro@pve\!a,svc-hades-ro@pve\!b
  HADES_PROXMOX_TOKEN_FILES="$private_fixture/pve-a.token,$private_fixture/pve-b.token"
  HADES_NETBOX_URL=https://netbox.example.test
  HADES_NETBOX_TOKEN_FILE="$private_fixture/netbox.token"
  HADES_DISCOVERY_ALLOWED_NETWORKS=192.0.2.0/24
  HADES_UPTIME_KUMA_URL=https://status.example.test
  HADES_UPTIME_KUMA_STATUS_SLUG=hades-status
)

expect_status 0 'homelab accepts multi-source protected token files' env \
  "${homelab_env[@]}" bash scripts/check-homelab-readonly-config.sh

expect_status 1 'homelab rejects mismatched Proxmox token counts' env \
  "${homelab_env[@]}" \
  HADES_PROXMOX_TOKEN_IDS=svc-hades-ro@pve\!a,svc-hades-ro@pve\!b,svc-hades-ro@pve\!c \
  bash scripts/check-homelab-readonly-config.sh

chmod 644 "$private_fixture/netbox.token"
expect_status 1 'homelab rejects unsafe token file permissions' env \
  "${homelab_env[@]}" bash scripts/check-homelab-readonly-config.sh
chmod 600 "$private_fixture/netbox.token"

expect_status 1 'homelab rejects legacy inline credentials' env \
  "${homelab_env[@]}" \
  HADES_NETBOX_TOKEN=synthetic-inline-token \
  bash scripts/check-homelab-readonly-config.sh

redaction_output=$(env "${homelab_env[@]}" \
  HADES_NETBOX_TOKEN=synthetic-inline-token \
  bash scripts/check-homelab-readonly-config.sh 2>&1 || true)
[[ "$redaction_output" != *synthetic-inline-token* ]] || {
  echo 'FAIL homelab preflight leaked an inline credential' >&2
  exit 1
}
echo 'PASS homelab preflight does not echo credentials'

expect_status 1 'homelab rejects malformed status slug' env \
  "${homelab_env[@]}" \
  HADES_UPTIME_KUMA_STATUS_SLUG=bad/slug \
  bash scripts/check-homelab-readonly-config.sh

expect_status 2 'homelab reports missing protected source inputs' env -i \
  PATH="$PATH" bash scripts/check-homelab-readonly-config.sh

printf 'Readonly configuration shape regressions passed\n'
