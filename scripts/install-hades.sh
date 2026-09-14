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
# shellcheck disable=SC1090
source "$inputs"
fail() { echo "FAIL $*" >&2; exit 1; }
compose_cmd=(docker compose --env-file "$inputs")
if ((test_mode && !root_supplied)); then fail 'test mode requires an explicit --root sandbox'; fi
need_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing prerequisite: $1"; }
under_root() { printf '%s/%s' "${root%/}" "${1#/}"; }
for name in HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE; do
  [[ -n "${!name:-}" ]] || fail "operator input is missing required deployment record variable: $name"
done
validate_private_records() {
  deployment_dir=${HADES_DEPLOYMENT_DIR:-}
  [[ -n "$deployment_dir" ]] || fail 'HADES_DEPLOYMENT_DIR is required for private deployment records'
  [[ -d "$deployment_dir" ]] || fail "private deployment directory does not exist: $deployment_dir"
  for record in "$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE" "$HADES_HERMES_SERVICE_FILE"; do
    [[ -f "$record" ]] || fail "missing required private deployment record: $record"
  done
  "${compose_cmd[@]}" -f "$HADES_OPEN_WEBUI_COMPOSE_FILE" config --quiet || fail 'invalid Open WebUI private compose record'
  "${compose_cmd[@]}" -f "$HADES_HINDSIGHT_COMPOSE_FILE" config --quiet || fail 'invalid Hindsight private compose record'
  "${compose_cmd[@]}" -f "$HADES_SEARXNG_COMPOSE_FILE" config --quiet || fail 'invalid SearXNG private compose record'
  systemd-analyze verify "$HADES_HERMES_SERVICE_FILE" || fail 'invalid Hermes private service record'
  grep -Eq '^[[:space:]]*WantedBy=' "$HADES_HERMES_SERVICE_FILE" || fail 'Hermes private service record has no install target'
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
  [[ -f "$repo_dir/hermes/config.yaml.example" ]] || fail 'Hermes config template is absent'
  [[ -f "$repo_dir/hermes/env.example" ]] || fail 'Hermes environment template is absent'
  if ((test_mode)); then echo 'PASS synthetic host contract (test mode)'; return; fi
  [[ $EUID -eq 0 ]] || fail 'run as root'
  [[ -r /etc/os-release ]] || fail 'cannot read OS identification'
  source /etc/os-release
  case "${ID:-}" in
    fedora) [[ "${VERSION_ID:-}" == 44 ]] || fail "unsupported Fedora version: ${VERSION_ID:-unknown}; use Fedora Server 44" ;;
    rocky) [[ "${VERSION_ID:-}" =~ ^(9|10)(\.|$) ]] || fail "unsupported Rocky Linux version: ${VERSION_ID:-unknown}; use Rocky Linux 9 or 10" ;;
    *) fail "unsupported OS: ${PRETTY_NAME:-unknown}; use Fedora Server 44 or Rocky Linux 9/10" ;;
  esac
  [[ "$(uname -m)" == x86_64 || "$(uname -m)" == aarch64 ]] || fail "unsupported architecture: $(uname -m)"
  need_cmd systemctl; need_cmd curl; need_cmd git; need_cmd openssl; need_cmd docker; need_cmd ss
  docker compose version >/dev/null 2>&1 || fail 'missing Docker Compose plugin'
  systemctl --version >/dev/null 2>&1 || fail 'systemd is unavailable'
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
  for d in "$HADES_STATE_ROOT" "$HADES_CONFIG_ROOT" "$HADES_BACKUP_ROOT"; do
    parent=$(dirname "$d")
    while [[ ! -d "$parent" && "$parent" != / ]]; do parent=$(dirname "$parent"); done
    [[ -d "$parent" && -w "$parent" ]] || fail "nearest existing parent is not writable for $d: $parent"
  done
  perms=$(stat -c '%a' "$inputs"); [[ "$perms" == 600 || "$perms" == 640 ]] || fail "operator input file must be mode 0600 or 0640: $inputs"
  [[ "$HADES_OWNER_BOOTSTRAP_ID" != REQUIRED_OPERATOR_INPUT && "$HADES_HERMES_API_KEY" != REQUIRED_OPERATOR_INPUT ]] || fail 'required operator input is still a placeholder'
  [[ "$HADES_HERMES_MODEL_ENDPOINT" =~ ^https?://[^[:space:]]+$ ]] || fail 'HADES_HERMES_MODEL_ENDPOINT must be an http(s) URL'
  curl --silent --show-error --connect-timeout 5 --max-time 10 --output /dev/null "$HADES_HERMES_MODEL_ENDPOINT" || fail 'configured model endpoint is not reachable; verify the private endpoint and DNS/network path'
  [[ -d "$HADES_IDENTITY_SECRETS_DIR" ]] || fail "missing identity secret directory: $HADES_IDENTITY_SECRETS_DIR"
  for secret in jwt_secret key_seed admin_password; do
    [[ -f "$HADES_IDENTITY_SECRETS_DIR/$secret" ]] || fail "missing LLDAP identity secret: $HADES_IDENTITY_SECRETS_DIR/$secret"
  done
  if find "$HADES_IDENTITY_SECRETS_DIR" -maxdepth 1 -type f -perm /077 -print -quit | grep -q .; then fail 'identity secret permissions are broader than 0600'; fi
  while read -r owner mode; do
    [[ "$owner" == 1000 && "$mode" == 600 ]] || fail "LLDAP identity secrets must be service-owned UID 1000 mode 0600 (found $owner mode $mode)"
  done < <(find "$HADES_IDENTITY_SECRETS_DIR" -maxdepth 1 -type f -printf '%U %m\n')
  validate_private_records
  echo 'PASS supported host preflight'
}
preflight
if ((preflight_only)); then exit 0; fi
if ((test_mode)); then
  config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
  mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
  [[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
  [[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
  [[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
  install -d -m 0750 "$state_root/runtime" "$state_root/compose"
  install -d -m 0750 "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
  install -m 0644 "$repo_dir/hermes/sitecustomize.py" "$config_root/overlay/sitecustomize.py"
  install -m 0644 "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$config_root/adapters/grocy-recipe-authoring.py"
  install -m 0644 "$repo_dir/integrations/agent-zero-mcp/server.py" "$config_root/adapters/agent-zero-mcp.py"
  install -m 0644 "$repo_dir/webui/hades-theme.css" "$config_root/assets/hades-theme.css"
  install -m 0644 "$repo_dir/webui/hades-theme.js" "$config_root/assets/hades-theme.js"
  printf 'manifest=%s\ninstalled_from=%s\nphase=prepared\n' "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" "$repo_dir" > "$state_root/install-contract"
  chmod 0640 "$state_root/install-contract"
  echo 'PASS test-mode installation contract (no containers, no fixture data)'
  exit 0
fi
config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
[[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
[[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
[[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
install -d -m 0750 "$state_root/runtime" "$state_root/compose"
install -d -m 0750 "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
install -m 0644 "$repo_dir/hermes/sitecustomize.py" "$config_root/overlay/sitecustomize.py"
install -m 0644 "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$config_root/adapters/grocy-recipe-authoring.py"
install -m 0644 "$repo_dir/integrations/agent-zero-mcp/server.py" "$config_root/adapters/agent-zero-mcp.py"
install -m 0644 "$repo_dir/webui/hades-theme.css" "$config_root/assets/hades-theme.css"
install -m 0644 "$repo_dir/webui/hades-theme.js" "$config_root/assets/hades-theme.js"
printf 'manifest=%s\ninstalled_from=%s\nphase=prepared\n' "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" "$repo_dir" > "$state_root/install-contract"
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
install -m 0644 "$HADES_HERMES_SERVICE_FILE" /etc/systemd/system/hades-hermes.service
systemctl daemon-reload
systemctl enable --now hades-hermes.service
validate_started_runtime
printf 'phase=deployed\n' >> "$state_root/install-contract"
echo 'PASS HADES component deployment completed from tracked contracts and explicit private records'
