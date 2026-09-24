#!/usr/bin/env bash
set -Eeuo pipefail

# Read-only post-cutover verifier. It proves the final migration invariant but
# never performs the cutover, stops services, removes containers, or deletes data.

record=${1:?usage: verify-production-cutover-complete.sh ACCEPTANCE_RECORD}
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
default_infra_repo=$(cd "$repo_dir/../hades-infra" 2>/dev/null && pwd || true)
destination_ip=${HADES_DESTINATION_IP:?HADES_DESTINATION_IP is required}
destination_ssh=${HADES_DESTINATION_SSH:?HADES_DESTINATION_SSH is required}
expected_guest=${HADES_DESTINATION_HOSTNAME:-hades-core}
dns_name=${HADES_CUTOVER_NAME:-hades.local}
webui_port=${HADES_WEBUI_PORT:-3000}
rollback_host=${HADES_ROLLBACK_HOST:?HADES_ROLLBACK_HOST is required}
rollback_package_root=${HADES_ROLLBACK_PACKAGE_ROOT:-/srv/hades-backups}
rollback_root=${HADES_ROLLBACK_ROOT:-/srv/hades-backups/manifests/migration-20260916}
hindsight_rollback_root=${HADES_HINDSIGHT_ROLLBACK_ROOT:-/srv/hades-backups/hindsight}
rollback_manifest=${HADES_ROLLBACK_MANIFEST:-${default_infra_repo:+$default_infra_repo/migrations/rollback-manifest.yaml}}
hades_repo=${HADES_REPO_DIR:-$repo_dir}
infra_repo=${HADES_INFRA_REPO_DIR:-$default_infra_repo}
cleanup_record=${HADES_LAPTOP_CLEANUP_RECORD:?HADES_LAPTOP_CLEANUP_RECORD is required}

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

check_acceptance() {
  "$repo_dir/scripts/validate-destination-owner-acceptance.sh" "$record"
}

check_destination_identity() {
  local identity
  identity=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "$destination_ssh" \
    'hostname -s' 2>/dev/null) || return 1
  [[ "$identity" == "$expected_guest" ]]
}

check_authoritative_destination() {
  getent ahostsv4 "$dns_name" | awk -v ip="$destination_ip" '$1 == ip { found = 1 } END { exit(found ? 0 : 1) }' || return 1
  curl -fsS --connect-timeout 3 --max-time 10 "http://${dns_name}:${webui_port}/health" >/dev/null
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

check_source_service_stopped() {
  command -v systemctl >/dev/null 2>&1 || return 1
  local user_enabled system_enabled
  user_enabled=$(systemctl --user is-enabled hades-hermes.service 2>/dev/null || true)
  system_enabled=$(systemctl is-enabled hades-hermes.service 2>/dev/null || true)
  [[ -n "$user_enabled" && -n "$system_enabled" ]] || return 1
  [[ "$user_enabled" != enabled && "$user_enabled" != enabled-runtime && "$user_enabled" != alias ]] || return 1
  [[ "$system_enabled" != enabled && "$system_enabled" != enabled-runtime && "$system_enabled" != alias ]] || return 1
  ! systemctl --user is-active --quiet hades-hermes.service 2>/dev/null \
    && ! systemctl is-active --quiet hades-hermes.service 2>/dev/null
}

check_source_containers_absent() {
  command -v docker >/dev/null 2>&1 || return 1
  local names name
  names=$(docker ps -a --format '{{.Names}}') || return 1
  for name in hades-open-webui hades-hindsight hades-grocy hades-agent-zero hades-searxng hades-lldap-production; do
    ! grep -Fxq "$name" <<<"$names" || return 1
  done
}

check_laptop_cleanup_record() {
  "$repo_dir/scripts/validate-laptop-decommission-record.sh" "$cleanup_record"
}

check_development_checkouts_preserved() {
  [[ -d "$hades_repo/.git" && -d "$infra_repo/.git" ]]
}

check 'real destination acceptance record' check_acceptance
check 'destination SSH identity is the expected homelab guest' check_destination_identity
check 'authoritative hades.local reaches destination health' check_authoritative_destination
check 'independent rollback package remains protected and verifiable' check_rollback_package
check 'protected Hindsight production export remains verified' check_hindsight_export
check 'rollback manifest has complete required component coverage' check_complete_rollback_manifest
check 'laptop Hermes production service is stopped and disabled from runtime' check_source_service_stopped
check 'laptop production containers are absent' check_source_containers_absent
check 'laptop cleanup evidence is complete and secret-free' check_laptop_cleanup_record
check 'development and infrastructure checkouts remain preserved' check_development_checkouts_preserved

printf 'SUMMARY pass=%d fail=%d\n' "$pass" "$fail"
if (( fail > 0 )); then
  printf 'Post-cutover invariant is not proven; this verifier made no changes.\n' >&2
  exit 1
fi
printf 'PASS production HADES is homelab-hosted and laptop production is absent\n'
