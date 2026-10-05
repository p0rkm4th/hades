#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''; root=/; root_supplied=0; preflight_only=0; test_mode=0; synthetic_deployment_test=0
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --root) root=${2:?--root needs a directory}; root_supplied=1; shift 2 ;;
    --preflight) preflight_only=1; shift ;;
    --test-mode) test_mode=1; shift ;;
    --synthetic-deployment-test) synthetic_deployment_test=1; shift ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "FAIL unknown option: $1" >&2; exit 2 ;;
  esac
done
if ((synthetic_deployment_test && (test_mode || root_supplied))); then
  echo 'FAIL --synthetic-deployment-test runs the real host path; do not combine it with sandbox options' >&2
  exit 2
fi
[[ -n "$root" ]] || root=/
if [[ "$test_mode" == 1 && -z "$inputs" ]]; then inputs="$repo_dir/config/operator-inputs.env.example"; fi
[[ -f "$repo_dir/config/versions.env" ]] || { echo 'FAIL missing config/versions.env' >&2; exit 1; }
[[ -f "$inputs" ]] || { echo "FAIL missing operator input file: $inputs" >&2; exit 1; }
[[ ! -L "$inputs" ]] || { echo 'FAIL operator input file must not be a symlink' >&2; exit 1; }
# shellcheck disable=SC1090
source "$inputs"
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD HADES_NGINX_IMAGE
fail() { echo "FAIL $*" >&2; exit 1; }
source_revision=archive
source_tree=unavailable
source_clean=unknown
if source_revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse --verify HEAD 2>/dev/null); then
  source_tree=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse 'HEAD^{tree}' 2>/dev/null) || fail 'could not read the source Git tree'
  source_status=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" status --porcelain=v1 --untracked-files=all 2>/dev/null) || fail 'could not verify source worktree cleanliness'
  if [[ -z "$source_status" ]]; then
    source_clean=true
  else
    source_clean=false
  fi
elif (( ! test_mode )); then
  fail 'production installation requires a Git checkout with a committed revision'
fi
if (( ! test_mode )) && [[ "$source_clean" != true ]]; then
  fail 'production installation requires a clean Git worktree; commit or revert source changes and retry'
fi
source_provenance_records() {
  printf 'source_revision=%s\nsource_tree=%s\nsource_clean=%s\n' \
    "$source_revision" "$source_tree" "$source_clean"
}
hades_layer_digest() {
  sha256sum "$@" | awk '{print $1}' | sha256sum | awk '{print $1}'
}
[[ "${HADES_MANIFEST_VERSION:-}" == 1 ]] || fail 'unsupported authoritative manifest version; expected version 1'
[[ "${HADES_INPUTS_VERSION:-}" == 1 || "${HADES_INPUTS_VERSION:-}" == 2 ]] || fail 'unsupported operator input contract version; expected version 1 or 2'
if [[ "${HADES_SYNTHETIC_FIXTURE:-false}" == true && "$test_mode" != 1 ]]; then
  if (( ! synthetic_deployment_test )); then
    fail 'synthetic fixture inputs are test-only and cannot be used for production installation'
  fi
  bash "$repo_dir/scripts/synthetic-deployment-target.sh" verify
elif ((synthetic_deployment_test)); then
  fail '--synthetic-deployment-test requires HADES_SYNTHETIC_FIXTURE=true inputs'
fi
if (( ! test_mode )) && grep -Eq '^[A-Z_][A-Z0-9_]*=[^#]*REQUIRED_[A-Z0-9_]+' "$inputs"; then
  fail 'operator input still contains a REQUIRED_ placeholder'
fi
generated_records=0
if [[ "$HADES_INPUTS_VERSION" == 2 ]]; then
  generated_records=1
  : "${HADES_CONFIG_ROOT:?operator input is missing HADES_CONFIG_ROOT}"
  : "${HADES_HERMES_PROFILE:?operator input is missing HADES_HERMES_PROFILE}"
  HADES_DEPLOYMENT_DIR=${HADES_DEPLOYMENT_DIR:-$HADES_CONFIG_ROOT/private-deployment}
  HADES_OPEN_WEBUI_COMPOSE_FILE=${HADES_OPEN_WEBUI_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/open-webui.compose.yaml}
  HADES_HINDSIGHT_COMPOSE_FILE=${HADES_HINDSIGHT_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/hindsight.compose.yaml}
  HADES_SEARXNG_COMPOSE_FILE=${HADES_SEARXNG_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/searxng.compose.yaml}
  HADES_HERMES_SERVICE_FILE=${HADES_HERMES_SERVICE_FILE:-$HADES_DEPLOYMENT_DIR/hermes.service}
  HADES_AGENT_ZERO_CLIENT_ENV_FILE="$HADES_DEPLOYMENT_DIR/agent-zero-client-auth.env"
  HADES_GROCY_URL=${HADES_GROCY_URL:-http://127.0.0.1:7003}
  [[ "$HADES_GROCY_URL" =~ ^https?://[^[:space:]\\#\;\"\']+$ ]] || fail 'HADES_GROCY_URL must be a simple HTTP(S) URL without spaces, quotes, or shell separators'
  export HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE
  export HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE HADES_AGENT_ZERO_CLIENT_ENV_FILE
fi
if ((synthetic_deployment_test)) && [[ "$HADES_INPUTS_VERSION" != 2 ]]; then
  fail '--synthetic-deployment-test requires generated operator input contract v2'
fi
if (( ! generated_records )) && [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
  fail 'Agent Zero native Operator login requires v2 generated deployment records'
fi
HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=${HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED:-false}
HADES_AGENT_ZERO_OPERATOR_PORT=${HADES_AGENT_ZERO_OPERATOR_PORT:-7004}
[[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true || "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == false ]] || fail 'HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED must be true or false'
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
  (( generated_records )) || fail 'Agent Zero Operator proxy requires v2 generated deployment records'
  [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]] || fail 'Agent Zero Operator proxy requires HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE'
  [[ -n "${HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE:-}" && -n "${HADES_EPSILON_PHASE3_LLDAP_URL:-}" && -n "${HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE:-}" ]] || fail 'Agent Zero Operator proxy requires the live Phase 3 LLDAP authority file, URL, and reader password file'
fi
compose_cmd=(docker compose --env-file "$inputs")
if ((test_mode && !root_supplied)); then fail 'test mode requires an explicit --root sandbox'; fi
need_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing prerequisite: $1"; }
under_root() { printf '%s/%s' "${root%/}" "${1#/}"; }
ensure_shared_network() {
  local name=$1 found
  if found=$(docker network inspect --format '{{.Driver}} {{.Scope}}' "$name" 2>/dev/null); then
    [[ "$found" == 'bridge local' ]] || fail "shared network has an incompatible driver or scope: $name ($found)"
  else
    docker network create --driver bridge "$name" >/dev/null || fail "could not create required shared bridge network: $name"
  fi
}
if (( ! generated_records )); then
  : "${HADES_HINDSIGHT_DATABASE_SECRET_FILE:?operator input is missing HADES_HINDSIGHT_DATABASE_SECRET_FILE}"
  for name in HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE; do
    [[ -n "${!name:-}" ]] || fail "operator input is missing required deployment record variable: $name"
  done
fi
for name in HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_IDENTITY_SECRETS_DIR HADES_DEPLOYMENT_DIR HADES_OPEN_WEBUI_COMPOSE_FILE HADES_HINDSIGHT_COMPOSE_FILE HADES_SEARXNG_COMPOSE_FILE HADES_HERMES_SERVICE_FILE HADES_HERMES_PROFILE HADES_GROCY_API_KEY_FILE; do
  [[ -n "${!name:-}" ]] || fail "operator input is missing required path variable: $name"
  [[ "${!name}" == /* ]] || fail "operator input path must be absolute: $name"
done
if (( generated_records )); then
  [[ -n "${HADES_HERMES_WORKING_DIRECTORY:-}" && "$HADES_HERMES_WORKING_DIRECTORY" == /* ]] ||
    fail 'v2 operator input is missing an absolute HADES_HERMES_WORKING_DIRECTORY'
fi
if [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
  [[ "$HADES_AGENT_ZERO_CREDENTIAL_FILE" == /* ]] || fail 'operator input path must be absolute: HADES_AGENT_ZERO_CREDENTIAL_FILE'
fi
HADES_AGENT_ZERO_CLIENT_ENV_FILE=${HADES_AGENT_ZERO_CLIENT_ENV_FILE:-$HADES_DEPLOYMENT_DIR/agent-zero-client-auth.env}
if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
  [[ "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE" == /* ]] || fail 'operator password path must be absolute: HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE'
  HADES_AGENT_ZERO_AUTH_ENV_FILE="$HADES_DEPLOYMENT_DIR/agent-zero-operator-auth.env"
  export HADES_AGENT_ZERO_AUTH_ENV_FILE
fi
HADES_HERMES_RUNTIME_USER=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
HADES_HERMES_RUNTIME_GROUP=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
HADES_OPEN_WEBUI_SECRET_SOURCE=${HADES_OPEN_WEBUI_SECRET_SOURCE:-$HADES_STATE_ROOT/secrets/open-webui-secret}
[[ "$HADES_HERMES_RUNTIME_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || fail 'invalid HADES_HERMES_RUNTIME_USER'
[[ "$HADES_HERMES_RUNTIME_GROUP" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || fail 'invalid HADES_HERMES_RUNTIME_GROUP'
[[ "$HADES_OPEN_WEBUI_SECRET_SOURCE" == /* ]] || fail 'HADES_OPEN_WEBUI_SECRET_SOURCE must be absolute'
if (( generated_records )); then
  [[ -n "${HADES_HERMES_EXECUTABLE:-}" ]] || fail 'operator input is missing required path variable: HADES_HERMES_EXECUTABLE'
  [[ "$HADES_HERMES_EXECUTABLE" == /* ]] || fail 'operator input path must be absolute: HADES_HERMES_EXECUTABLE'
  [[ "${HADES_SEARXNG_SECRET_FILE:-}" == /* ]] || fail 'operator input path must be absolute: HADES_SEARXNG_SECRET_FILE'
fi
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
  if (( generated_records )); then
    grocy_record="$deployment_dir/grocy-mcp.env"
    [[ -f "$grocy_record" && ! -L "$grocy_record" && "$(stat -c '%a' "$grocy_record")" == 600 ]] ||
      fail 'generated Grocy MCP environment record is missing, linked, or not mode 0600'
    grep -Fxq "HADES_GROCY_URL=${HADES_GROCY_URL:-http://127.0.0.1:7003}" "$grocy_record" ||
      fail 'generated Grocy MCP URL record is stale; rerun the deployment-record renderer'
    grep -Fxq "HADES_GROCY_API_KEY_FILE=$HADES_CONFIG_ROOT/secrets/grocy-api-key" "$grocy_record" ||
      fail 'generated Grocy MCP key path is stale; rerun the deployment-record renderer'
    owner_policy_record="$deployment_dir/hades-owner-policy.env"
    if [[ -n "${HADES_OWNER_SUBJECT_IDS:-}" ]]; then
      [[ -f "$owner_policy_record" && ! -L "$owner_policy_record" ]] || fail 'generated Hermes owner-policy record is missing or unsafe'
      owner_policy_mode=$(stat -c '%a' "$owner_policy_record")
      [[ "$owner_policy_mode" == 600 || "$owner_policy_mode" == 640 ]] || fail 'generated Hermes owner-policy record must be mode 0600 or 0640'
      [[ "$(wc -l < "$owner_policy_record")" == 1 ]] || fail 'generated Hermes owner-policy record is malformed'
      grep -Fxq "HADES_OWNER_SUBJECT_IDS=$HADES_OWNER_SUBJECT_IDS" "$owner_policy_record" || fail 'generated Hermes owner-policy record is stale; rerun the deployment-record renderer'
    elif [[ -e "$owner_policy_record" || -L "$owner_policy_record" ]]; then
      fail 'generated Hermes owner-policy record is stale; rerun the deployment-record renderer'
    fi
  fi
  if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
    auth_record="$deployment_dir/agent-zero-operator-auth.env"
    [[ -f "$auth_record" && ! -L "$auth_record" && "$(stat -c '%a' "$auth_record")" == 600 ]] ||
      fail 'generated Agent Zero Operator auth env file is missing, linked, or not mode 0600'
    mapfile -t auth_lines < "$auth_record"
    [[ "${#auth_lines[@]}" == 2 && "${auth_lines[0]}" == 'AUTH_LOGIN=hades-operator' && "${auth_lines[1]}" =~ ^AUTH_PASSWORD=[A-Za-z0-9._~-]{16,256}$ ]] ||
      fail 'generated Agent Zero Operator auth env file is malformed'
    expected_password=$(<"$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE")
    rendered_password=${auth_lines[1]#AUTH_PASSWORD=}
    [[ "$rendered_password" == "$expected_password" ]] || fail 'generated Agent Zero Operator auth is stale; rerun the installer'
    "${compose_cmd[@]}" -f "$repo_dir/deploy/agent-zero.compose.yaml" config --quiet ||
      fail 'invalid Agent Zero Compose record with optional native auth'
  elif [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    if (( ! test_mode )); then
      client_record="$deployment_dir/agent-zero-client-auth.env"
      [[ -f "$client_record" && ! -L "$client_record" && "$(stat -c '%a' "$client_record")" == 600 ]] ||
        fail 'generated Agent Zero client auth env is missing, linked, or not mode 0600'
      mapfile -t client_lines < "$client_record"
      [[ "${#client_lines[@]}" == 1 && "${client_lines[0]}" == "AGENT_ZERO_API_KEY=$(<"$HADES_AGENT_ZERO_CREDENTIAL_FILE")" ]] ||
        fail 'generated Agent Zero API credential is malformed or stale'
    fi
  fi
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    for record in "$deployment_dir/agent-zero-operator-proxy.env" "$deployment_dir/agent-zero-operator-proxy.compose.yaml" "$deployment_dir/agent-zero-operator-auth.service"; do
      [[ -f "$record" && ! -L "$record" && "$(stat -c '%a' "$record")" == 600 ]] || fail 'generated Agent Zero Operator proxy deployment record is missing, linked, or not mode 0600'
    done
    [[ -f "$HADES_CONFIG_ROOT/operator-proxy/nginx.conf" && "$(stat -c '%a' "$HADES_CONFIG_ROOT/operator-proxy/nginx.conf")" == 644 ]] || fail 'generated Operator Nginx configuration is missing or has unsafe permissions'
    for secret in phase3-authority.json lldap-reader-password auth.env; do
      [[ -f "$HADES_CONFIG_ROOT/operator-proxy/$secret" && ! -L "$HADES_CONFIG_ROOT/operator-proxy/$secret" && "$(stat -c '%a' "$HADES_CONFIG_ROOT/operator-proxy/$secret")" == 600 ]] || fail "generated Operator private input is missing or unsafe: $secret"
    done
    "${compose_cmd[@]}" -f "$deployment_dir/agent-zero-operator-proxy.compose.yaml" config --quiet || fail 'invalid Agent Zero Operator proxy Compose record'
    SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system systemd-analyze verify "$deployment_dir/agent-zero-operator-auth.service" || fail 'invalid Agent Zero Operator auth service record'
  fi
  "${compose_cmd[@]}" -f "$HADES_OPEN_WEBUI_COMPOSE_FILE" config --quiet || fail 'invalid Open WebUI private compose record'
  "${compose_cmd[@]}" -f "$HADES_HINDSIGHT_COMPOSE_FILE" config --quiet || fail 'invalid Hindsight private compose record'
  "${compose_cmd[@]}" -f "$HADES_SEARXNG_COMPOSE_FILE" config --quiet || fail 'invalid SearXNG private compose record'
  for record in "$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE"; do
    images=$("${compose_cmd[@]}" -f "$record" config --images)
    if grep -Eq '(^|/|:)latest(@|$)' <<<"$images"; then
      fail 'private deployment record contains an unpinned latest image'
    fi
    if (( ! test_mode )); then
      while IFS= read -r image; do
        [[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] ||
          fail "private deployment record contains a mutable image reference: $record"
      done <<<"$images"
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
# Validate against vendor dependencies only. Host-local units may be
# intentionally unreadable during test-mode installation and are unrelated to
# this disposable generated record.
SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system \
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
  if [[ "$name" == HADES_GROCY_API_KEY_FILE && "$test_mode" != 1 ]] && grep -Eq '^(REQUIRED_|SYNTHETIC_GROCY_API_KEY$)' "$path"; then
    fail 'Grocy key is a placeholder; issue a key in Grocy Manage API keys and store it in the protected input file'
  fi
}
validate_v2_ldap_binding() {
  [[ -n "${HADES_OPEN_WEBUI_LDAP_APP_PASSWORD:-}" ]] || fail 'v2 Open WebUI LDAP bind password is missing'
  [[ "${HADES_OPEN_WEBUI_LDAP_APP_PASSWORD}" == "$(<"$HADES_IDENTITY_SECRETS_DIR/admin_password")" ]] ||
    fail 'v2 Open WebUI LDAP bind password does not match the configured LLDAP password'
}
validate_hermes_profile_parent() {
  local path parent mode other walk
  parent=$(dirname "$HADES_HERMES_PROFILE")
  while [[ ! -d "$parent" && "$parent" != / ]]; do parent=$(dirname "$parent"); done
  [[ -d "$parent" && ! -L "$parent" ]] || fail 'Hermes profile parent is missing or is a symlink'
  if id "$HADES_HERMES_RUNTIME_USER" >/dev/null 2>&1; then
    runuser -u "$HADES_HERMES_RUNTIME_USER" -- test -x "$parent" ||
      fail "Hermes runtime cannot traverse the profile parent: $parent; place the profile under a service-accessible persistent path such as /var/lib/hades"
    return
  fi
  walk=$parent
  while [[ "$walk" != / ]]; do
    [[ -d "$walk" && ! -L "$walk" ]] || fail "Hermes profile path contains a missing directory or symlink: $walk"
    mode=$(stat -c '%a' "$walk")
    other=${mode: -1}
    [[ "$other" =~ ^[0-7]$ ]] || fail "cannot inspect Hermes profile parent permissions: $walk"
    (( (8#$other & 1) == 1 )) ||
      fail "Hermes profile parent is not traversable by its future service account: $walk; place the profile under a service-accessible persistent path such as /var/lib/hades"
    walk=$(dirname "$walk")
  done
}
validate_hermes_working_directory() {
  local path=${HADES_HERMES_WORKING_DIRECTORY:-} walk mode other source_file view_source
  [[ -n "$path" ]] || return 0
  [[ "$path" == /* && -d "$path" && ! -L "$path" ]] ||
    fail 'HADES_HERMES_WORKING_DIRECTORY must be an existing absolute non-symlink directory'
  source_file="$path/hermes/config.yaml.example"
  [[ -f "$source_file" && ! -L "$source_file" ]] ||
    fail 'Hermes working directory is missing the tracked Hermes configuration source'
  view_source="$path/integrations/homelab_views.py"
  [[ -f "$view_source" && ! -L "$view_source" ]] ||
    fail 'Hermes working directory is missing the tracked homelab view module'
  if id "$HADES_HERMES_RUNTIME_USER" >/dev/null 2>&1; then
    runuser -u "$HADES_HERMES_RUNTIME_USER" -- test -x "$path" &&
      runuser -u "$HADES_HERMES_RUNTIME_USER" -- test -r "$source_file" &&
      runuser -u "$HADES_HERMES_RUNTIME_USER" -- test -r "$view_source" ||
      fail "Hermes runtime cannot traverse or read its working directory: $path; use a service-accessible checkout such as /opt/hades"
    return 0
  fi
  # On a first install the service account is created only after preflight.
  # Require the checkout path and source file to be traversable/readable by an
  # unrelated service identity before any persistent state is written.
  walk=$path
  while [[ "$walk" != / ]]; do
    [[ -d "$walk" && ! -L "$walk" ]] || fail "Hermes working-directory path contains a missing directory or symlink: $walk"
    mode=$(stat -c '%a' "$walk")
    other=${mode: -1}
    [[ "$other" =~ ^[0-7]$ ]] || fail "cannot inspect Hermes working-directory permissions: $walk"
    (( (8#$other & 1) == 1 )) ||
      fail "Hermes working directory is not traversable by its future service account: $walk; use a service-accessible checkout such as /opt/hades"
    walk=$(dirname "$walk")
  done
  mode=$(stat -c '%a' "$view_source")
  other=${mode: -1}
  [[ "$other" =~ ^[0-7]$ ]] && (( (8#$other & 4) == 4 )) ||
    fail "Hermes homelab view module is not readable by its future service account: $view_source"
  mode=$(stat -c '%a' "$source_file")
  other=${mode: -1}
  [[ "$other" =~ ^[0-7]$ ]] && (( (8#$other & 4) == 4 )) ||
    fail "Hermes working-directory source is not readable by its future service account: $source_file"
}
validate_synthetic_secret_contract() {
  [[ -d "$HADES_IDENTITY_SECRETS_DIR" ]] || fail "missing identity secret directory: $HADES_IDENTITY_SECRETS_DIR"
  [[ ! -L "$HADES_IDENTITY_SECRETS_DIR" ]] || fail 'identity secret directory must not be a symlink'
  for secret in jwt_secret key_seed admin_password; do
    path="$HADES_IDENTITY_SECRETS_DIR/$secret"
    [[ -f "$path" && ! -L "$path" ]] || fail "missing or linked identity secret: $path"
    [[ "$(stat -c '%a' "$path")" == 600 ]] || fail "identity secret must be mode 0600: $path"
  done
  if (( generated_records )); then validate_v2_ldap_binding; fi
  if (( ! generated_records )); then validate_secret_file HADES_HINDSIGHT_DATABASE_SECRET_FILE; fi
  validate_secret_file HADES_GROCY_API_KEY_FILE
  if (( generated_records )); then
    validate_secret_file HADES_SEARXNG_SECRET_FILE
    [[ -n "${HADES_HINDSIGHT_LLM_API_KEY:-}" && "$HADES_HINDSIGHT_LLM_API_KEY" != REQUIRED_SECRET_INPUT ]] || fail 'Hindsight LLM API key input is missing or still a placeholder'
  fi
  if [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    validate_secret_file HADES_AGENT_ZERO_CREDENTIAL_FILE
  fi
  if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
    validate_secret_file HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE
  fi
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    validate_secret_file HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE
    validate_secret_file HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE
    [[ "$(stat -c '%a' "$HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE")" == 600 && "$(stat -c '%a' "$HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE")" == 600 ]] || fail 'Operator gateway LLDAP mapping and reader password must both be mode 0600'
    command -v getfacl >/dev/null 2>&1 && command -v setfacl >/dev/null 2>&1 || fail 'Agent Zero Operator proxy requires getfacl/setfacl'
    PYTHONPATH="$repo_dir${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'from integrations.automation.phase3_lldap_authority import Phase3LldapAuthority; import sys; Phase3LldapAuthority._validate_endpoint(sys.argv[1])' "$HADES_EPSILON_PHASE3_LLDAP_URL" || fail 'HADES_EPSILON_PHASE3_LLDAP_URL must use HTTPS or local loopback HTTP'
    [[ "$HADES_AGENT_ZERO_OPERATOR_PORT" =~ ^[0-9]{1,5}$ ]] && (( HADES_AGENT_ZERO_OPERATOR_PORT >= 1 && HADES_AGENT_ZERO_OPERATOR_PORT <= 65535 )) || fail 'HADES_AGENT_ZERO_OPERATOR_PORT must be 1-65535'
    webui_bind=${HADES_OPEN_WEBUI_BIND:-127.0.0.1:3000}
    [[ "$webui_bind" =~ ^(127\.0\.0\.1|localhost):([0-9]{1,5})$ ]] || fail 'Agent Zero Operator proxy requires a loopback HADES_OPEN_WEBUI_BIND'
    webui_upstream_port=$((${webui_bind##*:} + 1))
    (( webui_upstream_port <= 65535 && HADES_AGENT_ZERO_OPERATOR_PORT != ${webui_bind##*:} && HADES_AGENT_ZERO_OPERATOR_PORT != webui_upstream_port && HADES_AGENT_ZERO_OPERATOR_PORT != 7002 && HADES_AGENT_ZERO_OPERATOR_PORT != 8645 && ${webui_bind##*:} != 8645 && webui_upstream_port != 8645 )) || fail 'Agent Zero Operator proxy ports overlap or exceed the valid range'
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
  bash "$repo_dir/scripts/secure-agent-zero-workspace.sh" hades-agent-zero || fail 'Agent Zero private workspace secret permissions are unsafe'
  systemctl is-active --quiet hades-hermes.service || fail 'deployed Hermes service is not active'
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    systemctl is-active --quiet hades-agent-zero-operator-auth.service || fail 'Agent Zero Operator auth service is not active'
    docker inspect -f '{{.State.Status}}' hades-agent-zero-operator-proxy 2>/dev/null | grep -Fxq running || fail 'Agent Zero Operator proxy container is not running'
    auth_ready=0
    for _ in {1..30}; do
      if curl --fail --silent --output /dev/null --max-time 3 http://127.0.0.1:8645/health; then auth_ready=1; break; fi
      sleep 1
    done
    ((auth_ready)) || fail 'Agent Zero Operator auth health endpoint is unavailable'
    unauth_status=$(curl --silent --output /dev/null --max-time 3 --write-out '%{http_code}' "http://127.0.0.1:$HADES_AGENT_ZERO_OPERATOR_PORT/" || true)
    [[ "$unauth_status" == 401 ]] || fail "Agent Zero Operator proxy did not deny unauthenticated traffic (HTTP ${unauth_status:-unavailable})"
  fi
}
preflight() {
  tracked_sources=(
    config/versions.env
    config/reconstruction-manifest.json
    hermes/config.yaml.example
    hermes/env.example
    hermes/sitecustomize.py
    integrations/grocy-mcp/launch.py
    integrations/grocy-mcp/requirements.lock
    scripts/install-grocy-mcp.sh
    scripts/check-grocy-mcp-runtime.py
    integrations/grocy-recipe-authoring/server.py
    integrations/agent-zero-mcp/server.py
    integrations/public-research/server.py
    integrations/public-research/research.py
    webui/hades-theme.css
    webui/hades-theme.js
    webui/finance-upload.js
    webui/receipt-upload.js
    webui/task_notification_compat.py
    deploy/lldap.compose.yaml
    deploy/grocy.compose.yaml
    deploy/agent-zero.compose.yaml
    scripts/secure-agent-zero-workspace.sh
    scripts/sync-agent-zero-client-auth.sh
    scripts/synthetic-deployment-target.sh
  )
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    tracked_sources+=(
      deploy/templates/agent-zero-operator.nginx.conf.in
      deploy/templates/agent-zero-operator-proxy.compose.yaml
      deploy/templates/agent-zero-operator-auth.service.in
      integrations/operator-access/proxy_auth_server.py
      integrations/operator-access/session_auth.py
      integrations/automation/phase3_lldap_authority.py
      integrations/automation/phase3_self_service.py
    )
  fi
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
  architecture=$(uname -m)
  [[ "$architecture" == x86_64 || "$architecture" == aarch64 ]] || fail "unsupported architecture: $architecture"
  if [[ "$architecture" == x86_64 ]]; then
    loader=/lib64/ld-linux-x86-64.so.2
    [[ -x "$loader" ]] || fail 'cannot verify x86-64-v2 CPU support; the pinned Open WebUI runtime requires x86-64-v2'
    "$loader" --help 2>/dev/null | grep -Fq 'x86-64-v2 (supported' || fail 'CPU must support x86-64-v2 for the pinned Open WebUI runtime; configure VMs with a host-passthrough CPU'
  fi
  need_cmd systemctl; need_cmd curl; need_cmd git; need_cmd openssl; need_cmd docker; need_cmd ss; need_cmd nproc
  docker compose version >/dev/null 2>&1 || fail 'missing Docker Compose plugin'
  systemctl --version >/dev/null 2>&1 || fail 'systemd is unavailable'
  if (( generated_records )); then
    [[ -x "$HADES_HERMES_EXECUTABLE" ]] || fail "Hermes artifact is missing or not executable: $HADES_HERMES_EXECUTABLE; install the pinned source with scripts/install-hermes-artifact.sh"
    installed_hermes_version=$("$HADES_HERMES_EXECUTABLE" --version 2>&1) || fail 'Hermes artifact could not report its version'
    grep -Fq "${HADES_HERMES_VERSION}" <<<"$installed_hermes_version" || fail "Hermes artifact version does not match config/versions.env (${HADES_HERMES_VERSION})"
  fi
  cpu_count=$(nproc --all 2>/dev/null || true)
  [[ "$cpu_count" =~ ^[0-9]+$ && "$cpu_count" -ge 2 ]] || fail 'at least 2 CPU cores are required'
  memory_kb=$(awk '/^MemTotal:/ {print $2; exit}' /proc/meminfo)
  [[ "$memory_kb" =~ ^[0-9]+$ && "$memory_kb" -ge 8388608 ]] || fail 'at least 8 GiB RAM is required'
  available_kb=$(df -Pk / | awk 'NR == 2 {print $4}')
  [[ "$available_kb" =~ ^[0-9]+$ ]] || fail 'could not determine free disk on the root filesystem'
  required_disk_kb=41943040
  images_to_check=("$HADES_LLDAP_IMAGE" "$HADES_HINDSIGHT_IMAGE" "$HADES_GROCY_IMAGE" "$HADES_AGENT_ZERO_IMAGE" "$HADES_SEARXNG_IMAGE_RECORD" "${HADES_OPEN_WEBUI_IMAGE:-}")
  all_pinned_images_cached=1
  for image in "${images_to_check[@]}"; do
    [[ -n "$image" ]] || continue
    docker image inspect "$image" >/dev/null 2>&1 || { all_pinned_images_cached=0; break; }
  done
  if (( all_pinned_images_cached )); then required_disk_kb=8388608; fi
  [[ "$available_kb" -ge "$required_disk_kb" ]] || fail "insufficient free disk on root filesystem (available ${available_kb} KiB; required ${required_disk_kb} KiB; cached pinned images: $((all_pinned_images_cached)))"
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
  validate_hermes_profile_parent
  validate_hermes_working_directory
  perms=$(stat -c '%a' "$inputs"); [[ "$perms" == 600 || "$perms" == 640 ]] || fail "operator input file must be mode 0600 or 0640: $inputs"
  [[ "$HADES_HERMES_API_KEY" != REQUIRED_OPERATOR_INPUT ]] || fail 'required operator input is still a placeholder'
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
  if (( generated_records )); then validate_v2_ldap_binding; fi
  if (( ! generated_records )); then validate_secret_file HADES_HINDSIGHT_DATABASE_SECRET_FILE; fi
  validate_secret_file HADES_GROCY_API_KEY_FILE
  if [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    validate_secret_file HADES_AGENT_ZERO_CREDENTIAL_FILE
  fi
  if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
    validate_secret_file HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE
  fi
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    validate_secret_file HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE
    validate_secret_file HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE
    [[ "$(stat -c '%a' "$HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE")" == 600 && "$(stat -c '%a' "$HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE")" == 600 ]] || fail 'Operator gateway LLDAP mapping and reader password must both be mode 0600'
    command -v getfacl >/dev/null 2>&1 && command -v setfacl >/dev/null 2>&1 || fail 'Agent Zero Operator proxy requires getfacl/setfacl'
    PYTHONPATH="$repo_dir${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'from integrations.automation.phase3_lldap_authority import Phase3LldapAuthority; import sys; Phase3LldapAuthority._validate_endpoint(sys.argv[1])' "$HADES_EPSILON_PHASE3_LLDAP_URL" || fail 'HADES_EPSILON_PHASE3_LLDAP_URL must use HTTPS or local loopback HTTP'
    [[ "$HADES_AGENT_ZERO_OPERATOR_PORT" =~ ^[0-9]{1,5}$ ]] && (( HADES_AGENT_ZERO_OPERATOR_PORT >= 1 && HADES_AGENT_ZERO_OPERATOR_PORT <= 65535 )) || fail 'HADES_AGENT_ZERO_OPERATOR_PORT must be 1-65535'
    webui_bind=${HADES_OPEN_WEBUI_BIND:-127.0.0.1:3000}
    [[ "$webui_bind" =~ ^(127\.0\.0\.1|localhost):([0-9]{1,5})$ ]] || fail 'Agent Zero Operator proxy requires a loopback HADES_OPEN_WEBUI_BIND'
    webui_upstream_port=$((${webui_bind##*:} + 1))
    (( webui_upstream_port <= 65535 && HADES_AGENT_ZERO_OPERATOR_PORT != ${webui_bind##*:} && HADES_AGENT_ZERO_OPERATOR_PORT != webui_upstream_port && HADES_AGENT_ZERO_OPERATOR_PORT != 7002 && HADES_AGENT_ZERO_OPERATOR_PORT != 8645 && ${webui_bind##*:} != 8645 && webui_upstream_port != 8645 )) || fail 'Agent Zero Operator proxy ports overlap or exceed the valid range'
    for port in "$webui_upstream_port" "$HADES_AGENT_ZERO_OPERATOR_PORT" 8645; do
      if ss -ltn "sport = :$port" | awk 'NR > 1 {found=1} END {exit !found}'; then
        owned=0
        case "$port" in
          "$webui_upstream_port") [[ "$(docker inspect -f '{{.State.Status}}' hades-open-webui 2>/dev/null || true)" == running ]] && owned=1 ;;
          "$HADES_AGENT_ZERO_OPERATOR_PORT") docker ps -a --format '{{.Names}}' | grep -Fxq hades-agent-zero-operator-proxy && owned=1 ;;
          8645) systemctl is-active --quiet hades-agent-zero-operator-auth.service 2>/dev/null && owned=1 ;;
        esac
        ((owned)) || fail "Agent Zero Operator proxy port is occupied by an unrelated process: $port"
      fi
    done
  fi
  if (( ! generated_records )); then
    validate_private_records
  else
    for template in open-webui.compose.yaml hindsight.compose.yaml searxng.compose.yaml hermes.service.in; do
      [[ -f "$repo_dir/deploy/templates/$template" ]] || fail "missing tracked deployment template: $template"
    done
  fi
  echo 'PASS supported host preflight'
}
preflight
if ((preflight_only)); then exit 0; fi
if (( !test_mode )); then
  if ! getent group "$HADES_HERMES_RUNTIME_GROUP" >/dev/null; then groupadd --system "$HADES_HERMES_RUNTIME_GROUP"; fi
  if id "$HADES_HERMES_RUNTIME_USER" >/dev/null 2>&1; then
    [[ "$(id -gn "$HADES_HERMES_RUNTIME_USER")" == "$HADES_HERMES_RUNTIME_GROUP" ]] || fail 'existing Hermes runtime user has an unexpected primary group'
  else
    useradd --system --gid "$HADES_HERMES_RUNTIME_GROUP" --no-create-home --home-dir "$HADES_HERMES_PROFILE" --shell /usr/sbin/nologin "$HADES_HERMES_RUNTIME_USER"
  fi
  [[ ! -L "$HADES_HERMES_PROFILE" ]] || fail 'Hermes profile must not be a symlink'
  install -d -o "$HADES_HERMES_RUNTIME_USER" -g "$HADES_HERMES_RUNTIME_GROUP" -m 0700 "$HADES_HERMES_PROFILE"
  chown -R "$HADES_HERMES_RUNTIME_USER:$HADES_HERMES_RUNTIME_GROUP" "$HADES_HERMES_PROFILE"
  find "$HADES_HERMES_PROFILE" -type d -exec chmod 0700 {} +
  find "$HADES_HERMES_PROFILE" -type f -exec chmod go-rwx {} +
  webui_secret_dir=$(dirname "$HADES_OPEN_WEBUI_SECRET_SOURCE")
  install -d -m 0700 "$webui_secret_dir"
  [[ ! -L "$HADES_OPEN_WEBUI_SECRET_SOURCE" ]] || fail 'Open WebUI secret must not be a symlink'
  if [[ -e "$HADES_OPEN_WEBUI_SECRET_SOURCE" ]]; then
    [[ -f "$HADES_OPEN_WEBUI_SECRET_SOURCE" && "$(stat -c '%a' "$HADES_OPEN_WEBUI_SECRET_SOURCE")" == 600 ]] || fail 'Open WebUI secret must be a regular file with mode 0600'
  else
    secret_tmp=$(mktemp "$webui_secret_dir/.open-webui-secret.XXXXXX")
    chmod 0600 "$secret_tmp"
    openssl rand -hex 32 > "$secret_tmp"
    mv -n "$secret_tmp" "$HADES_OPEN_WEBUI_SECRET_SOURCE"
    rm -f "$secret_tmp"
  fi
fi
if (( generated_records && ! test_mode )); then
  [[ "$root" == / ]] || fail 'operator input contract v2 generated records require the real target root'
  mkdir -p "$HADES_CONFIG_ROOT/searxng" "$HADES_OPEN_WEBUI_DATA" "$HADES_HINDSIGHT_DATA" "$HADES_SEARXNG_DATA"
  [[ "$HADES_HINDSIGHT_DATA" != / && ! -L "$HADES_HINDSIGHT_DATA" ]] || fail 'Hindsight state path must be a non-root regular directory path'
  # Hindsight is rootless (UID 1000); bind-mounted state must be writable by
  # that service account on a fresh host and after a rerun.
  chown -R 1000:1000 "$HADES_HINDSIGHT_DATA"
  bash "$repo_dir/scripts/render-deployment-records.sh" "$inputs" "$HADES_DEPLOYMENT_DIR" >/dev/null
  owner_policy_record="$HADES_DEPLOYMENT_DIR/hades-owner-policy.env"
  if [[ -n "${HADES_OWNER_SUBJECT_IDS:-}" ]]; then
    chown root:"$HADES_HERMES_RUNTIME_GROUP" "$owner_policy_record"
    chmod 0640 "$owner_policy_record"
  fi
  if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
    compose_cmd+=(--env-file "$HADES_DEPLOYMENT_DIR/agent-zero-operator-proxy.env")
  fi
  validate_private_records
fi
if ((test_mode)); then
  config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
  mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
  profile_root=$(under_root "$HADES_HERMES_PROFILE")
  install -d -m 0700 "$profile_root"
  [[ -e "$profile_root/config.yaml" ]] || install -m 0600 "$repo_dir/hermes/config.yaml.example" "$profile_root/config.yaml"
  [[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
  install -m 0644 "$repo_dir/config/reconstruction-manifest.json" "$config_root/reconstruction-manifest.json"
  [[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
  [[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
  install -d -m 0750 "$state_root/runtime" "$state_root/compose"
  install -d -m 0750 "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
  install -m 0644 "$repo_dir/hermes/sitecustomize.py" "$config_root/overlay/sitecustomize.py"
  install -m 0644 "$repo_dir/integrations/homelab_views.py" "$config_root/overlay/homelab_views.py"
  install -m 0644 "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$config_root/adapters/grocy-recipe-authoring.py"
  install -m 0644 "$repo_dir/integrations/agent-zero-mcp/server.py" "$config_root/adapters/agent-zero-mcp.py"
  install -m 0644 "$repo_dir/webui/hades-theme.css" "$config_root/assets/hades-theme.css"
  install -m 0644 "$repo_dir/webui/hades-theme.js" "$config_root/assets/hades-theme.js"
  install -m 0644 "$repo_dir/webui/finance-upload.js" "$config_root/assets/finance-upload.js"
  install -m 0644 "$repo_dir/webui/receipt-upload.js" "$config_root/assets/receipt-upload.js"
  install -m 0644 "$repo_dir/integrations/grocy-mcp/launch.py" "$config_root/adapters/grocy-mcp-launch.py"
  {
    printf 'manifest=%s\nreconstruction_manifest=%s\nlayer=%s\ninstalled_from=%s\n' \
      "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" \
      "$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')" \
      "$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/homelab_views.py" "$repo_dir/integrations/grocy-mcp/launch.py" "$repo_dir/integrations/grocy-mcp/requirements.lock" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js" "$repo_dir/webui/finance-upload.js" "$repo_dir/webui/receipt-upload.js")" \
      "$repo_dir"
    source_provenance_records
    printf 'phase=prepared\n'
  } > "$state_root/install-contract"
  chmod 0640 "$state_root/install-contract"
  if [[ "${HADES_TEST_FAIL_AFTER_PREPARE:-0}" == 1 ]]; then
    echo 'FAIL synthetic injected interruption after preparation' >&2
    exit 97
  fi
  echo 'PASS test-mode installation contract (no containers, no fixture data)'
  exit 0
fi
if (( !test_mode )); then
  bash "$repo_dir/scripts/install-grocy-mcp.sh"
fi
ensure_shared_network hades-application-net
ensure_shared_network hades-private
ensure_shared_network hades-grocy-net
config_root=$(under_root "$HADES_CONFIG_ROOT"); state_root=$(under_root "$HADES_STATE_ROOT"); backup_root=$(under_root "$HADES_BACKUP_ROOT")
mkdir -p "$config_root" "$state_root" "$backup_root"; chmod 0750 "$config_root" "$state_root" "$backup_root"
[[ -e "$config_root/versions.env" ]] || install -m 0644 "$repo_dir/config/versions.env" "$config_root/versions.env"
install -m 0644 "$repo_dir/config/reconstruction-manifest.json" "$config_root/reconstruction-manifest.json"
[[ -e "$config_root/hermes-config.yaml" ]] || install -m 0644 "$repo_dir/hermes/config.yaml.example" "$config_root/hermes-config.yaml"
[[ -e "$config_root/hermes.env.example" ]] || install -m 0644 "$repo_dir/hermes/env.example" "$config_root/hermes.env.example"
install -d -m 0750 "$state_root/runtime" "$state_root/compose"
install -d -m 0750 "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
install -m 0644 "$repo_dir/hermes/sitecustomize.py" "$config_root/overlay/sitecustomize.py"
install -m 0644 "$repo_dir/integrations/homelab_views.py" "$config_root/overlay/homelab_views.py"
install -m 0644 "$repo_dir/integrations/grocy-mcp/launch.py" "$config_root/adapters/grocy-mcp-launch.py"
install -m 0644 "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$config_root/adapters/grocy-recipe-authoring.py"
install -m 0644 "$repo_dir/integrations/agent-zero-mcp/server.py" "$config_root/adapters/agent-zero-mcp.py"
install -m 0644 "$repo_dir/webui/hades-theme.css" "$config_root/assets/hades-theme.css"
install -m 0644 "$repo_dir/webui/hades-theme.js" "$config_root/assets/hades-theme.js"
install -m 0644 "$repo_dir/webui/finance-upload.js" "$config_root/assets/finance-upload.js"
install -m 0644 "$repo_dir/webui/receipt-upload.js" "$config_root/assets/receipt-upload.js"
runtime_secret_dir="$config_root/secrets"
install -d -o root -g "$HADES_HERMES_RUNTIME_GROUP" -m 0750 "$runtime_secret_dir"
runtime_grocy_key="$runtime_secret_dir/grocy-api-key"
key_hash=$(sha256sum "$HADES_GROCY_API_KEY_FILE" | awk '{print $1}')
current_key_hash=''
if [[ -e "$runtime_grocy_key" || -L "$runtime_grocy_key" ]]; then
  [[ -f "$runtime_grocy_key" && ! -L "$runtime_grocy_key" ]] || fail 'installed Grocy API key path is not a regular file'
  current_key_hash=$(sha256sum "$runtime_grocy_key" | awk '{print $1}')
fi
if [[ "$current_key_hash" != "$key_hash" ]]; then
  key_tmp=$(mktemp "$runtime_secret_dir/.grocy-api-key.XXXXXX")
  chmod 0600 "$key_tmp"
  if ! cat -- "$HADES_GROCY_API_KEY_FILE" > "$key_tmp"; then rm -f -- "$key_tmp"; fail 'could not prepare Hermes-readable Grocy API key'; fi
  chown root:"$HADES_HERMES_RUNTIME_GROUP" "$key_tmp"
  chmod 0640 "$key_tmp"
  mv -f -- "$key_tmp" "$runtime_grocy_key"
fi
chown root:"$HADES_HERMES_RUNTIME_GROUP" "$runtime_grocy_key"
chmod 0640 "$runtime_grocy_key"
chgrp -R "$HADES_HERMES_RUNTIME_GROUP" "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
chgrp "$HADES_HERMES_RUNTIME_GROUP" "$config_root"
chmod 0750 "$config_root" "$config_root/overlay" "$config_root/adapters" "$config_root/assets"
find "$config_root/overlay" "$config_root/adapters" "$config_root/assets" -type f -exec chmod 0640 {} +
{
  printf 'manifest=%s\nreconstruction_manifest=%s\nlayer=%s\ninstalled_from=%s\n' \
    "$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')" \
    "$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')" \
    "$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/homelab_views.py" "$repo_dir/integrations/grocy-mcp/launch.py" "$repo_dir/integrations/grocy-mcp/requirements.lock" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js" "$repo_dir/webui/finance-upload.js" "$repo_dir/webui/receipt-upload.js")" \
    "$repo_dir"
  source_provenance_records
  printf 'phase=prepared\n'
} > "$state_root/install-contract"
if ((synthetic_deployment_test)); then printf 'synthetic_deployment_test=true\n' >> "$state_root/install-contract"; fi
chmod 0640 "$state_root/install-contract"
export HADES_IDENTITY_SECRETS_DIR
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" != true ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl stop hades-agent-zero-operator-auth.service 2>/dev/null || true
    systemctl disable hades-agent-zero-operator-auth.service 2>/dev/null || true
  fi
  if [[ "$root" == / ]]; then
    rm -f /etc/systemd/system/hades-agent-zero-operator-auth.service
    rm -f "$HADES_CONFIG_ROOT/operator-proxy/phase3-authority.json" "$HADES_CONFIG_ROOT/operator-proxy/lldap-reader-password" "$HADES_CONFIG_ROOT/operator-proxy/auth.env"
    acl_marker="$HADES_CONFIG_ROOT/operator-proxy/config-root-acl-original"
    if [[ -f "$acl_marker" && ! -L "$acl_marker" ]]; then
      IFS=: read -r acl_uid acl_previous < "$acl_marker"
      if [[ "$acl_previous" == none ]]; then setfacl -x "u:$acl_uid" "$HADES_CONFIG_ROOT" 2>/dev/null || true
      else setfacl -m "u:$acl_uid:$acl_previous" "$HADES_CONFIG_ROOT"; fi
      rm -f "$acl_marker"
    fi
    systemctl daemon-reload
  fi
  if command -v docker >/dev/null 2>&1; then docker rm -f hades-agent-zero-operator-proxy >/dev/null 2>&1 || true; fi
fi
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
if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
  bash "$repo_dir/scripts/sync-agent-zero-client-auth.sh" "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
  chgrp "$HADES_HERMES_RUNTIME_GROUP" "$HADES_DEPLOYMENT_DIR"
  chmod 0710 "$HADES_DEPLOYMENT_DIR"
  chgrp "$HADES_HERMES_RUNTIME_GROUP" "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
  chmod 0640 "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
else
  rm -f "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
fi
"${compose_cmd[@]}" -f "$HADES_SEARXNG_COMPOSE_FILE" up -d
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
  install -m 0600 "$HADES_DEPLOYMENT_DIR/agent-zero-operator-auth.service" /etc/systemd/system/hades-agent-zero-operator-auth.service
  SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system systemd-analyze verify "$HADES_DEPLOYMENT_DIR/agent-zero-operator-auth.service" || fail 'invalid Agent Zero Operator auth service record'
  systemctl daemon-reload
  systemctl enable hades-agent-zero-operator-auth.service
  systemctl restart hades-agent-zero-operator-auth.service
  "${compose_cmd[@]}" -f "$HADES_DEPLOYMENT_DIR/agent-zero-operator-proxy.compose.yaml" config --quiet || fail 'invalid Agent Zero Operator proxy Compose record'
  "${compose_cmd[@]}" -f "$HADES_DEPLOYMENT_DIR/agent-zero-operator-proxy.compose.yaml" up -d
fi
install -m 0600 "$HADES_HERMES_SERVICE_FILE" /etc/systemd/system/hades-hermes.service
systemctl daemon-reload
systemctl enable hades-hermes.service
systemctl restart hades-hermes.service
validate_started_runtime
printf 'phase=deployed\n' >> "$state_root/install-contract"
if ((synthetic_deployment_test)); then
  echo 'PASS full synthetic HADES deployment completed on the explicitly authorized disposable target'
else
  echo 'PASS HADES component deployment completed from tracked contracts and explicit private records'
fi
