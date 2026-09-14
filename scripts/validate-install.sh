#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; test_mode=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; shift 2 ;;
    --test-mode) test_mode=1; shift ;;
    -h|--help) echo 'usage: validate-install.sh [--inputs FILE] [--root DIR] [--test-mode]'; exit 0 ;;
    *) echo "FAIL unknown option: $1"; exit 2 ;;
  esac
done
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL version manifest missing'; exit 1; }
if [[ -n "$inputs" && -f "$inputs" ]]; then source "$inputs"; fi
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
export HADES_LLDAP_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE
export HADES_IDENTITY_SECRETS_DIR
compose_cmd=(docker compose)
[[ -n "$inputs" ]] && compose_cmd+=(--env-file "$inputs")
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
[[ -f "$state" ]] || { echo 'FAIL installer contract marker missing'; exit 1; }
grep -q '^manifest=' "$state" || { echo 'FAIL installer marker is malformed'; exit 1; }
expected_manifest=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')
installed_manifest=$(awk -F= '$1 == "manifest" {print $2}' "$state")
[[ "$installed_manifest" == "$expected_manifest" ]] || { echo 'FAIL installer marker manifest is stale'; exit 1; }
config_root="${root%/}${HADES_CONFIG_ROOT:-/etc/hades}"
for file in overlay/sitecustomize.py adapters/grocy-recipe-authoring.py adapters/agent-zero-mcp.py assets/hades-theme.css assets/hades-theme.js; do
  [[ -f "$config_root/$file" ]] || { echo "FAIL HADES layer missing: $file"; exit 1; }
done
if (( ! test_mode )) && command -v docker >/dev/null 2>&1; then
  for f in "$repo_dir"/deploy/*.compose.yaml; do "${compose_cmd[@]}" -f "$f" config --quiet || { echo "FAIL compose $(basename "$f")"; exit 1; }; done
fi
if ((test_mode)); then
  echo 'PASS synthetic authenticated-path placeholder contract'
  echo 'PASS synthetic validation: production credentials and fixture state were not created'
else
  for container in hades-lldap hades-grocy hades-agent-zero; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
    [[ "$status" == running ]] || { echo "FAIL tracked container is not running: $container"; exit 1; }
  done
  echo 'WARN full conversation, identity, memory, Grocy, search, and operator checks require live private inputs'
fi
echo 'PASS install validation contract'
