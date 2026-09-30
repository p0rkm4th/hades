#!/usr/bin/env bash
set -Eeuo pipefail

# Read-only gate for the final laptop -> homelab cutover. This script never changes DNS,
# authenticates an owner account, stops services, or deletes data.
# It is intentionally usable before owner acceptance and again immediately
# before the authorized cutover.

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
infra_repo_dir=$(cd "$repo_dir/../hades-infra" 2>/dev/null && pwd || true)
destination_ip=${HADES_DESTINATION_IP:?HADES_DESTINATION_IP is required}
destination_ssh=${HADES_DESTINATION_SSH:?HADES_DESTINATION_SSH is required}
dns_name=${HADES_CUTOVER_NAME:-hades.local}
webui_port=${HADES_WEBUI_PORT:-3000}
rollback_host=${HADES_ROLLBACK_HOST:?HADES_ROLLBACK_HOST is required}
rollback_package_root=${HADES_ROLLBACK_PACKAGE_ROOT:-/srv/hades-backups}
rollback_root=${HADES_ROLLBACK_ROOT:-/srv/hades-backups/manifests/migration-20260916}
hindsight_rollback_root=${HADES_HINDSIGHT_ROLLBACK_ROOT:-/srv/hades-backups/hindsight}
rollback_manifest=${HADES_ROLLBACK_MANIFEST:-${infra_repo_dir:+$infra_repo_dir/migrations/rollback-manifest.yaml}}
expected_vm_id=${HADES_DESTINATION_VMID:-802}
expected_guest=${HADES_DESTINATION_HOSTNAME:-hades-core}
expected_source_revision=${HADES_DESTINATION_SOURCE_REVISION:?HADES_DESTINATION_SOURCE_REVISION is required}
destination_repo=${HADES_DESTINATION_REPO:?HADES_DESTINATION_REPO is required}
proxmox_host=${HADES_PROXMOX_HOST:?HADES_PROXMOX_HOST is required}

pass=0
fail=0
check() {
  local label=$1
  shift
  if "$@"; then
    printf 'PASS %s\n' "$label"
    pass=$((pass + 1))
  else
    printf 'FAIL %s\n' "$label"
    fail=$((fail + 1))
  fi
}

check_destination_identity() {
  local identity
  identity=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
    sh -s -- "$destination_repo" <<'REMOTE_IDENTITY'
set -eu
repo=$1
printf '%s|%s|%s\n' \
  "$(hostname -s)" \
  "$(systemctl is-active hades-hermes.service)" \
  "$(systemctl show -p WorkingDirectory --value hades-hermes.service)"
REMOTE_IDENTITY
    2>/dev/null) || return 1
  [[ "$identity" == "$expected_guest|active|$destination_repo" ]]
}

check_destination_source() {
  "$repo_dir/scripts/verify-destination-source.sh" \
    "$destination_ssh" "$destination_repo" "$expected_source_revision"
}

check_destination_runtime() {
  local names
  names=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
    "docker ps --format '{{.Names}}|{{.Status}}'" 2>/dev/null) || return 1
  local required
  for required in hades-open-webui hades-lldap hades-hindsight hades-grocy hades-searxng hades-agent-zero; do
    grep -Eq "^${required}\|Up( |$)" <<<"$names" || return 1
  done
}

check_vm_persistence() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$proxmox_host" \
    "test \"\$(qm config \"$expected_vm_id\" | sed -n 's/^onboot: //p')\" = 1"
}

check_webui_health() {
  curl -fsS --connect-timeout 3 --max-time 10 \
    "http://${destination_ip}:${webui_port}/health" >/dev/null
}

check_resolved_cutover_path() {
  curl -fsS --connect-timeout 3 --max-time 10 \
    --resolve "${dns_name}:${webui_port}:${destination_ip}" \
    "http://${dns_name}:${webui_port}/health" >/dev/null
}

check_authoritative_name() {
  getent ahostsv4 "$dns_name" | awk -v ip="$destination_ip" '$1 == ip { found = 1 } END { exit(found ? 0 : 1) }'
}

check_rollback_package() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$rollback_host" \
    sh -s -- "$rollback_package_root" "$rollback_root" <<'REMOTE_ROLLBACK'
set -eu
package_root=$1
rollback_root=$2
test -d "$package_root"
test -s "$package_root/SHA256SUMS"
cd "$package_root"
sha256sum -c SHA256SUMS >/dev/null
test -d "$rollback_root"
test -s "$rollback_root/repositories/SHA256SUMS"
cd "$rollback_root/repositories"
sha256sum -c SHA256SUMS >/dev/null
! find "$package_root" -path "$package_root/rehearsals" -prune -o -type f -perm /077 -print -quit | grep -q .
! find "$package_root" -path "$package_root/rehearsals" -prune -o -type d -perm /077 -print -quit | grep -q .
! find "$package_root" -path "$package_root/rehearsals" -prune -o -type l -print -quit | grep -q .
REMOTE_ROLLBACK
}

check_hindsight_export() {
  ssh -o BatchMode=yes -o ConnectTimeout=5 "$rollback_host" \
    sh -s -- "$hindsight_rollback_root" <<'REMOTE_HINDSIGHT'
set -eu
root=$1
found=1
for archive in $(find "$root" -type f -name '*.dump' -size +0c -print); do
  sidecar="${archive}.SHA256SUM"
  if test -s "$sidecar" && (cd "$(dirname "$archive")" && sha256sum -c "$(basename "$sidecar")" >/dev/null); then
    found=0
    break
  fi
done
test "$found" -eq 0
REMOTE_HINDSIGHT
}

check_complete_rollback_manifest() {
  [[ -f "$rollback_manifest" ]] || return 1
  ruby -ryaml -e '
    data = YAML.safe_load(File.read(ARGV.fetch(0)), permitted_classes: [], aliases: false)
    required = %w[Open\ WebUI LLDAP Hindsight Grocy Hermes Agent\ Zero SearXNG deployment\ manifests]
    complete = %w[CAPTURED_CHECKSUM_VERIFIED VERIFIED_GIT_BUNDLES VERIFIED_NONEMPTY_RESTORE_SHAPE VERIFIED_NONEMPTY_FORMAT]
    encryption_pending_allowed = %w[LLDAP Agent\ Zero]
    artifacts = data.fetch("artifacts").to_h { |row| [row.fetch("component"), row.fetch("status")] }
    pending = required.select { |component| artifacts[component] == "CAPTURED_PROTECTED_ENCRYPTION_PENDING" }
    missing = required.reject do |component|
      complete.include?(artifacts[component]) ||
        (encryption_pending_allowed.include?(component) && artifacts[component] == "CAPTURED_PROTECTED_ENCRYPTION_PENDING")
    end
    abort "incomplete rollback components: #{missing.join(", ")}" unless missing.empty?
    warn "NOTE encrypted custody remains pending: #{pending.join(", ")}" unless pending.empty?
  ' "$rollback_manifest"
}

check_source_runtime_preserved() {
  systemctl --user is-active --quiet hades-hermes.service 2>/dev/null \
    || systemctl is-active --quiet hades-hermes.service 2>/dev/null \
    || return 1
  local names
  names=$(docker ps --format '{{.Names}}' 2>/dev/null) || return 1
  grep -Fxq hades-open-webui <<<"$names"
}

check 'destination identity, Hermes, and active service source' check_destination_identity
check 'destination source revision and cleanliness' check_destination_source
check 'destination application containers' check_destination_runtime
check 'destination VM onboot persistence' check_vm_persistence
check 'destination WebUI LAN health' check_webui_health
check 'hades.local simulated destination path' check_resolved_cutover_path
check 'authoritative hades.local points to destination' check_authoritative_name
check 'independent rollback package is present and protected' check_rollback_package
check 'protected Hindsight production export is present and verified' check_hindsight_export
check 'rollback manifest has complete required component coverage' check_complete_rollback_manifest
check 'laptop source runtime remains preserved' check_source_runtime_preserved

printf 'SUMMARY pass=%d fail=%d\n' "$pass" "$fail"
if (( fail > 0 )); then
  printf 'Cutover remains blocked; this preflight made no changes.\n' >&2
  exit 1
fi
printf 'Preflight complete; owner acceptance and explicit cutover authorization are still required.\n'
