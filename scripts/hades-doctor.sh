#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; test_mode=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; shift 2 ;;
    --test-mode) test_mode=1; shift ;;
    -h|--help) echo 'usage: hades-doctor.sh [--inputs FILE] [--root DIR] [--test-mode]'; exit 0 ;;
    *) echo "FAIL unknown option: $1"; exit 2 ;;
  esac
done
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL version manifest missing'; exit 1; }
[[ -f "$repo_dir/docs/component-manifest.md" ]] || { echo 'FAIL component manifest missing'; exit 1; }
if [[ -n "$inputs" ]]; then
  [[ -f "$inputs" ]] || { echo "FAIL missing operator input file: $inputs"; exit 1; }
  [[ ! -L "$inputs" ]] || { echo 'FAIL operator input file must not be a symlink'; exit 1; }
  source "$inputs"
fi
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
[[ "${HADES_MANIFEST_VERSION:-}" == 1 ]] || { echo 'FAIL unsupported authoritative manifest version; expected version 1'; exit 1; }
if [[ -n "$inputs" ]]; then
  [[ "${HADES_INPUTS_VERSION:-}" == 1 ]] || { echo 'FAIL unsupported operator input contract version; expected version 1'; exit 1; }
  for name in HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_IDENTITY_SECRETS_DIR HADES_DEPLOYMENT_DIR HADES_HERMES_PROFILE; do
    [[ "${!name:-}" == /* ]] || { echo "FAIL operator input path must be absolute: $name"; exit 1; }
  done
fi
export HADES_LLDAP_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE
export HADES_IDENTITY_SECRETS_DIR
compose_cmd=(docker compose)
[[ -n "$inputs" ]] && compose_cmd+=(--env-file "$inputs")
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
if [[ -f "$state" ]]; then
  expected_manifest=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')
  installed_manifest=$(awk -F= '$1 == "manifest" {print $2}' "$state")
  [[ "$installed_manifest" == "$expected_manifest" ]] && echo 'PASS installation marker and manifest' || { echo 'FAIL installation marker manifest is stale'; exit 1; }
else
  echo 'WARN installation marker missing'
fi
config_root="${root%/}${HADES_CONFIG_ROOT:-/etc/hades}"
for file in overlay/sitecustomize.py adapters/grocy-recipe-authoring.py adapters/agent-zero-mcp.py assets/hades-theme.css assets/hades-theme.js; do
  [[ -f "$config_root/$file" ]] && echo "PASS HADES layer $file" || echo "WARN HADES layer missing: $file"
done
[[ -f "$config_root/reconstruction-manifest.json" ]] && echo 'PASS reconstruction manifest' || echo 'WARN reconstruction manifest missing'
if [[ -n "$inputs" && -f "$inputs" ]]; then
  perms=$(stat -c '%a' "$inputs")
  [[ "$perms" == 600 || "$perms" == 640 ]] && echo 'PASS operator-input permissions' || echo "WARN operator-input permissions: $perms"
else echo 'WARN operator-input file not supplied'; fi
if ((test_mode)); then echo 'PASS read-only synthetic doctor'; exit 0; fi
doctor_fail=0
command -v docker >/dev/null 2>&1 && "${compose_cmd[@]}" version >/dev/null 2>&1 && echo 'PASS container runtime available' || echo 'WARN container runtime unavailable'
if command -v docker >/dev/null 2>&1; then
  for container in hades-lldap hades-grocy hades-agent-zero; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
    if [[ "$status" == running ]]; then echo "PASS container $container"; else echo "FAIL container $container state=${status:-missing}"; doctor_fail=1; fi
  done
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' hades-lldap 2>/dev/null || true)
  if [[ "$health" == healthy ]]; then echo 'PASS LLDAP health'; elif [[ -z "$health" ]]; then echo 'WARN LLDAP health=not-configured'; else echo "FAIL LLDAP health=$health"; doctor_fail=1; fi
fi
for f in "$repo_dir"/deploy/*.compose.yaml; do
  if command -v docker >/dev/null 2>&1; then
    if "${compose_cmd[@]}" -f "$f" config --quiet; then echo "PASS compose $(basename "$f")"; else echo "FAIL compose $(basename "$f")"; doctor_fail=1; fi
  fi
done
echo 'WARN live health and exposure checks require the target runtime; no repair was performed'
(( doctor_fail == 0 )) || exit 1
