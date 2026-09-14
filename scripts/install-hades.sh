#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; preflight_only=0; test_mode=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; shift 2 ;;
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
need_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing prerequisite: $1"; }
under_root() { printf '%s/%s' "${root%/}" "${1#/}"; }
for name in HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE; do
  [[ -n "${!name:-}" ]] || fail "operator input is missing required deployment record variable: $name"
done
preflight() {
  [[ -f "$repo_dir/hermes/config.yaml.example" ]] || fail 'Hermes config template is absent'
  [[ -f "$repo_dir/hermes/env.example" ]] || fail 'Hermes environment template is absent'
  if ((test_mode)); then echo 'PASS synthetic host contract (test mode)'; return; fi
  [[ $EUID -eq 0 ]] || fail 'run as root'
  [[ -r /etc/os-release ]] || fail 'cannot read OS identification'
  source /etc/os-release
  [[ "${ID:-}" == fedora || "${ID_LIKE:-}" == *rhel* || "${ID_LIKE:-}" == *fedora* ]] || fail "unsupported OS: ${PRETTY_NAME:-unknown}; use Fedora Server or Rocky Linux"
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
  [[ -d "$HADES_IDENTITY_SECRETS_DIR" ]] || fail "missing identity secret directory: $HADES_IDENTITY_SECRETS_DIR"
  if find "$HADES_IDENTITY_SECRETS_DIR" -maxdepth 1 -type f -perm /077 -print -quit | grep -q .; then fail 'identity secret permissions are broader than 0600'; fi
  while read -r owner mode; do
    [[ "$owner" == 1000 && "$mode" == 600 ]] || fail "LLDAP identity secrets must be service-owned UID 1000 mode 0600 (found $owner mode $mode)"
  done < <(find "$HADES_IDENTITY_SECRETS_DIR" -maxdepth 1 -type f -printf '%U %m\n')
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
  printf 'manifest=%s\ninstalled_from=%s\nphase=prepared\n' "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" "$repo_dir" > "$state_root/install-contract"
  chmod 0640 "$state_root/install-contract"
  echo 'PASS test-mode installation contract (no containers, no fixture data)'
  exit 0
fi
deployment_dir=${HADES_DEPLOYMENT_DIR:-}
[[ -n "$deployment_dir" ]] || fail 'HADES_DEPLOYMENT_DIR is required for private deployment records'
[[ -d "$deployment_dir" ]] || fail "private deployment directory does not exist: $deployment_dir"
for record in "$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE" "$HADES_HERMES_SERVICE_FILE"; do
  [[ -f "$record" ]] || fail "missing required private deployment record: $record"
done
docker compose -f "$HADES_OPEN_WEBUI_COMPOSE_FILE" config --quiet || fail 'invalid Open WebUI private compose record'
docker compose -f "$HADES_HINDSIGHT_COMPOSE_FILE" config --quiet || fail 'invalid Hindsight private compose record'
docker compose -f "$HADES_SEARXNG_COMPOSE_FILE" config --quiet || fail 'invalid SearXNG private compose record'
systemd-analyze verify "$HADES_HERMES_SERVICE_FILE" || fail 'invalid Hermes private service record'
config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
[[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
[[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
[[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
install -d -m 0750 "$state_root/runtime" "$state_root/compose"
printf 'manifest=%s\ninstalled_from=%s\nphase=prepared\n' "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" "$repo_dir" > "$state_root/install-contract"
chmod 0640 "$state_root/install-contract"
export HADES_IDENTITY_SECRETS_DIR
compose="$repo_dir/deploy/lldap.compose.yaml"
docker compose -f "$compose" config --quiet || fail 'invalid compose contract: lldap'
docker compose -f "$compose" up -d
docker compose -f "$HADES_OPEN_WEBUI_COMPOSE_FILE" up -d
docker compose -f "$HADES_HINDSIGHT_COMPOSE_FILE" up -d
compose="$repo_dir/deploy/grocy.compose.yaml"
docker compose -f "$compose" config --quiet || fail 'invalid compose contract: grocy'
docker compose -f "$compose" up -d
docker compose -f "$HADES_SEARXNG_COMPOSE_FILE" up -d
compose="$repo_dir/deploy/agent-zero.compose.yaml"
docker compose -f "$compose" config --quiet || fail 'invalid compose contract: agent-zero'
docker compose -f "$compose" up -d
install -m 0644 "$HADES_HERMES_SERVICE_FILE" /etc/systemd/system/hades-hermes.service
systemctl daemon-reload
systemctl enable --now hades-hermes.service
printf 'phase=deployed\n' >> "$state_root/install-contract"
echo 'PASS HADES component deployment completed from tracked contracts and explicit private records'
