#!/usr/bin/env bash
set -Eeuo pipefail

# Bounded, one-component upgrade helper. It never edits version pins; the
# operator changes the authoritative manifest first and keeps the prior copy
# as the rollback artifact.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
component=''; inputs=''; backup_dir=''; apply=0
usage() {
  cat <<'EOF'
usage: upgrade-hades.sh --component {hermes|open-webui|hindsight|grocy|lldap|searxng|agent-zero} --inputs FILE
                        --backup-dir DIR [--apply]

Without --apply, validate the requested bounded upgrade and print its plan.
With --apply, require HADES_UPGRADE_BACKUP_VERIFIED=1 and perform one tracked
Compose pull/up after installer preflight. Hermes, Open WebUI, Hindsight, and
SearXNG are plan-only because their private operator records require their own
acceptance workflow.
EOF
}
while (($#)); do
  case "$1" in
    --component) component=${2:?--component needs a value}; shift 2 ;;
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --backup-dir) backup_dir=${2:?--backup-dir needs a directory}; shift 2 ;;
    --apply) apply=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
fail() { echo "FAIL $*" >&2; exit 1; }
[[ "$component" =~ ^(hermes|open-webui|hindsight|grocy|lldap|searxng|agent-zero)$ ]] || fail 'component is not in the bounded upgrade map'
[[ -f "$inputs" && ! -L "$inputs" ]] || fail 'operator input file is missing or linked'
[[ -d "$backup_dir" && ! -L "$backup_dir" ]] || fail 'backup directory must already exist and not be a symlink'
[[ "$(stat -c '%a' "$backup_dir")" == 700 ]] || fail 'backup directory must be mode 0700'
[[ -f "$repo_dir/config/versions.env" ]] || fail 'authoritative version manifest is missing'
source "$inputs"
source "$repo_dir/config/versions.env"
export HADES_LLDAP_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE
case "$component" in
  lldap) compose_file="$repo_dir/deploy/lldap.compose.yaml"; container=hades-lldap ;;
  grocy) compose_file="$repo_dir/deploy/grocy.compose.yaml"; container=hades-grocy ;;
  agent-zero) compose_file="$repo_dir/deploy/agent-zero.compose.yaml"; container=hades-agent-zero ;;
  hermes) private_record='private Hermes package/deployment record' ;;
  open-webui) private_record='private Open WebUI immutable artifact/deployment record' ;;
  hindsight) private_record='private Hindsight image/deployment record' ;;
  searxng) private_record='private SearXNG image/deployment record' ;;
esac
if [[ -n "${private_record:-}" ]]; then
  echo "PLAN one-component upgrade: $component"
  echo "PLAN source: $repo_dir/config/versions.env plus $private_record"
  echo 'PLAN required sequence: verified backup -> installer preflight -> private-record validation -> restart -> health -> doctor -> validate -> rollback retention -> owner acceptance'
  ((apply)) && fail "$component is plan-only; use its private operator record and acceptance workflow"
  exit 0
fi
[[ -f "$compose_file" ]] || fail "tracked Compose record missing: $compose_file"
echo "PLAN one-component upgrade: $component"
echo "PLAN source: config/versions.env plus $compose_file"
echo 'PLAN required sequence: verified backup -> installer preflight -> pull/up -> health -> doctor -> validate -> rollback retention'
((apply)) || exit 0

[[ $EUID -eq 0 ]] || fail '--apply must run as root'
[[ "${HADES_UPGRADE_BACKUP_VERIFIED:-0}" == 1 ]] || fail '--apply requires HADES_UPGRADE_BACKUP_VERIFIED=1'
command -v docker >/dev/null 2>&1 || fail 'docker is required for --apply'
bash "$repo_dir/scripts/install-hades.sh" --preflight --inputs "$inputs"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="$backup_dir/${component}-${stamp}"
install -m 0600 "$compose_file" "$backup.compose.yaml"
install -m 0600 "$repo_dir/config/versions.env" "$backup.versions.env"
sha256sum "$backup.compose.yaml" "$backup.versions.env" > "$backup.SHA256SUMS"
compose_cmd=(docker compose --env-file "$inputs")
"${compose_cmd[@]}" -f "$compose_file" config --quiet || fail "invalid $component Compose configuration"
"${compose_cmd[@]}" -f "$compose_file" pull || fail "$component image pull failed; prior runtime remains available"
"${compose_cmd[@]}" -f "$compose_file" up -d || fail "$component restart failed; inspect runtime and use the retained rollback artifacts"
status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
[[ "$status" == running ]] || fail "$component did not return to running state: ${status:-missing}"
echo "PASS $component upgraded and running; retained rollback artifacts at $backup.*"
