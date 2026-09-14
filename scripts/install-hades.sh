#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; root_supplied=0; preflight_only=0; test_mode=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; root_supplied=1; shift 2 ;;
    --preflight) preflight_only=1; shift ;;
    --test-mode) test_mode=1; shift ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
[[ -n "$root" ]] || root=/
if [[ "$test_mode" == 1 && -z "$inputs" ]]; then inputs="$repo_dir/config/operator-inputs.env.example"; fi
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL missing config/versions.env' >&2; exit 1; }
[[ -f "$inputs" ]] || { echo "FAIL missing operator input file: $inputs" >&2; exit 1; }
[[ ! -L "$inputs" ]] || { echo 'FAIL operator input file must not be a symlink' >&2; exit 1; }
# shellcheck disable=SC1090
source "$inputs"
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD
fail() { echo "FAIL $*" >&2; exit 1; }
hades_layer_digest() {
  sha256sum "$@" | awk '{print $1}' | sha256sum | awk '{print $1}'
}
[[ "${HADES_MANIFEST_VERSION:-}" == 1 ]] || fail 'unsupported authoritative manifest version; expected version 1'
[[ "${HADES_INPUTS_VERSION:-}" == 1 ]] || fail 'unsupported operator input contract version; expected version 1'
compose_cmd=(docker compose --env-file "$inputs")
if ((test_mode && !root_supplied)); then fail 'test mode requires an explicit --root sandbox'; fi
need_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing prerequisite: $1"; }
under_root() { printf '%s/%s' "${root%/}" "${1#/}"; }
for name in HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE; do
  [[ -n "${!name:-}" ]] || fail "operator input is missing required deployment record variable: $name"
done
for name in HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_IDENTITY_SECRETS_DIR HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE HADES_HERMES_PROFILE HADES_HINDSIGHT_DATABASE_SECRET_FILE HADES_GROCY_API_KEY_FILE HADES_AGENT_ZERO_CREDENTIAL_FILE; do
  [[ -n "${!name:-}" ]] || fail "operator input is missing required path variable: $name"
  [[ "${!name}" == /* ]] || fail "operator input path must be absolute: $name"
done
validate_private_records() {
  deployment_dir=${HADES_DEPLOYMENT_DIR:-}
  [[ -n "$deployment_dir" ]] || fail 'HADES_DEPLOYMENT_DIR is required for private deployment records'
  [[ -d "$deployment_dir" ]] || fail "private deployment directory does not exist: $deployment_dir"
  [[ ! -L "$deployment_dir" ]] || fail 'private deployment directory must not be a symlink'
  for record in "$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE" "$HADES_HERMES_SERVICE_FILE"; do
    [[ -f "$record" ]] || fail "missing required private deployment record: $record"
    [[ ! -L "$record" ]] || fail 'private deployment records must not be symlinks'
    mode=$(stat -c '%a' "$record")
    [[ "$mode" == 600 || "$mode" == 640 ]] || fail 'private deployment records must be mode 0600 or 0640'
  done
  "${compose_cmd[@]}" -f "$HADES_OPEN_WEBUI_COMPOSE_FILE" config --quiet || fail 'invalid Open WebUI private compose record'
  "${compose_cmd[@]}" -f "$HADES_HINDSIGHT_COMPOSE_FILE" config --quiet || fail 'invalid Hindsight private compose record'
  "${compose_cmd[@]}" -f "$HADES_SEARXNG_COMPOSE_FILE" config --quiet || fail 'invalid SearXNG private compose record'
  for record in "$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE"; do
    images=$("${compose_cmd[@]}" -f "$record" config --images)
    if grep -Eq '(^|/|:)latest(@|$)' <<<"$images"; then
      fail 'private deployment record contains an unpinned latest image'
    fi
  done
  if (( ! test_mode )); then
    hindsight_images=$("${compose_cmd[@]}" -f "$HADES_HINDSIGHT_COMPOSE_FILE" config --images)
    grep -Fxq "$HADES_HINDSIGHT_IMAGE" <<<"$hindsight_images" ||
      fail 'Hindsight private record does not use config/versions.env:HADES_HINDSIGHT_IMAGE'
    searxng_images=$("${compose_cmd[@]}" -f "$HADES_SEARXNG_COMPOSE_FILE" config --images)
    grep -Fxq "$HADES_SEARXNG_IMAGE_RECORD" <<<"$searxng_images" ||
      fail 'SearXNG private record does not use config/versions.env:HADES_SEARXNG_IMAGE_RECORD'
  fi
  systemd-analyze verify "$HADES_HERMES_SERVICE_FILE" || fail 'invalid Hermes private service record'
  grep -Eq '^[[:space:]]*WantedBy=' "$HADES_HERMES_SERVICE_FILE" || fail 'Hermes private service record has no install target'
}
validate_secret_file() {
  local name=$1 path=${!1:-}
  [[ -n "$path" ]] || fail "required secret-file input is missing: $name"
  [[ "$path" == /* ]] || fail "secret-file input path must be absolute: $name"
  [[ -f "$path" ]] || fail "missing secret-file input: $name"
  [[ ! -L "$path" ]] || fail "secret-file input must not be a symlink: $name"
  mode=$(stat -c '%a' "$path")
  [[ "$mode" == 600 || "$mode" == 640 ]] || fail "secret-file input must be mode 0600 or 0640: $name"
}
validate_synthetic_secret_contract() {
  [[ -d "$HADES_IDENTITY_SECRETS_DIR" ]] || fail "missing identity secret directory: $HADES_IDENTITY_SECRETS_DIR"
  [[ ! -L "$HADES_IDENTITY_SECRETS_DIR" ]] || fail 'identity secret directory must not be a symlink'
  for secret in jwt_secret key_seed admin_password; do
    path="$HADES_IDENTITY_SECRETS_DIR/$secret"
    [[ -f "$path" && ! -L "$path" ]] || fail "missing or linked identity secret: $path"
    [[ "$(stat -c '%a' "$path")" == 600 ]] || fail "identity secret must be mode 0600: $path"
  done
  validate_secret_file HADES_HINDSIGHT_DATABASE_SECRET_FILE
  validate_secret_file HADES_GROCY_API_KEY_FILE
  if [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    validate_secret_file HADES_AGENT_ZERO_CREDENTIAL_FILE
  fi
}
validate_started_runtime() {
  for record in "$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE"; do
    running=$("${compose_cmd[@]}" -f "$record" ps --status running -q 2>/dev/null || true)
    [[ -n "$running" ]] || fail "private deployment has no running service: $record"
  done
  for container in hades-lldap hades-grocy hades-agent-zero; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
    [[ "$status" == running ]] || fail "deployed container is not running: $container (state=${status:-missing})"
  done
  systemctl is-active --quiet hades-hermes.service || fail 'deployed Hermes service is not active'
}
preflight() {
  tracked_sources=(
    config/versions.env
    config/reconstruction-manifest.json
    hermes/config.yaml.example
    hermes/env.example
    hermes/sitecustomize.py
    integrations/grocy-recipe-authoring/server.py
    integrations/agent-zero-mcp/server.py
    webui/hades-theme.css
    webui/hades-theme.js
    deploy/lldap.compose.yaml
    deploy/grocy.compose.yaml
    deploy/agent-zero.compose.yaml
  )
  for source_file in "${tracked_sources[@]}"; do
    [[ -f "$repo_dir/$source_file" ]] || fail "required tracked source is absent: $source_file"
  done
  if ((test_mode)); then
    if [[ -d "${HADES_DEPLOYMENT_DIR:-}" ]]; then
      validate_private_records
      validate_synthetic_secret_contract
      echo 'PASS synthetic private deployment records'
    fi
    echo 'PASS synthetic host contract (test mode)'
    return
  fi
  [[ $EUID -eq 0 ]] || fail 'run as root'
  [[ -r /etc/os-release ]] || fail 'cannot read OS identification'
  source /etc/os-release
  case "${ID:-}" in
    fedora) [[ "${VERSION_ID:-}" == 44 ]] || fail "unsupported Fedora version: ${VERSION_ID:-unknown}; use Fedora Server 44" ;;
    rocky) [[ "${VERSION_ID:-}" =~ ^(9|10)(\.|$) ]] || fail "unsupported Rocky Linux version: ${VERSION_ID:-unknown}; use Rocky Linux 9 or 10" ;;
    *) fail "unsupported OS: ${PRETTY_NAME:-unknown}; use Fedora Server 44 or Rocky Linux 9/10" ;;
  esac
  [[ "$(uname -m)" == x86_64 || "$(uname -m)" == aarch64 ]] || fail "unsupported architecture: $(uname -m)"
  need_cmd systemctl; need_cmd curl; need_cmd git; need_cmd openssl; need_cmd docker; need_cmd ss; need_cmd nproc
  docker compose version >/dev/null 2>&1 || fail 'missing Docker Compose plugin'
  systemctl --version >/dev/null 2>&1 || fail 'systemd is unavailable'
  cpu_count=$(nproc --all 2>/dev/null || true)
  [[ "$cpu_count" =~ ^[0-9]+$ && "$cpu_count" -ge 2 ]] || fail 'at least 2 CPU cores are required'
  memory_kb=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)
  [[ "$memory_kb" =~ ^[0-9]+$ && "$memory_kb" -ge 8388608 ]] || fail 'at least 8 GiB RAM is required'
  available_kb=$(df -Pk / | awk 'NR == 2 {print $4}')
  [[ "$available_kb" =~ ^[0-9]+$ && "$available_kb" -ge 41943040 ]] || fail 'at least 40 GiB free disk is required on the root filesystem'
  for port in 17170 7002 7003; do
    if ss -ltn "sport = :$port" | awk 'NR > 1 {found=1} END {exit !found}'; then
      case "$port" in
        17170) owned=hades-lldap ;;
        7002) owned=hades-agent-zero ;;
        7003) owned=hades-grocy ;;
      esac
      docker ps -a --format '{{.Names}}' | grep -Fxq "$owned" || fail "required private port is already occupied: $port"
    fi
  done
  for d in "$HADES_STATE_ROOT" "$HADES_CONFIG_ROOT" "$HADES_BACKUP_ROOT" "$HADES_HERMES_PROFILE"; do
    parent=$(dirname "$d")
    while [[ ! -d "$parent" && "$parent" != / ]]; do parent=$(dirname "$parent"); done
    [[ -d "$parent" && -w "$parent" ]] || fail "nearest existing parent is not writable for $d: $parent"
  done
  perms=$(stat -c '%a' "$inputs"); [[ "$perms" == 600 || "$perms" == 640 ]] || fail "operator input file must be mode 0600 or 0640: $inputs"
  [[ "$HADES_OWNER_BOOTSTRAP_ID" != REQUIRED_OPERATOR_INPUT && "$HADES_HERMES_API_KEY" != REQUIRED_OPERATOR_INPUT ]] || fail 'required operator input is still a placeholder'
  [[ "$HADES_HERMES_MODEL_ENDPOINT" =~ ^https?://[^[:space:]]+$ ]] || fail 'HADES_HERMES_MODEL_ENDPOINT must be an http(s) URL'
  curl --silent --connect-timeout 5 --max-time 10 --output /dev/null "$HADES_HERMES_MODEL_ENDPOINT" 2>/dev/null || fail 'configured model endpoint is not reachable; verify the private endpoint and DNS/network path'
  [[ -d "$HADES_IDENTITY_SECRETS_DIR" ]] || fail "missing identity secret directory: $HADES_IDENTITY_SECRETS_DIR"
  [[ ! -L "$HADES_IDENTITY_SECRETS_DIR" ]] || fail 'identity secret directory must not be a symlink'
  for secret in jwt_secret key_seed admin_password; do
    [[ -f "$HADES_IDENTITY_SECRETS_DIR/$secret" ]] || fail "missing LLDAP identity secret: $HADES_IDENTITY_SECRETS_DIR/$secret"
    [[ ! -L "$HADES_IDENTITY_SECRETS_DIR/$secret" ]] || fail 'LLDAP identity secrets must not be symlinks'
  done
  if find "$HADES_IDENTITY_SECRETS_DIR" -maxdepth 1 -type f -perm /077 -print -quit | grep -q .; then fail 'identity secret permissions are broader than 0600'; fi
  while read -r owner mode; do
    [[ "$owner" == 1000 && "$mode" == 600 ]] || fail "LLDAP identity secrets must be service-owned UID 1000 mode 0600 (found $owner mode $mode)"
  done < <(find "$HADES_IDENTITY_SECRETS_DIR" -maxdepth 1 -type f -printf '%U %m\n')
  validate_secret_file HADES_HINDSIGHT_DATABASE_SECRET_FILE
  validate_secret_file HADES_GROCY_API_KEY_FILE
  if [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    validate_secret_file HADES_AGENT_ZERO_CREDENTIAL_FILE
  fi
  validate_private_records
  echo 'PASS supported host preflight'
}
preflight
if ((preflight_only)); then exit 0; fi
if ((test_mode)); then
  config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
  mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
  [[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
  install -m 0644 "$repo_dir/config/reconstruction-manifest.json" "$config_root/reconstruction-manifest.json"
  [[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
  [[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
  install -d -m 0750 "$state_root/runtime" "$state_root/compose"
  install -d -m 0750 "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
  install -m 0644 "$repo_dir/hermes/sitecustomize.py" "$config_root/overlay/sitecustomize.py"
  install -m 0644 "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$config_root/adapters/grocy-recipe-authoring.py"
  install -m 0644 "$repo_dir/integrations/agent-zero-mcp/server.py" "$config_root/adapters/agent-zero-mcp.py"
  install -m 0644 "$repo_dir/webui/hades-theme.css" "$config_root/assets/hades-theme.css"
  install -m 0644 "$repo_dir/webui/hades-theme.js" "$config_root/assets/hades-theme.js"
  printf 'manifest=%s\nreconstruction_manifest=%s\nlayer=%s\ninstalled_from=%s\nphase=prepared\n' "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" "$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')" "$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js")" "$repo_dir" > "$state_root/install-contract"
  chmod 0640 "$state_root/install-contract"
  if [[ "${HADES_TEST_FAIL_AFTER_PREPARE:-0}" == 1 ]]; then
    echo 'FAIL synthetic injected interruption after preparation' >&2
    exit 97
  fi
  echo 'PASS test-mode installation contract (no containers, no fixture data)'
  exit 0
fi
config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
[[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
install -m 0644 "$repo_dir/config/reconstruction-manifest.json" "$config_root/reconstruction-manifest.json"
[[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
[[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
install -d -m 0750 "$state_root/runtime" "$state_root/compose"
install -d -m 0750 "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
install -m 0644 "$repo_dir/hermes/sitecustomize.py" "$config_root/overlay/sitecustomize.py"
install -m 0644 "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$config_root/adapters/grocy-recipe-authoring.py"
install -m 0644 "$repo_dir/integrations/agent-zero-mcp/server.py" "$config_root/adapters/agent-zero-mcp.py"
install -m 0644 "$repo_dir/webui/hades-theme.css" "$config_root/assets/hades-theme.css"
install -m 0644 "$repo_dir/webui/hades-theme.js" "$config_root/assets/hades-theme.js"
printf 'manifest=%s\nreconstruction_manifest=%s\nlayer=%s\ninstalled_from=%s\nphase=prepared\n' "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" "$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')" "$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js")" "$repo_dir" > "$state_root/install-contract"
chmod 0640 "$state_root/install-contract"
export HADES_IDENTITY_SECRETS_DIR
compose="$repo_dir/deploy/lldap.compose.yaml"
"${compose_cmd[@]}" -f "$compose" config --quiet || fail 'invalid compose contract: lldap'
"${compose_cmd[@]}" -f "$compose" up -d
"${compose_cmd[@]}" -f "$HADES_OPEN_WEBUI_COMPOSE_FILE" up -d
"${compose_cmd[@]}" -f "$HADES_HINDSIGHT_COMPOSE_FILE" up -d
compose="$repo_dir/deploy/grocy.compose.yaml"
"${compose_cmd[@]}" -f "$compose" config --quiet || fail 'invalid compose contract: grocy'
"${compose_cmd[@]}" -f "$compose" up -d
compose="$repo_dir/deploy/agent-zero.compose.yaml"
"${compose_cmd[@]}" -f "$compose" config --quiet || fail 'invalid compose contract: agent-zero'
"${compose_cmd[@]}" -f "$compose" up -d
"${compose_cmd[@]}" -f "$HADES_SEARXNG_COMPOSE_FILE" up -d
install -m 0600 "$HADES_HERMES_SERVICE_FILE" /etc/systemd/system/hades-hermes.service
systemctl daemon-reload
systemctl enable --now hades-hermes.service
validate_started_runtime
printf 'phase=deployed\n' >> "$state_root/install-contract"
echo 'PASS HADES component deployment completed from tracked contracts and explicit private records'
