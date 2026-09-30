#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; test_mode=0; synthetic_deployment_test=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; shift 2 ;;
    --test-mode) test_mode=1; shift ;;
    --synthetic-deployment-test) synthetic_deployment_test=1; shift ;;
    -h|--help) echo 'usage: validate-install.sh [--inputs FILE] [--root DIR] [--test-mode | --synthetic-deployment-test]'; exit 0 ;;
    *) echo "FAIL unknown option: $1"; exit 2 ;;
  esac
done
if ((synthetic_deployment_test && test_mode)); then echo 'FAIL full synthetic deployment validation cannot be combined with --test-mode' >&2; exit 2; fi
if ((synthetic_deployment_test)) && [[ "$root" != / ]]; then echo 'FAIL --synthetic-deployment-test validates the authorized machine root only' >&2; exit 2; fi
if ((synthetic_deployment_test)) && [[ -z "$inputs" ]]; then echo 'FAIL --synthetic-deployment-test requires explicit synthetic inputs' >&2; exit 2; fi
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL version manifest missing'; exit 1; }
if [[ -n "$inputs" ]]; then
  [[ -f "$inputs" ]] || { echo "FAIL missing operator input file: $inputs"; exit 1; }
  [[ ! -L "$inputs" ]] || { echo 'FAIL operator input file must not be a symlink'; exit 1; }
  source "$inputs"
fi
HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=${HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED:-false}
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
[[ "${HADES_MANIFEST_VERSION:-}" == 1 ]] || { echo 'FAIL unsupported authoritative manifest version; expected version 1'; exit 1; }
if [[ -n "$inputs" ]]; then
  [[ "${HADES_INPUTS_VERSION:-}" == 1 || "${HADES_INPUTS_VERSION:-}" == 2 ]] || { echo 'FAIL unsupported operator input contract version; expected version 1 or 2'; exit 1; }
  if [[ "${HADES_SYNTHETIC_FIXTURE:-false}" == true && "$test_mode" != 1 ]]; then
    if (( ! synthetic_deployment_test )); then
      echo 'FAIL synthetic fixture inputs are test-only and cannot validate a production installation' >&2; exit 1
    fi
    bash "$repo_dir/scripts/synthetic-deployment-target.sh" verify
    [[ "${HADES_INPUTS_VERSION:-}" == 2 ]] || { echo 'FAIL full synthetic deployment validation requires operator input contract v2' >&2; exit 1; }
  elif ((synthetic_deployment_test)); then
    echo 'FAIL --synthetic-deployment-test requires HADES_SYNTHETIC_FIXTURE=true inputs' >&2; exit 1
  fi
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
export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD HADES_NGINX_IMAGE
export HADES_IDENTITY_SECRETS_DIR
hades_layer_digest() {
  sha256sum "$@" | awk '{print $1}' | sha256sum | awk '{print $1}'
}
compose_cmd=(docker compose)
[[ -n "$inputs" ]] && compose_cmd+=(--env-file "$inputs")
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
  proxy_env="${HADES_DEPLOYMENT_DIR:-${HADES_CONFIG_ROOT:-/etc/hades}/private-deployment}/agent-zero-operator-proxy.env"
  [[ -f "$proxy_env" && ! -L "$proxy_env" && "$(stat -c '%a' "$proxy_env")" == 600 ]] || { echo 'FAIL Agent Zero Operator proxy environment record missing or unsafe'; exit 1; }
  compose_cmd+=(--env-file "$proxy_env")
fi
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
[[ -f "$state" ]] || { echo 'FAIL installer contract marker missing'; exit 1; }
if ((synthetic_deployment_test)); then
  grep -Fxq 'synthetic_deployment_test=true' "$state" || { echo 'FAIL install marker does not identify a synthetic test deployment'; exit 1; }
  echo 'WARN validating test-only synthetic identities on an explicitly authorized machine'
elif grep -Fxq 'synthetic_deployment_test=true' "$state"; then
  echo 'FAIL synthetic deployment requires explicit --synthetic-deployment-test and target authorization' >&2; exit 1
fi
grep -q '^manifest=' "$state" || { echo 'FAIL installer marker is malformed'; exit 1; }
expected_manifest=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')
installed_manifest=$(awk -F= '$1 == "manifest" {print $2}' "$state")
[[ "$installed_manifest" == "$expected_manifest" ]] || { echo 'FAIL installer marker manifest is stale'; exit 1; }
installed_source_revision=$(awk -F= '$1 == "source_revision" {print $2}' "$state")
installed_source_tree=$(awk -F= '$1 == "source_tree" {print $2}' "$state")
if [[ -z "$installed_source_revision" ]]; then
  echo 'WARN installation source revision is unavailable'
elif [[ "$installed_source_revision" == archive ]]; then
  ((test_mode)) || { echo 'FAIL production install marker has no Git source revision'; exit 1; }
  echo 'WARN synthetic install source has no Git revision'
else
  current_source_revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse --verify HEAD 2>/dev/null || true)
  current_source_tree=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse 'HEAD^{tree}' 2>/dev/null || true)
  [[ "$installed_source_revision" == "$current_source_revision" && -n "$current_source_tree" && "$installed_source_tree" == "$current_source_tree" ]] || {
    echo 'FAIL installation source revision or tree is stale'; exit 1;
  }
  echo 'PASS installation source revision and tree'
fi
expected_reconstruction_manifest=$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')
installed_reconstruction_manifest=$(awk -F= '$1 == "reconstruction_manifest" {print $2}' "$state")
[[ "$installed_reconstruction_manifest" == "$expected_reconstruction_manifest" ]] || { echo 'FAIL installer reconstruction manifest is stale'; exit 1; }
expected_layer=$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/grocy-mcp/launch.py" "$repo_dir/integrations/grocy-mcp/requirements.lock" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js" "$repo_dir/webui/finance-upload.js" "$repo_dir/webui/receipt-upload.js")
installed_layer=$(awk -F= '$1 == "layer" {print $2}' "$state")
[[ "$installed_layer" == "$expected_layer" ]] || { echo 'FAIL installer HADES layer provenance is stale'; exit 1; }
config_root="${root%/}${HADES_CONFIG_ROOT:-/etc/hades}"
owner_policy_record="${root%/}${HADES_DEPLOYMENT_DIR:-${HADES_CONFIG_ROOT:-/etc/hades}/private-deployment}/hades-owner-policy.env"
if [[ -n "${HADES_OWNER_SUBJECT_IDS:-}" ]]; then
  owner_policy_stat=$(stat -c '%u:%g:%a' "$owner_policy_record" 2>/dev/null || true)
  expected_gid=$(getent group "${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}" | cut -d: -f3)
  [[ -f "$owner_policy_record" && ! -L "$owner_policy_record" && "$owner_policy_stat" == "0:$expected_gid:640" && "$(wc -l < "$owner_policy_record")" == 1 ]] || { echo 'FAIL explicit owner subject policy record is missing or unsafe'; exit 1; }
  grep -Fxq "HADES_OWNER_SUBJECT_IDS=$HADES_OWNER_SUBJECT_IDS" "$owner_policy_record" || { echo 'FAIL explicit owner subject policy record is stale'; exit 1; }
else
  [[ ! -e "$owner_policy_record" && ! -L "$owner_policy_record" ]] || { echo 'FAIL unexpected owner subject policy record exists while the input is empty'; exit 1; }
fi
for file in overlay/sitecustomize.py adapters/grocy-mcp-launch.py adapters/grocy-recipe-authoring.py adapters/agent-zero-mcp.py assets/hades-theme.css assets/hades-theme.js assets/finance-upload.js assets/receipt-upload.js; do
  [[ -f "$config_root/$file" ]] || { echo "FAIL HADES layer missing: $file"; exit 1; }
done
[[ -f "$config_root/reconstruction-manifest.json" ]] || { echo 'FAIL reconstruction manifest missing'; exit 1; }
[[ "$(sha256sum "$config_root/reconstruction-manifest.json" | awk '{print $1}')" == "$expected_reconstruction_manifest" ]] || { echo 'FAIL installed reconstruction manifest differs from repository'; exit 1; }
installed_layer=$(hades_layer_digest "$config_root/overlay/sitecustomize.py" "$config_root/adapters/grocy-mcp-launch.py" "$repo_dir/integrations/grocy-mcp/requirements.lock" "$config_root/adapters/grocy-recipe-authoring.py" "$config_root/adapters/agent-zero-mcp.py" "$config_root/assets/hades-theme.css" "$config_root/assets/hades-theme.js" "$config_root/assets/finance-upload.js" "$config_root/assets/receipt-upload.js")
[[ "$installed_layer" == "$expected_layer" ]] || { echo 'FAIL installed HADES layer differs from repository'; exit 1; }
if (( ! test_mode )) && command -v docker >/dev/null 2>&1; then
  for f in "$repo_dir"/deploy/*.compose.yaml; do "${compose_cmd[@]}" -f "$f" config --quiet || { echo "FAIL compose $(basename "$f")"; exit 1; }; done
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    proxy_compose="$HADES_DEPLOYMENT_DIR/agent-zero-operator-proxy.compose.yaml"
    [[ -f "$proxy_compose" && ! -L "$proxy_compose" && "$(stat -c '%a' "$proxy_compose")" == 600 ]] || { echo 'FAIL Agent Zero Operator proxy Compose record missing or unsafe'; exit 1; }
    "${compose_cmd[@]}" -f "$proxy_compose" config --quiet || { echo 'FAIL Agent Zero Operator proxy Compose'; exit 1; }
    systemctl is-active --quiet hades-agent-zero-operator-auth.service || { echo 'FAIL Agent Zero Operator auth service is inactive'; exit 1; }
    docker inspect -f '{{.State.Status}}' hades-agent-zero-operator-proxy 2>/dev/null | grep -Fxq running || { echo 'FAIL Agent Zero Operator proxy is not running'; exit 1; }
  fi
fi
if ((test_mode)); then
  echo 'PASS synthetic authenticated-path placeholder contract'
  echo 'PASS synthetic validation: production credentials and fixture state were not created'
else
  for container in hades-lldap hades-grocy hades-agent-zero; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
    [[ "$status" == running ]] || { echo "FAIL tracked container is not running: $container"; exit 1; }
  done
  agent_zero_workspace_env_mode=$(docker exec --user 0 hades-agent-zero stat -c '%a' /a0/usr/.env 2>/dev/null || true)
  [[ "$agent_zero_workspace_env_mode" == 600 ]] || { echo 'FAIL Agent Zero private workspace environment file is missing or not mode 0600'; exit 1; }
  systemctl is-active --quiet hades-hermes.service || { echo 'FAIL Hermes gateway service is inactive'; exit 1; }
  runtime_user=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
  runtime_group=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
  if ! id "$runtime_user" >/dev/null 2>&1 || [[ "$(id -gn "$runtime_user")" != "$runtime_group" ]]; then
    echo 'FAIL Hermes service identity is missing or mismatched'
    exit 1
  fi
  runuser -u "$runtime_user" -- test -r "$HADES_HERMES_PROFILE/hermes.env" &&
    runuser -u "$runtime_user" -- test -r "$HADES_HERMES_PROFILE/config.yaml" || {
      echo 'FAIL Hermes runtime cannot read its profile'
      exit 1
    }
  grocy_mcp_prefix=/opt/hades-grocy-mcp
  grocy_mcp_python="$grocy_mcp_prefix/venv/bin/python"
  grocy_mcp_bin="$grocy_mcp_prefix/venv/bin/grocy-mcp"
  [[ -x "$grocy_mcp_python" && -x "$grocy_mcp_bin" ]] || { echo 'FAIL pinned Grocy MCP runtime is missing'; exit 1; }
  "$grocy_mcp_python" -c 'import importlib.metadata as m,sys; sys.exit(0 if m.version("grocy-mcp")==sys.argv[1] else 1)' "$HADES_GROCY_MCP_VERSION" || { echo 'FAIL Grocy MCP runtime version differs from manifest'; exit 1; }
  python3 "$repo_dir/scripts/check-hermes-profile-contract.py" "$HADES_HERMES_PROFILE/config.yaml" || {
    echo 'FAIL Hermes profile lacks a required V1 MCP registration or profile classification'
    exit 1
  }
  runtime_grocy_key="$HADES_CONFIG_ROOT/secrets/grocy-api-key"
  [[ -f "$runtime_grocy_key" && ! -L "$runtime_grocy_key" && "$(stat -c '%a' "$runtime_grocy_key")" == 640 ]] || { echo 'FAIL protected Hermes-readable Grocy API key is missing or unsafe'; exit 1; }
  runuser -u "$runtime_user" -- test -r "$runtime_grocy_key" || { echo 'FAIL Hermes runtime cannot read the protected Grocy API key'; exit 1; }
  (cd "$repo_dir" && runuser -u "$runtime_user" -- env \
    HADES_GROCY_MCP_LAUNCHER="$repo_dir/integrations/grocy-mcp/launch.py" \
    HADES_GROCY_RUNTIME_API_KEY_FILE="$runtime_grocy_key" \
    HADES_GROCY_URL="${HADES_GROCY_URL:-http://127.0.0.1:7003}" \
    "$grocy_mcp_python" "$repo_dir/scripts/check-grocy-mcp-runtime.py") || { echo 'FAIL Grocy MCP functional catalog check'; exit 1; }
  if [[ -n "${HADES_HINDSIGHT_COMPOSE_FILE:-}" ]]; then
    hindsight_check_args=(--compose-file "$HADES_HINDSIGHT_COMPOSE_FILE")
    [[ -z "$inputs" ]] || hindsight_check_args+=(--env-file "$inputs")
    python3 "$repo_dir/scripts/check-hindsight-worker-runtime.py" "${hindsight_check_args[@]}" || exit 1
  elif [[ -n "$inputs" && "${HADES_INPUTS_VERSION:-1}" == 2 ]]; then
    echo 'FAIL Hindsight Compose record is unavailable for worker identity validation'
    exit 1
  else
    echo 'WARN Hindsight worker identity is not checked without a Compose record'
  fi
  echo 'WARN full conversation, identity, memory, Grocy, search, and operator checks require live private inputs'
fi
if ((synthetic_deployment_test)); then
  echo 'WARN validation applies only to the authorized synthetic test deployment'
fi
echo 'PASS install validation contract'
