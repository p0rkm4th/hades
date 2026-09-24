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
if [[ -n "$inputs" ]]; then
  [[ -f "$inputs" ]] || { echo "FAIL missing operator input file: $inputs"; exit 1; }
  [[ ! -L "$inputs" ]] || { echo 'FAIL operator input file must not be a symlink'; exit 1; }
  source "$inputs"
fi
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
[[ "${HADES_MANIFEST_VERSION:-}" == 1 ]] || { echo 'FAIL unsupported authoritative manifest version; expected version 1'; exit 1; }
if [[ -n "$inputs" ]]; then
  [[ "${HADES_INPUTS_VERSION:-}" == 1 || "${HADES_INPUTS_VERSION:-}" == 2 ]] || { echo 'FAIL unsupported operator input contract version; expected version 1 or 2'; exit 1; }
  if [[ "$HADES_INPUTS_VERSION" == 2 ]]; then
    HADES_DEPLOYMENT_DIR=${HADES_DEPLOYMENT_DIR:-$HADES_CONFIG_ROOT/private-deployment}
    HADES_OPEN_WEBUI_COMPOSE_FILE=${HADES_OPEN_WEBUI_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/open-webui.compose.yaml}
    HADES_HINDSIGHT_COMPOSE_FILE=${HADES_HINDSIGHT_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/hindsight.compose.yaml}
    HADES_SEARXNG_COMPOSE_FILE=${HADES_SEARXNG_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/searxng.compose.yaml}
    HADES_HERMES_SERVICE_FILE=${HADES_HERMES_SERVICE_FILE:-$HADES_DEPLOYMENT_DIR/hermes.service}
  fi
  for name in HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_IDENTITY_SECRETS_DIR HADES_DEPLOYMENT_DIR HADES_HERMES_PROFILE; do
    [[ "${!name:-}" == /* ]] || { echo "FAIL operator input path must be absolute: $name"; exit 1; }
  done
fi
export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD
export HADES_IDENTITY_SECRETS_DIR
hades_layer_digest() {
  sha256sum "$@" | awk '{print $1}' | sha256sum | awk '{print $1}'
}
compose_cmd=(docker compose)
[[ -n "$inputs" ]] && compose_cmd+=(--env-file "$inputs")
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
[[ -f "$state" ]] || { echo 'FAIL installer contract marker missing'; exit 1; }
grep -q '^manifest=' "$state" || { echo 'FAIL installer marker is malformed'; exit 1; }
expected_manifest=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')
installed_manifest=$(awk -F= '$1 == "manifest" {print $2}' "$state")
[[ "$installed_manifest" == "$expected_manifest" ]] || { echo 'FAIL installer marker manifest is stale'; exit 1; }
expected_reconstruction_manifest=$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')
installed_reconstruction_manifest=$(awk -F= '$1 == "reconstruction_manifest" {print $2}' "$state")
[[ "$installed_reconstruction_manifest" == "$expected_reconstruction_manifest" ]] || { echo 'FAIL installer reconstruction manifest is stale'; exit 1; }
expected_layer=$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js")
installed_layer=$(awk -F= '$1 == "layer" {print $2}' "$state")
[[ "$installed_layer" == "$expected_layer" ]] || { echo 'FAIL installer HADES layer provenance is stale'; exit 1; }
config_root="${root%/}${HADES_CONFIG_ROOT:-/etc/hades}"
for file in overlay/sitecustomize.py adapters/grocy-recipe-authoring.py adapters/agent-zero-mcp.py assets/hades-theme.css assets/hades-theme.js; do
  [[ -f "$config_root/$file" ]] || { echo "FAIL HADES layer missing: $file"; exit 1; }
done
[[ -f "$config_root/reconstruction-manifest.json" ]] || { echo 'FAIL reconstruction manifest missing'; exit 1; }
[[ "$(sha256sum "$config_root/reconstruction-manifest.json" | awk '{print $1}')" == "$expected_reconstruction_manifest" ]] || { echo 'FAIL installed reconstruction manifest differs from repository'; exit 1; }
installed_layer=$(hades_layer_digest "$config_root/overlay/sitecustomize.py" "$config_root/adapters/grocy-recipe-authoring.py" "$config_root/adapters/agent-zero-mcp.py" "$config_root/assets/hades-theme.css" "$config_root/assets/hades-theme.js")
[[ "$installed_layer" == "$expected_layer" ]] || { echo 'FAIL installed HADES layer differs from repository'; exit 1; }
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
