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
    -h|--help) echo 'usage: hades-doctor.sh [--inputs FILE] [--root DIR] [--test-mode | --synthetic-deployment-test]'; exit 0 ;;
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
if ((synthetic_deployment_test && test_mode)); then echo 'FAIL full synthetic deployment checks cannot be combined with --test-mode' >&2; exit 2; fi
if ((synthetic_deployment_test)) && [[ "$root" != / ]]; then echo 'FAIL --synthetic-deployment-test checks the authorized machine root only' >&2; exit 2; fi
if ((synthetic_deployment_test)) && [[ -z "$inputs" ]]; then echo 'FAIL --synthetic-deployment-test requires explicit synthetic inputs' >&2; exit 2; fi
# The repository manifest is authoritative; operator inputs cannot override pins.
source "$repo_dir/config/versions.env"
[[ "${HADES_MANIFEST_VERSION:-}" == 1 ]] || { echo 'FAIL unsupported authoritative manifest version; expected version 1'; exit 1; }
if [[ -n "$inputs" ]]; then
  [[ "${HADES_INPUTS_VERSION:-}" == 1 || "${HADES_INPUTS_VERSION:-}" == 2 ]] || { echo 'FAIL unsupported operator input contract version; expected version 1 or 2'; exit 1; }
  if [[ "${HADES_SYNTHETIC_FIXTURE:-false}" == true && "$test_mode" != 1 ]]; then
    if (( ! synthetic_deployment_test )); then
      echo 'FAIL synthetic fixture inputs are test-only and cannot be used for production diagnosis' >&2; exit 1
    fi
    bash "$repo_dir/scripts/synthetic-deployment-target.sh" verify
    [[ "${HADES_INPUTS_VERSION:-}" == 2 ]] || { echo 'FAIL full synthetic deployment checks require operator input contract v2' >&2; exit 1; }
  elif ((synthetic_deployment_test)); then
    echo 'FAIL --synthetic-deployment-test requires HADES_SYNTHETIC_FIXTURE=true inputs' >&2; exit 1
  fi
  if [[ "$HADES_INPUTS_VERSION" == 2 ]]; then
    HADES_DEPLOYMENT_DIR=${HADES_DEPLOYMENT_DIR:-$HADES_CONFIG_ROOT/private-deployment}
    HADES_OPEN_WEBUI_COMPOSE_FILE=${HADES_OPEN_WEBUI_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/open-webui.compose.yaml}
    HADES_HINDSIGHT_COMPOSE_FILE=${HADES_HINDSIGHT_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/hindsight.compose.yaml}
    HADES_SEARXNG_COMPOSE_FILE=${HADES_SEARXNG_COMPOSE_FILE:-$HADES_DEPLOYMENT_DIR/searxng.compose.yaml}
    HADES_HERMES_SERVICE_FILE=${HADES_HERMES_SERVICE_FILE:-$HADES_DEPLOYMENT_DIR/hermes.service}
    HADES_AGENT_ZERO_CLIENT_ENV_FILE="$HADES_DEPLOYMENT_DIR/agent-zero-client-auth.env"
  fi
  if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
    [[ "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE" == /* ]] || { echo 'FAIL Agent Zero Operator password path must be absolute'; exit 1; }
    HADES_AGENT_ZERO_AUTH_ENV_FILE="$HADES_DEPLOYMENT_DIR/agent-zero-operator-auth.env"
    export HADES_AGENT_ZERO_AUTH_ENV_FILE
  fi
  for name in HADES_STATE_ROOT HADES_CONFIG_ROOT HADES_BACKUP_ROOT HADES_IDENTITY_SECRETS_DIR HADES_DEPLOYMENT_DIR HADES_HERMES_PROFILE; do
    [[ "${!name:-}" == /* ]] || { echo "FAIL operator input path must be absolute: $name"; exit 1; }
  done
fi
if [[ -n "${HADES_DEPLOYMENT_DIR:-}" ]]; then
  HADES_AGENT_ZERO_CLIENT_ENV_FILE=${HADES_AGENT_ZERO_CLIENT_ENV_FILE:-$HADES_DEPLOYMENT_DIR/agent-zero-client-auth.env}
fi
HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=${HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED:-false}
HADES_AGENT_ZERO_OPERATOR_PORT=${HADES_AGENT_ZERO_OPERATOR_PORT:-7004}
export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD HADES_NGINX_IMAGE
export HADES_IDENTITY_SECRETS_DIR
hades_layer_digest() {
  sha256sum "$@" | awk '{print $1}' | sha256sum | awk '{print $1}'
}
check_homelab_runtime_package() {
  local path=${HADES_HERMES_WORKING_DIRECTORY:-} package_root expected_modules runtime_modules module
  local source_path source_mode active_working_directory hermes_environment environment_working_directory
  if [[ "$installed_source_verified" != 1 || -z "$path" ]]; then
    echo 'WARN homelab runtime package identity is unknown; installed source or working-directory input is unavailable'
    return 0
  fi
  if ! active_working_directory=$(systemctl show -p WorkingDirectory --value hades-hermes.service 2>/dev/null) ||
     [[ -z "$active_working_directory" ]]; then
    if ((test_mode)); then
      echo 'WARN homelab runtime package identity is unknown; active Hermes working directory is unavailable'
    else
      echo 'FAIL active Hermes working directory could not be verified'
      doctor_fail=1
    fi
    return 0
  fi
  if [[ "$active_working_directory" != "$path" ]]; then
    echo 'FAIL configured Hermes working directory differs from the active service'
    doctor_fail=1
    return 0
  fi
  hermes_environment="${HADES_HERMES_PROFILE:-}/hermes.env"
  if [[ ! -f "$hermes_environment" || -L "$hermes_environment" || ! -r "$hermes_environment" ]]; then
    if ((test_mode)); then
      echo 'WARN homelab runtime package identity is unknown; Hermes profile environment is unavailable'
    else
      echo 'FAIL Hermes profile environment cannot be verified'
      doctor_fail=1
    fi
    return 0
  fi
  environment_working_directory=$(sed -n 's/^HADES_HERMES_WORKING_DIRECTORY=//p' "$hermes_environment")
  if [[ "$environment_working_directory" != "$path" ]]; then
    echo 'FAIL Hermes profile environment working directory differs from the active service'
    doctor_fail=1
    return 0
  fi
  echo 'PASS active Hermes working directory matches operator input'
  package_root="$path/integrations/homelab-readonly"
  if [[ "$path" != /* || -L "$path" || ! -d "$path" ||
        -L "$path/integrations" || ! -d "$path/integrations" ||
        -L "$package_root" || ! -d "$package_root" ]]; then
    echo 'FAIL Hermes homelab runtime package is missing or has an unsafe path'
    doctor_fail=1
    return 0
  fi
  if [[ -n "$(find "$package_root" -type l -print -quit 2>/dev/null)" ||
        -n "$(find "$package_root" -name '*.py' ! -type f -print -quit 2>/dev/null)" ]]; then
    echo 'FAIL Hermes homelab runtime package contains a symlink or non-regular Python module'
    doctor_fail=1
    return 0
  fi
  expected_modules=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" \
    ls-tree -r --name-only "$installed_source_revision" -- integrations/homelab-readonly 2>/dev/null |
    sed -n '/\.py$/s@^integrations/homelab-readonly/@@p' | LC_ALL=C sort) || {
      echo 'FAIL Hermes homelab package source membership cannot be read from the installed revision'
      doctor_fail=1
      return 0
    }
  runtime_modules=$(find "$package_root" -type f -name '*.py' -printf '%P\n' 2>/dev/null | LC_ALL=C sort) || {
    echo 'FAIL Hermes homelab runtime package cannot be inspected'
    doctor_fail=1
    return 0
  }
  if [[ -z "$expected_modules" || "$expected_modules" != "$runtime_modules" ]] ||
     ! grep -Fxq 'server.py' <<<"$expected_modules"; then
    echo 'FAIL Hermes homelab runtime package module set differs from the installed source revision'
    doctor_fail=1
    return 0
  fi
  while IFS= read -r module; do
    source_path="integrations/homelab-readonly/$module"
    source_mode=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" \
      ls-tree "$installed_source_revision" -- "$source_path" 2>/dev/null | awk '{print $1}') || source_mode=''
    if [[ "$source_mode" != 100644 && "$source_mode" != 100755 ]] ||
       ! git -c "safe.directory=$repo_dir" -C "$repo_dir" \
         show "$installed_source_revision:$source_path" 2>/dev/null |
         cmp -s - "$package_root/$module"; then
      echo 'FAIL Hermes homelab runtime package differs from the installed source revision'
      doctor_fail=1
      return 0
    fi
  done <<<"$expected_modules"
  echo 'PASS Hermes homelab runtime package matches the installed source revision'
}
compose_cmd=(docker compose)
[[ -n "$inputs" ]] && compose_cmd+=(--env-file "$inputs")
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
  proxy_env="${HADES_DEPLOYMENT_DIR:-${HADES_CONFIG_ROOT:-/etc/hades}/private-deployment}/agent-zero-operator-proxy.env"
  if [[ -f "$proxy_env" && ! -L "$proxy_env" ]]; then compose_cmd+=(--env-file "$proxy_env"); fi
fi
check_compose_boundaries() {
  local record
  local records=("$repo_dir"/deploy/*.compose.yaml)
  if [[ -n "${HADES_DEPLOYMENT_DIR:-}" && -d "${HADES_DEPLOYMENT_DIR:-}" ]]; then
    records+=("$HADES_OPEN_WEBUI_COMPOSE_FILE" "$HADES_HINDSIGHT_COMPOSE_FILE" "$HADES_SEARXNG_COMPOSE_FILE")
    if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
      records+=("$HADES_DEPLOYMENT_DIR/agent-zero-operator-proxy.compose.yaml")
    fi
  fi
  for record in "${records[@]}"; do
    [[ -f "$record" ]] || continue
    if grep -Eq '(^|[[:space:]])privileged:[[:space:]]*true([[:space:]]|$)' "$record"; then
      echo "FAIL authority-amplifying Compose setting: $record"
      doctor_fail=1
    fi
    if grep -Eq '(^|[[:space:]])network_mode:[[:space:]]*host([[:space:]]|$)' "$record"; then
      if [[ "$record" == *agent-zero-operator-proxy.compose.yaml ]] && \
        grep -Fq 'user: "101:101"' "$record" && grep -Fq 'cap_drop:' "$record" && \
        grep -Fq -- '- ALL' "$record" && ! grep -Fq 'privileged: true' "$record" && \
        grep -Fq '127.0.0.1:' "${HADES_CONFIG_ROOT:-/etc/hades}/operator-proxy/nginx.conf" 2>/dev/null; then
        echo 'PASS Operator gateway host networking is restricted by loopback listeners and dropped capabilities'
      else
        echo "FAIL authority-amplifying Compose setting: $record"
        doctor_fail=1
      fi
    fi
    if grep -Eq '/var/run/docker\.sock|(^|[[:space:]])-?[[:space:]]*/:/[[:space:]]|(^|[[:space:]])-?[[:space:]]*-[[:space:]]*:/host([[:space:]]|$)' "$record"; then
      echo "FAIL broad host or Docker-socket mount: $record"
      doctor_fail=1
    fi
    case "$record" in
      *hindsight*|*searxng*|*grocy*|*agent-zero*|*lldap*)
        if grep -Eq '0\.0\.0\.0:' "$record"; then
          echo "WARN private service has an all-interface port binding: $record"
        fi
        ;;
    esac
  done
}
config_root="${root%/}${HADES_CONFIG_ROOT:-/etc/hades}"
state="${root%/}${HADES_STATE_ROOT:-/var/lib/hades}/install-contract"
doctor_fail=0
installed_source_verified=0
owner_policy_record="${root%/}${HADES_DEPLOYMENT_DIR:-${HADES_CONFIG_ROOT:-/etc/hades}/private-deployment}/hades-owner-policy.env"
if [[ -n "${HADES_OWNER_SUBJECT_IDS:-}" ]]; then
  owner_policy_stat=$(stat -c '%u:%g:%a' "$owner_policy_record" 2>/dev/null || true)
  expected_gid=$(getent group "${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}" | cut -d: -f3)
  if [[ -f "$owner_policy_record" && ! -L "$owner_policy_record" && "$owner_policy_stat" == "0:$expected_gid:640" && "$(wc -l < "$owner_policy_record")" == 1 ]] &&
    grep -Fxq "HADES_OWNER_SUBJECT_IDS=$HADES_OWNER_SUBJECT_IDS" "$owner_policy_record"; then
    echo 'PASS explicit owner subject policy record and permissions'
  else
    echo 'FAIL explicit owner subject policy record is missing, stale, or unsafe'
    doctor_fail=1
  fi
elif [[ -e "$owner_policy_record" || -L "$owner_policy_record" ]]; then
  echo 'FAIL unexpected owner subject policy record exists while the input is empty'
  doctor_fail=1
fi
if [[ -n "$inputs" && "${HADES_INPUTS_VERSION:-}" == 2 ]]; then
  research_policy_found=0
  for integration_root in "${HADES_INTEGRATIONS_ROOT:-}" "${HADES_HERMES_WORKING_DIRECTORY:-}"; do
    [[ -n "$integration_root" ]] || continue
    policy_file="$integration_root/integrations/public-research/research.py"
    if [[ -f "$policy_file" && ! -L "$policy_file" && -r "$policy_file" ]]; then
      research_policy_found=1
      break
    fi
  done
  if ((research_policy_found)); then
    echo 'PASS public-research privacy policy is available from the Hermes integration root'
  else
    echo 'FAIL public-research privacy policy is missing from the Hermes integration root'
    doctor_fail=1
  fi
fi
check_compose_boundaries
check_secret_file() {
  local name=$1 path=$2
  if [[ ! -f "$path" ]]; then
    echo "FAIL $name missing"
    doctor_fail=1
  elif [[ -L "$path" ]]; then
    echo "FAIL $name is a symlink"
    doctor_fail=1
  else
    local mode
    mode=$(stat -c '%a' "$path")
    if [[ "$mode" == 600 || "$mode" == 640 ]]; then
      echo "PASS $name permissions"
    else
      echo "FAIL $name permissions=$mode"
      doctor_fail=1
    fi
  fi
}
if [[ -n "$inputs" && -d "${HADES_DEPLOYMENT_DIR:-}" ]]; then
  [[ ! -L "$HADES_IDENTITY_SECRETS_DIR" ]] && echo 'PASS identity secret directory' || { echo 'FAIL identity secret directory is a symlink'; doctor_fail=1; }
  for secret in jwt_secret key_seed admin_password; do
    path="$HADES_IDENTITY_SECRETS_DIR/$secret"
    if [[ -f "$path" && ! -L "$path" && "$(stat -c '%a' "$path")" == 600 ]]; then
      echo "PASS identity secret $secret permissions"
    else
      echo "FAIL identity secret $secret missing, linked, or not mode 0600"
      doctor_fail=1
    fi
  done
  if [[ "${HADES_INPUTS_VERSION:-1}" != 2 ]]; then
    check_secret_file 'Hindsight database secret' "$HADES_HINDSIGHT_DATABASE_SECRET_FILE"
  fi
  check_secret_file 'Grocy API key' "$HADES_GROCY_API_KEY_FILE"
  if [[ "${HADES_INPUTS_VERSION:-1}" == 2 ]]; then
    HADES_OPEN_WEBUI_SECRET_SOURCE=${HADES_OPEN_WEBUI_SECRET_SOURCE:-$HADES_STATE_ROOT/secrets/open-webui-secret}
    check_secret_file 'Open WebUI signing secret' "$HADES_OPEN_WEBUI_SECRET_SOURCE"
  fi
  if [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    check_secret_file 'Agent Zero credential' "$HADES_AGENT_ZERO_CREDENTIAL_FILE"
  fi
  if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
    check_secret_file 'Agent Zero Operator password' "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE"
    check_secret_file 'Agent Zero generated auth env' "$HADES_AGENT_ZERO_AUTH_ENV_FILE"
    if [[ -f "$HADES_AGENT_ZERO_AUTH_ENV_FILE" && -f "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE" ]]; then
      mapfile -t agent_zero_auth_lines < "$HADES_AGENT_ZERO_AUTH_ENV_FILE"
      expected_agent_zero_password=$(<"$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE")
      rendered_agent_zero_password=''
      if ((${#agent_zero_auth_lines[@]} > 1)); then
        rendered_agent_zero_password=${agent_zero_auth_lines[1]#AUTH_PASSWORD=}
      fi
      if [[ "${#agent_zero_auth_lines[@]}" == 2 && "${agent_zero_auth_lines[0]}" == 'AUTH_LOGIN=hades-operator' && "${agent_zero_auth_lines[1]}" =~ ^AUTH_PASSWORD=[A-Za-z0-9._~-]{16,256}$ && "$rendered_agent_zero_password" == "$expected_agent_zero_password" ]]; then
        echo 'PASS Agent Zero native auth configuration'
      else
        echo 'FAIL Agent Zero native auth configuration is malformed or stale'
        doctor_fail=1
      fi
      if ((test_mode)); then
        echo 'WARN Agent Zero bounded API credential is generated after runtime startup'
      else
        check_secret_file 'Agent Zero generated client auth env' "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
      fi
      if [[ -f "$HADES_AGENT_ZERO_CLIENT_ENV_FILE" && "$test_mode" == 0 ]]; then
        mapfile -t agent_zero_client_lines < "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
        runtime_agent_zero_key=$(docker exec hades-agent-zero /opt/venv-a0/bin/python -c 'import sys,os,hashlib,base64; sys.path.insert(0, "/a0"); from helpers import dotenv; dotenv.load_dotenv(); rid=os.getenv("A0_PERSISTENT_RUNTIME_ID"); login=os.getenv("AUTH_LOGIN", ""); password=os.getenv("AUTH_PASSWORD", "");
if not rid: raise SystemExit("persistent runtime ID is missing");
print(base64.urlsafe_b64encode(hashlib.sha256(f"{rid}:{login}:{password}".encode()).digest()).decode().replace("=", "")[:16])' 2>/dev/null || true)
        rendered_agent_zero_key=''
        if ((${#agent_zero_client_lines[@]} == 1)); then
          rendered_agent_zero_key=${agent_zero_client_lines[0]#AGENT_ZERO_API_KEY=}
        fi
        if [[ "${#agent_zero_client_lines[@]}" == 1 && "$rendered_agent_zero_key" =~ ^[A-Za-z0-9_-]{16}$ && "$rendered_agent_zero_key" == "$runtime_agent_zero_key" ]]; then
          echo 'PASS Agent Zero bounded API credential matches the running service'
        else
          echo 'FAIL Agent Zero bounded API credential is stale or malformed'
          doctor_fail=1
        fi
        unset runtime_agent_zero_key rendered_agent_zero_key agent_zero_client_lines
      fi
    else
      echo 'FAIL Agent Zero native auth input or generated env is missing'
      doctor_fail=1
    fi
  elif [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
    if ((test_mode)); then
      echo 'WARN Agent Zero client auth env is generated only after runtime startup'
    else
      check_secret_file 'Agent Zero generated client auth env' "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
      if [[ -f "$HADES_AGENT_ZERO_CLIENT_ENV_FILE" && -f "$HADES_AGENT_ZERO_CREDENTIAL_FILE" ]]; then
        mapfile -t agent_zero_client_lines < "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
        expected_agent_zero_key=$(<"$HADES_AGENT_ZERO_CREDENTIAL_FILE")
        if [[ "${#agent_zero_client_lines[@]}" == 1 && "${agent_zero_client_lines[0]}" == "AGENT_ZERO_API_KEY=$expected_agent_zero_key" ]]; then
          echo 'PASS Agent Zero external API credential configuration'
        else
          echo 'FAIL Agent Zero external API credential configuration is malformed or stale'
          doctor_fail=1
        fi
      else
        echo 'FAIL Agent Zero external API credential or generated env is missing'
        doctor_fail=1
      fi
    fi
  fi
elif [[ -n "$inputs" && "$test_mode" == 0 ]]; then
  echo "FAIL private deployment directory missing: ${HADES_DEPLOYMENT_DIR:-unset}"
  doctor_fail=1
fi
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
  proxy_root="$config_root/operator-proxy"
  proxy_compose="${HADES_DEPLOYMENT_DIR:-}/agent-zero-operator-proxy.compose.yaml"
  for record in "$proxy_root/nginx.conf" "$proxy_root/auth.env" "$proxy_root/phase3-authority.json" "$proxy_root/lldap-reader-password" "$proxy_compose" "${HADES_DEPLOYMENT_DIR:-}/agent-zero-operator-auth.service"; do
    [[ -f "$record" && ! -L "$record" ]] || { echo "FAIL Operator gateway record missing or linked: $record"; doctor_fail=1; }
  done
  for secret in "$proxy_root/auth.env" "$proxy_root/phase3-authority.json" "$proxy_root/lldap-reader-password"; do
    if [[ -f "$secret" && ! -L "$secret" && "$(stat -c '%a' "$secret")" == 600 ]]; then
      echo "PASS Operator gateway private input $(basename "$secret") permissions"
    else
      echo "FAIL Operator gateway private input $(basename "$secret") is missing or unsafe"
      doctor_fail=1
    fi
  done
  if [[ -f "$proxy_root/nginx.conf" ]]; then
    if grep -q "listen 127.0.0.1:$HADES_AGENT_ZERO_OPERATOR_PORT" "$proxy_root/nginx.conf" && \
      grep -q 'proxy_pass http://127.0.0.1:7002' "$proxy_root/nginx.conf" && \
      grep -q 'auth_request /__hades_operator_auth' "$proxy_root/nginx.conf" && \
      grep -q 'auth_request /__hades_cookie_filter' "$proxy_root/nginx.conf"; then
      echo 'PASS Operator gateway loopback route and request authorization configuration'
    else
      echo 'FAIL Operator gateway route, authorization, or upstream binding is incorrect'
      doctor_fail=1
    fi
  fi
  if [[ -f "$proxy_compose" ]]; then
    if "${compose_cmd[@]}" -f "$proxy_compose" config --quiet; then
      proxy_image=$("${compose_cmd[@]}" -f "$proxy_compose" config --images 2>/dev/null || true)
      [[ "$proxy_image" == "$HADES_NGINX_IMAGE" ]] && echo 'PASS Operator gateway immutable image pin' || { echo 'FAIL Operator gateway image pin differs from config/versions.env'; doctor_fail=1; }
    else
      echo 'FAIL Operator gateway Compose configuration is invalid'
      doctor_fail=1
    fi
  fi
  if ((test_mode)); then
    echo 'WARN live Operator gateway service and listener checks skipped in test mode'
  else
    systemctl is-active --quiet hades-agent-zero-operator-auth.service && echo 'PASS Operator live authorization service' || { echo 'FAIL Operator authorization service is inactive'; doctor_fail=1; }
    docker inspect -f '{{.State.Status}}' hades-agent-zero-operator-proxy 2>/dev/null | grep -Fxq running && echo 'PASS Operator gateway container' || { echo 'FAIL Operator gateway container is not running'; doctor_fail=1; }
    curl --fail --silent --output /dev/null --max-time 3 http://127.0.0.1:8645/health && echo 'PASS Operator authorization service health' || { echo 'FAIL Operator authorization service health check'; doctor_fail=1; }
    unauth_status=$(curl --silent --output /dev/null --max-time 3 --write-out '%{http_code}' "http://127.0.0.1:$HADES_AGENT_ZERO_OPERATOR_PORT/" || true)
    [[ "$unauth_status" == 401 ]] && echo 'PASS unauthenticated Operator UI request denied' || { echo "FAIL unauthenticated Operator UI status=$unauth_status"; doctor_fail=1; }
    webui_front_port=${HADES_OPEN_WEBUI_BIND:-127.0.0.1:3000}
    webui_front_port=${webui_front_port##*:}
    webui_upstream_port=$((webui_front_port + 1))
    for port in "$webui_front_port" "$webui_upstream_port" "$HADES_AGENT_ZERO_OPERATOR_PORT" 8645; do
      ss -ltnH "sport = :$port" | grep -Eq "127\.0\.0\.1:$port([[:space:]]|$)" && echo "PASS loopback listener $port" || { echo "FAIL expected loopback listener missing: $port"; doctor_fail=1; }
    done
  fi
fi
if [[ -f "$state" ]]; then
  if ((synthetic_deployment_test)); then
    grep -Fxq 'synthetic_deployment_test=true' "$state" && echo 'WARN installation uses synthetic test identities' || { echo 'FAIL install marker does not identify a synthetic test deployment'; doctor_fail=1; }
  elif grep -Fxq 'synthetic_deployment_test=true' "$state"; then
    echo 'FAIL synthetic deployment requires explicit --synthetic-deployment-test and target authorization'
    doctor_fail=1
  fi
  expected_manifest=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')
  installed_manifest=$(awk -F= '$1 == "manifest" {print $2}' "$state")
  [[ "$installed_manifest" == "$expected_manifest" ]] && echo 'PASS installation marker and manifest' || { echo 'FAIL installation marker manifest is stale'; exit 1; }
  installed_source_revision=$(awk -F= '$1 == "source_revision" {print $2}' "$state")
  installed_source_tree=$(awk -F= '$1 == "source_tree" {print $2}' "$state")
  if [[ -z "$installed_source_revision" ]]; then
    echo 'WARN installation source revision is unavailable; reinstall from a Git checkout to establish provenance'
  elif [[ "$installed_source_revision" == archive ]]; then
    if ((test_mode)); then
      echo 'WARN synthetic install source has no Git revision'
    else
      echo 'FAIL production install marker has no Git source revision'
      doctor_fail=1
    fi
  else
    current_source_revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse --verify HEAD 2>/dev/null || true)
    current_source_tree=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse 'HEAD^{tree}' 2>/dev/null || true)
    if [[ "$installed_source_revision" == "$current_source_revision" && -n "$current_source_tree" && "$installed_source_tree" == "$current_source_tree" ]]; then
      echo 'PASS installation source revision and tree'
      installed_source_verified=1
    else
      echo 'FAIL installation source revision or tree is stale'
      doctor_fail=1
    fi
  fi
  case "$(awk -F= '$1 == "source_clean" {print $2}' "$state")" in
    true) echo 'PASS installation was built from a clean source worktree' ;;
    false) echo 'WARN installation source worktree had uncommitted changes' ;;
    *) echo 'WARN installation source cleanliness was not recorded' ;;
  esac
  expected_reconstruction_manifest=$(sha256sum "$repo_dir/config/reconstruction-manifest.json" | awk '{print $1}')
  installed_reconstruction_manifest=$(awk -F= '$1 == "reconstruction_manifest" {print $2}' "$state")
  [[ "$installed_reconstruction_manifest" == "$expected_reconstruction_manifest" ]] && echo 'PASS reconstruction manifest provenance' || { echo 'FAIL reconstruction manifest provenance is stale'; exit 1; }
  expected_layer=$(hades_layer_digest "$repo_dir/hermes/sitecustomize.py" "$repo_dir/integrations/homelab_views.py" "$repo_dir/integrations/grocy-mcp/launch.py" "$repo_dir/integrations/grocy-mcp/requirements.lock" "$repo_dir/integrations/grocy-recipe-authoring/server.py" "$repo_dir/integrations/agent-zero-mcp/server.py" "$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js" "$repo_dir/webui/finance-upload.js" "$repo_dir/webui/receipt-upload.js")
  installed_layer=$(awk -F= '$1 == "layer" {print $2}' "$state")
  [[ "$installed_layer" == "$expected_layer" ]] && echo 'PASS HADES layer provenance' || { echo 'FAIL HADES layer provenance is stale'; exit 1; }
else
  echo 'WARN installation marker missing'
fi
check_homelab_runtime_package
for file in overlay/sitecustomize.py overlay/homelab_views.py adapters/grocy-mcp-launch.py adapters/grocy-recipe-authoring.py adapters/agent-zero-mcp.py assets/hades-theme.css assets/hades-theme.js assets/finance-upload.js assets/receipt-upload.js; do
  if [[ -f "$state" ]]; then
    [[ -f "$config_root/$file" ]] && echo "PASS HADES layer $file" || { echo "FAIL HADES layer missing: $file"; exit 1; }
  else
    [[ -f "$config_root/$file" ]] && echo "PASS HADES layer $file" || echo "WARN HADES layer missing: $file"
  fi
done
if [[ -f "$state" ]]; then
  [[ -f "$config_root/reconstruction-manifest.json" ]] || { echo 'FAIL reconstruction manifest missing'; exit 1; }
  [[ "$(sha256sum "$config_root/reconstruction-manifest.json" | awk '{print $1}')" == "$expected_reconstruction_manifest" ]] || { echo 'FAIL installed reconstruction manifest differs from repository'; exit 1; }
  installed_layer=$(hades_layer_digest "$config_root/overlay/sitecustomize.py" "$config_root/overlay/homelab_views.py" "$config_root/adapters/grocy-mcp-launch.py" "$repo_dir/integrations/grocy-mcp/requirements.lock" "$config_root/adapters/grocy-recipe-authoring.py" "$config_root/adapters/agent-zero-mcp.py" "$config_root/assets/hades-theme.css" "$config_root/assets/hades-theme.js" "$config_root/assets/finance-upload.js" "$config_root/assets/receipt-upload.js")
  [[ "$installed_layer" == "$expected_layer" ]] || { echo 'FAIL installed HADES layer differs from repository'; exit 1; }
  echo 'PASS reconstruction manifest'
else
  [[ -f "$config_root/reconstruction-manifest.json" ]] && echo 'PASS reconstruction manifest' || echo 'WARN reconstruction manifest missing'
fi
if [[ -n "$inputs" && -f "$inputs" ]]; then
  perms=$(stat -c '%a' "$inputs")
  [[ "$perms" == 600 || "$perms" == 640 ]] && echo 'PASS operator-input permissions' || echo "WARN operator-input permissions: $perms"
else echo 'WARN operator-input file not supplied'; fi
profile_root="$HADES_HERMES_PROFILE"
if ((test_mode)) && [[ "$root" != / ]]; then profile_root="$root/${HADES_HERMES_PROFILE#/}"; fi
if python3 "$repo_dir/scripts/check-hermes-profile-contract.py" "$profile_root/config.yaml"; then
  echo 'PASS required and classified Hermes MCP profile contract'
else
  echo 'FAIL Hermes profile is missing a required V1 registration or profile classification'
  doctor_fail=1
fi
if ((test_mode)); then (( doctor_fail == 0 )) || exit 1; echo 'PASS read-only synthetic doctor'; exit 0; fi
command -v docker >/dev/null 2>&1 && "${compose_cmd[@]}" version >/dev/null 2>&1 && echo 'PASS container runtime available' || echo 'WARN container runtime unavailable'
if command -v docker >/dev/null 2>&1; then
  for network in hades-application-net hades-private hades-grocy-net hades-identity-net; do
    network_driver=$(docker network inspect --format '{{.Driver}} {{.Scope}}' "$network" 2>/dev/null || true)
    if [[ "$network_driver" == 'bridge local' ]]; then
      echo "PASS shared network $network"
    else
      echo "FAIL shared network $network unavailable or incompatible"
      doctor_fail=1
    fi
  done
  for container in hades-lldap hades-open-webui hades-hindsight hades-grocy hades-agent-zero hades-searxng; do
    status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)
    if [[ "$status" == running ]]; then echo "PASS container $container"; else echo "FAIL container $container state=${status:-missing}"; doctor_fail=1; fi
  done
  agent_zero_workspace_env_mode=$(docker exec --user 0 hades-agent-zero stat -c '%a' /a0/usr/.env 2>/dev/null || true)
  if [[ "$agent_zero_workspace_env_mode" == 600 ]]; then
    echo 'PASS Agent Zero private workspace secret permissions'
  else
    echo 'FAIL Agent Zero private workspace environment file is missing or not mode 0600'
    doctor_fail=1
  fi
  if docker exec hades-open-webui python3 -c '
import json, sqlite3
db = sqlite3.connect("file:/app/backend/data/webui.db?mode=ro", uri=True, timeout=5)
row = db.execute("SELECT value FROM config WHERE key=?", ("openai.api_configs",)).fetchone()
config = json.loads(row[0]) if row else {}
headers = config.get("0", {}).get("headers", {}) if isinstance(config, dict) else {}
raise SystemExit(0 if headers.get("X-Hermes-Session-Key") == "hades-user-{{USER_ID}}" else 1)
' >/dev/null 2>&1; then
    echo 'PASS Open WebUI forwards the authenticated stable subject to Hermes'
  else
    echo 'FAIL Open WebUI Hermes connection is missing the authenticated stable-subject header'
    doctor_fail=1
  fi
  if (( !test_mode )); then
    if systemctl is-active --quiet hades-hermes.service; then echo 'PASS Hermes gateway service'; else echo 'FAIL Hermes gateway service is inactive'; doctor_fail=1; fi
    runtime_user=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
    runtime_group=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
    if id "$runtime_user" >/dev/null 2>&1 && [[ "$(id -gn "$runtime_user")" == "$runtime_group" ]]; then
      echo 'PASS Hermes service identity'
      if [[ -r "$HADES_HERMES_PROFILE/hermes.env" && -r "$HADES_HERMES_PROFILE/config.yaml" ]] && runuser -u "$runtime_user" -- test -r "$HADES_HERMES_PROFILE/hermes.env" && runuser -u "$runtime_user" -- test -r "$HADES_HERMES_PROFILE/config.yaml"; then
        echo 'PASS Hermes profile access'
      else
        echo 'FAIL Hermes runtime cannot read its profile'
        doctor_fail=1
      fi
    else
      echo 'FAIL Hermes service identity is missing or mismatched'
      doctor_fail=1
    fi
    if [[ -x "${HADES_HERMES_EXECUTABLE:-}" ]]; then
      installed_hermes_version=$("$HADES_HERMES_EXECUTABLE" --version 2>&1 || true)
      grep -Fq "$HADES_HERMES_VERSION" <<<"$installed_hermes_version" && echo 'PASS Hermes version pin' || { echo 'FAIL Hermes version differs from manifest'; doctor_fail=1; }
    else
      echo 'FAIL Hermes executable missing'
      doctor_fail=1
    fi
    grocy_mcp_prefix=/opt/hades-grocy-mcp
    grocy_mcp_python="$grocy_mcp_prefix/venv/bin/python"
    grocy_mcp_bin="$grocy_mcp_prefix/venv/bin/grocy-mcp"
    if [[ -x "$grocy_mcp_python" && -x "$grocy_mcp_bin" ]] && \
      "$grocy_mcp_python" -c 'import importlib.metadata as m,sys; sys.exit(0 if m.version("grocy-mcp")==sys.argv[1] else 1)' "$HADES_GROCY_MCP_VERSION"; then
      echo 'PASS pinned Grocy MCP runtime'
    else
      echo 'FAIL pinned Grocy MCP runtime is missing or differs from the version manifest'
      doctor_fail=1
    fi
    runtime_grocy_key="$HADES_CONFIG_ROOT/secrets/grocy-api-key"
    if [[ -f "$runtime_grocy_key" && ! -L "$runtime_grocy_key" && \
      "$(stat -c '%a' "$runtime_grocy_key")" == 640 && \
      "$(stat -c '%U:%G' "$runtime_grocy_key")" == "root:$runtime_group" ]] && \
      runuser -u "$runtime_user" -- test -r "$runtime_grocy_key"; then
      echo 'PASS Hermes-readable protected Grocy key'
    else
      echo 'FAIL Hermes cannot safely read the protected Grocy API key'
      doctor_fail=1
    fi
    if [[ -x "$grocy_mcp_python" && -x "$grocy_mcp_bin" && -f "$runtime_grocy_key" ]]; then
      if (cd "$repo_dir" && runuser -u "$runtime_user" -- env \
        HADES_GROCY_MCP_LAUNCHER="$repo_dir/integrations/grocy-mcp/launch.py" \
        HADES_GROCY_RUNTIME_API_KEY_FILE="$runtime_grocy_key" \
        HADES_GROCY_URL="${HADES_GROCY_URL:-http://127.0.0.1:7003}" \
        "$grocy_mcp_python" "$repo_dir/scripts/check-grocy-mcp-runtime.py"); then
        :
      else
        echo 'FAIL Grocy MCP could not initialize its canonical read/list tools'
        doctor_fail=1
      fi
    fi
  fi
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' hades-lldap 2>/dev/null || true)
  if [[ "$health" == healthy ]]; then echo 'PASS LLDAP health'; elif [[ -z "$health" ]]; then echo 'WARN LLDAP health=not-configured'; else echo "FAIL LLDAP health=$health"; doctor_fail=1; fi
  if [[ -n "${HADES_HINDSIGHT_COMPOSE_FILE:-}" ]]; then
    hindsight_check_args=(--compose-file "$HADES_HINDSIGHT_COMPOSE_FILE")
    [[ -z "$inputs" ]] || hindsight_check_args+=(--env-file "$inputs")
    if python3 "$repo_dir/scripts/check-hindsight-worker-runtime.py" "${hindsight_check_args[@]}"; then
      :
    else
      doctor_fail=1
    fi
  elif [[ -n "$inputs" && "${HADES_INPUTS_VERSION:-1}" == 2 ]]; then
    echo 'FAIL Hindsight Compose record is unavailable for worker identity validation'
    doctor_fail=1
  else
    echo 'WARN Hindsight worker identity is not checked without a Compose record'
  fi
fi
for f in "$repo_dir"/deploy/*.compose.yaml; do
  if command -v docker >/dev/null 2>&1; then
    if "${compose_cmd[@]}" -f "$f" config --quiet; then echo "PASS compose $(basename "$f")"; else echo "FAIL compose $(basename "$f")"; doctor_fail=1; fi
  fi
done
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo 'PASS live container and service checks completed; no host changes were made'
else
  echo 'WARN live container and service checks skipped because the container runtime is unavailable'
fi
(( doctor_fail == 0 )) || exit 1
