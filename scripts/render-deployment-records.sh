#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=${1:-}
output=${2:-}
[[ "$inputs" == /* && -f "$inputs" ]] || { echo 'FAIL renderer needs an absolute operator-input file' >&2; exit 2; }
[[ "$output" == /* ]] || { echo 'FAIL renderer needs an absolute output directory' >&2; exit 2; }
[[ ! -L "$inputs" ]] || { echo 'FAIL operator input file must not be a symlink' >&2; exit 1; }
# shellcheck disable=SC1090
source "$inputs"
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"

: "${HADES_CONFIG_ROOT:?operator input is missing HADES_CONFIG_ROOT}"
: "${HADES_HERMES_PROFILE:?operator input is missing HADES_HERMES_PROFILE}"
: "${HADES_HERMES_API_BASE_URL:?operator input is missing HADES_HERMES_API_BASE_URL}"
: "${HADES_OPEN_WEBUI_IMAGE:?operator input is missing HADES_OPEN_WEBUI_IMAGE}"
: "${HADES_OPEN_WEBUI_DATA:?operator input is missing HADES_OPEN_WEBUI_DATA}"
: "${HADES_HINDSIGHT_DATA:?operator input is missing HADES_HINDSIGHT_DATA}"
: "${HADES_SEARXNG_DATA:?operator input is missing HADES_SEARXNG_DATA}"
: "${HADES_SEARXNG_SECRET_FILE:?operator input is missing HADES_SEARXNG_SECRET_FILE}"
: "${HADES_HERMES_WORKING_DIRECTORY:?operator input is missing HADES_HERMES_WORKING_DIRECTORY}"
: "${HADES_HERMES_EXECUTABLE:?operator input is missing HADES_HERMES_EXECUTABLE}"
HADES_DEPLOYMENT_DIR=${HADES_DEPLOYMENT_DIR:-$HADES_CONFIG_ROOT/private-deployment}
HADES_GROCY_URL=${HADES_GROCY_URL:-http://127.0.0.1:7003}
[[ "$HADES_GROCY_URL" =~ ^https?://[A-Za-z0-9._:-]+(/[A-Za-z0-9._~:/?%+-]*)?$ ]] || {
  echo 'FAIL HADES_GROCY_URL must be a simple HTTP(S) URL without credentials or shell-sensitive characters' >&2; exit 1;
}
HADES_DEPLOYMENT_DIR=$output
HADES_HERMES_API_BIND_HOST=${HADES_HERMES_API_BIND_HOST:-127.0.0.1}
HADES_HERMES_RUNTIME_USER=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
HADES_HERMES_RUNTIME_GROUP=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
HADES_OWNER_SUBJECT_IDS=${HADES_OWNER_SUBJECT_IDS:-}
if [[ -n "$HADES_OWNER_SUBJECT_IDS" ]]; then
  [[ ${#HADES_OWNER_SUBJECT_IDS} -le 2048 && "$HADES_OWNER_SUBJECT_IDS" =~ ^[A-Za-z0-9._@-]+(,[A-Za-z0-9._@-]+)*$ ]] || {
    echo 'FAIL HADES_OWNER_SUBJECT_IDS must be a comma-separated list of stable subject IDs' >&2; exit 1;
  }
  IFS=, read -r -a owner_subject_rows <<< "$HADES_OWNER_SUBJECT_IDS"
  declare -A owner_subject_seen=()
  for owner_subject in "${owner_subject_rows[@]}"; do
    [[ -z "${owner_subject_seen[$owner_subject]:-}" ]] || { echo 'FAIL HADES_OWNER_SUBJECT_IDS contains a duplicate subject' >&2; exit 1; }
    owner_subject_seen[$owner_subject]=1
  done
fi
HADES_AGENT_ZERO_AUTH_ENV_FILE="$output/agent-zero-operator-auth.env"
HADES_AGENT_ZERO_CLIENT_ENV_FILE="$output/agent-zero-client-auth.env"
HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=${HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED:-false}
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" != true && "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" != false ]]; then
  echo 'FAIL HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED must be true or false' >&2; exit 1
fi
[[ "$HADES_OPEN_WEBUI_IMAGE" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || {
  echo 'FAIL HADES_OPEN_WEBUI_IMAGE must be an immutable image reference' >&2; exit 1;
}

mkdir -p "$output"
chmod 700 "$output"
if [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]]; then
  [[ "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE" == /* && -f "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE" && ! -L "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE" ]] || {
    echo 'FAIL Agent Zero Operator password input must be an absolute regular non-symlink file' >&2; exit 1;
  }
  auth_secret_mode=$(stat -c '%a' "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE")
  [[ "$auth_secret_mode" == 600 || "$auth_secret_mode" == 640 ]] || {
    echo 'FAIL Agent Zero Operator password input must be mode 0600 or 0640' >&2; exit 1;
  }
  [[ "$(awk 'END { print NR }' "$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE")" == 1 ]] || {
    echo 'FAIL Agent Zero Operator password must contain one line' >&2; exit 1;
  }
  agent_zero_operator_password=$(<"$HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE")
  [[ "$agent_zero_operator_password" =~ ^[A-Za-z0-9._~-]{16,256}$ ]] || {
    echo 'FAIL Agent Zero Operator password must be 16-256 URL-safe characters' >&2; exit 1;
  }
  auth_tmp="$output/.agent-zero-operator-auth.env.$$"
  (umask 077; printf 'AUTH_LOGIN=hades-operator\nAUTH_PASSWORD=%s\n' "$agent_zero_operator_password" > "$auth_tmp")
  chmod 600 "$auth_tmp"
  mv -f "$auth_tmp" "$HADES_AGENT_ZERO_AUTH_ENV_FILE"
  unset agent_zero_operator_password
elif [[ -n "${HADES_AGENT_ZERO_CREDENTIAL_FILE:-}" ]]; then
  rm -f "$HADES_AGENT_ZERO_AUTH_ENV_FILE"
  [[ "$HADES_AGENT_ZERO_CREDENTIAL_FILE" == /* && -f "$HADES_AGENT_ZERO_CREDENTIAL_FILE" && ! -L "$HADES_AGENT_ZERO_CREDENTIAL_FILE" ]] || {
    echo 'FAIL Agent Zero API credential must be an absolute regular non-symlink file' >&2; exit 1;
  }
  credential_mode=$(stat -c '%a' "$HADES_AGENT_ZERO_CREDENTIAL_FILE")
  [[ "$credential_mode" == 600 || "$credential_mode" == 640 ]] || {
    echo 'FAIL Agent Zero API credential must be mode 0600 or 0640' >&2; exit 1;
  }
  [[ "$(awk 'END { print NR }' "$HADES_AGENT_ZERO_CREDENTIAL_FILE")" == 1 ]] || {
    echo 'FAIL Agent Zero API credential must contain one line' >&2; exit 1;
  }
  agent_zero_api_key=$(<"$HADES_AGENT_ZERO_CREDENTIAL_FILE")
  [[ "$agent_zero_api_key" =~ ^[A-Za-z0-9_-]{16}$ ]] || {
    echo 'FAIL Agent Zero API credential must be a 16-character runtime token' >&2; exit 1;
  }
  client_tmp="$output/.agent-zero-client-auth.env.$$"
  (umask 077; printf 'AGENT_ZERO_API_KEY=%s\n' "$agent_zero_api_key" > "$client_tmp")
  chmod 600 "$client_tmp"
  if [[ -f "$HADES_AGENT_ZERO_CLIENT_ENV_FILE" ]] && cmp -s "$client_tmp" "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"; then
    rm -f "$client_tmp"
  else
    mv -f "$client_tmp" "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
  fi
  unset agent_zero_api_key
else
  rm -f "$HADES_AGENT_ZERO_AUTH_ENV_FILE"
  rm -f "$HADES_AGENT_ZERO_CLIENT_ENV_FILE"
  unset HADES_AGENT_ZERO_AUTH_ENV_FILE
fi
[[ -f "$HADES_SEARXNG_SECRET_FILE" && ! -L "$HADES_SEARXNG_SECRET_FILE" ]] || {
  echo 'FAIL SearXNG secret file is missing or a symlink' >&2; exit 1;
}
secret_mode=$(stat -c '%a' "$HADES_SEARXNG_SECRET_FILE")
[[ "$secret_mode" == 600 || "$secret_mode" == 640 ]] || {
  echo 'FAIL SearXNG secret file must be mode 0600 or 0640' >&2; exit 1;
}
mkdir -p "$HADES_CONFIG_ROOT/searxng"
awk -v secret="$(<"$HADES_SEARXNG_SECRET_FILE")" \
  '{gsub("__SEARXNG_SECRET__", secret); print}' \
  "$repo_dir/searxng/settings.yml" > "$HADES_CONFIG_ROOT/searxng/settings.yml"
chmod 600 "$HADES_CONFIG_ROOT/searxng/settings.yml"
revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse HEAD 2>/dev/null || printf 'unknown')
manifest_sha=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')

render() {
  local source=$1 target=$2
  {
    printf '# generated_by=hades\n# manifest_version=%s\n# repository_revision=%s\n# template=%s\n' \
      "$HADES_MANIFEST_VERSION" "$revision" "$source"
    cat "$repo_dir/$source"
  } > "$output/$target"
  chmod 600 "$output/$target"
}

render deploy/templates/open-webui.compose.yaml open-webui.compose.yaml
render deploy/templates/hindsight.compose.yaml hindsight.compose.yaml
render deploy/templates/searxng.compose.yaml searxng.compose.yaml
bash "$repo_dir/scripts/render-hermes-service.sh" \
  --inputs "$inputs" --output "$output/hermes.service" --deployment-dir "$output"

owner_policy_env="$output/hades-owner-policy.env"
if [[ -n "$HADES_OWNER_SUBJECT_IDS" ]]; then
  owner_policy_tmp="$output/.hades-owner-policy.env.$$"
  printf 'HADES_OWNER_SUBJECT_IDS=%s\n' "$HADES_OWNER_SUBJECT_IDS" > "$owner_policy_tmp"
  chmod 600 "$owner_policy_tmp"
  mv -f "$owner_policy_tmp" "$owner_policy_env"
else
  rm -f "$owner_policy_env"
fi

cat > "$output/grocy-mcp.env" <<EOF
HADES_GROCY_URL=${HADES_GROCY_URL:-http://127.0.0.1:7003}
HADES_GROCY_API_KEY_FILE=$HADES_CONFIG_ROOT/secrets/grocy-api-key
EOF
chmod 600 "$output/grocy-mcp.env"

operator_proxy_env="$output/agent-zero-operator-proxy.env"
operator_proxy_compose="$output/agent-zero-operator-proxy.compose.yaml"
operator_proxy_auth="$output/agent-zero-operator-auth.service"
if [[ "$HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED" == true ]]; then
  [[ -n "${HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE:-}" ]] || { echo 'FAIL Operator proxy requires HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE' >&2; exit 1; }
  [[ -n "${HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE:-}" && -n "${HADES_EPSILON_PHASE3_LLDAP_URL:-}" && -n "${HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE:-}" ]] || {
    echo 'FAIL Operator proxy requires the live Phase 3 LLDAP authority file, URL, and reader password file' >&2; exit 1;
  }
  proxy_port=${HADES_AGENT_ZERO_OPERATOR_PORT:-7004}
  [[ "$proxy_port" =~ ^[0-9]{1,5}$ ]] && ((proxy_port >= 1 && proxy_port <= 65535)) || { echo 'FAIL Operator proxy port must be 1-65535' >&2; exit 1; }
  webui_bind=${HADES_OPEN_WEBUI_BIND:-127.0.0.1:3000}
  [[ "$webui_bind" =~ ^(127\.0\.0\.1|localhost):([0-9]{1,5})$ ]] || { echo 'FAIL Operator proxy requires a loopback HADES_OPEN_WEBUI_BIND' >&2; exit 1; }
  webui_front_port=${webui_bind##*:}
  webui_upstream_port=$((webui_front_port + 1))
  ((webui_upstream_port <= 65535 && proxy_port != webui_front_port && proxy_port != webui_upstream_port && proxy_port != 7002 && proxy_port != 8645 && webui_front_port != 8645 && webui_upstream_port != 8645)) || { echo 'FAIL Operator proxy ports overlap or exceed the valid range' >&2; exit 1; }
  runtime_user=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
  runtime_group=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
  runtime_uid=$(id -u "$runtime_user" 2>/dev/null) || { echo 'FAIL Operator proxy requires the Hermes runtime user to exist before rendering' >&2; exit 1; }
  runtime_gid=$(id -g "$runtime_user")
  [[ "$(id -gn "$runtime_user")" == "$runtime_group" ]] || { echo 'FAIL Operator proxy runtime group must match the Hermes runtime user primary group' >&2; exit 1; }
  command -v getfacl >/dev/null 2>&1 && command -v setfacl >/dev/null 2>&1 || { echo 'FAIL Operator proxy requires getfacl/setfacl for private runtime directory traversal' >&2; exit 1; }
  for private_input in "$HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE" "$HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE"; do
    [[ "$private_input" == /* && -f "$private_input" && ! -L "$private_input" && "$(stat -c '%a' "$private_input")" == 600 ]] || {
      echo 'FAIL Operator proxy LLDAP inputs must be absolute regular mode-0600 files' >&2; exit 1;
    }
  done
  proxy_root="$HADES_CONFIG_ROOT/operator-proxy"
  source_root="$proxy_root/source"
  install -d -o "$runtime_uid" -g "$runtime_gid" -m 0700 "$proxy_root" "$source_root/integrations/operator-access" "$source_root/integrations/automation"
  acl_marker="$proxy_root/config-root-acl-original"
  if [[ ! -f "$acl_marker" ]]; then
    old_acl=$(getfacl -cpn "$HADES_CONFIG_ROOT" | awk -F: -v uid="$runtime_uid" '$1 == "user" && $2 == uid {print $3; exit}')
    (umask 077; printf '%s:%s\n' "$runtime_uid" "${old_acl:-none}" > "$acl_marker")
    chown "$runtime_uid:$runtime_gid" "$acl_marker"; chmod 0600 "$acl_marker"
  fi
  acl_uid=$(cut -d: -f1 "$acl_marker")
  acl_previous=$(cut -d: -f2- "$acl_marker")
  [[ "$acl_uid" == "$runtime_uid" ]] || { echo 'FAIL Operator proxy ACL ownership record does not match the runtime identity' >&2; exit 1; }
  acl_permissions='-'
  [[ "$acl_previous" == *r* ]] && acl_permissions='r'
  if [[ "$acl_previous" == *w* ]]; then acl_permissions+='w'; else acl_permissions+='-'; fi
  acl_permissions+='x'
  setfacl -m "u:$runtime_uid:$acl_permissions" "$HADES_CONFIG_ROOT"
  install -o "$runtime_uid" -g "$runtime_gid" -m 0600 "$HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE" "$proxy_root/phase3-authority.json"
  install -o "$runtime_uid" -g "$runtime_gid" -m 0600 "$HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE" "$proxy_root/lldap-reader-password"
  install -o "$runtime_uid" -g "$runtime_gid" -m 0640 "$repo_dir/integrations/operator-access/session_auth.py" "$source_root/integrations/operator-access/session_auth.py"
  install -o "$runtime_uid" -g "$runtime_gid" -m 0640 "$repo_dir/integrations/operator-access/proxy_auth_server.py" "$source_root/integrations/operator-access/proxy_auth_server.py"
  install -o "$runtime_uid" -g "$runtime_gid" -m 0640 "$repo_dir/integrations/automation/phase3_lldap_authority.py" "$source_root/integrations/automation/phase3_lldap_authority.py"
  install -o "$runtime_uid" -g "$runtime_gid" -m 0640 "$repo_dir/integrations/automation/phase3_self_service.py" "$source_root/integrations/automation/phase3_self_service.py"
  : > "$source_root/integrations/__init__.py"; : > "$source_root/integrations/operator-access/__init__.py"; : > "$source_root/integrations/automation/__init__.py"
  chown "$runtime_uid:$runtime_gid" "$source_root/integrations/__init__.py" "$source_root/integrations/operator-access/__init__.py" "$source_root/integrations/automation/__init__.py"
  chmod 0640 "$source_root/integrations/"*/__init__.py
  sed -e "s|@WEBUI_FRONT_PORT@|$webui_front_port|g" \
      -e "s|@WEBUI_UPSTREAM_PORT@|$webui_upstream_port|g" \
      -e "s|@OPERATOR_FRONT_PORT@|$proxy_port|g" \
      -e 's|@AUTH_PORT@|8645|g' -e 's|@AGENT_ZERO_UPSTREAM_PORT@|7002|g' \
      "$repo_dir/deploy/templates/agent-zero-operator.nginx.conf.in" > "$proxy_root/nginx.conf"
  chown "$runtime_uid:$runtime_gid" "$proxy_root/nginx.conf"; chmod 0644 "$proxy_root/nginx.conf"
  sed -e "s|@HADES_OPERATOR_RUNTIME_USER@|$runtime_user|g" \
      -e "s|@HADES_OPERATOR_RUNTIME_GROUP@|$runtime_group|g" \
      -e "s|@HADES_OPERATOR_SOURCE_ROOT@|$source_root|g" \
      -e "s|@HADES_OPERATOR_AUTH_ENV_FILE@|$proxy_root/auth.env|g" \
      -e "s|@HADES_OPERATOR_AUTHORITY_CONFIG@|$proxy_root/phase3-authority.json|g" \
      -e "s|@HADES_OPERATOR_READER_PASSWORD_FILE@|$proxy_root/lldap-reader-password|g" \
      "$repo_dir/deploy/templates/agent-zero-operator-auth.service.in" > "$operator_proxy_auth"
  chmod 0600 "$operator_proxy_auth"
  auth_tmp="$proxy_root/.auth.env.$$"
  printf 'HADES_OPERATOR_WEBUI_ENDPOINT=http://127.0.0.1:%s\nHADES_OPERATOR_LLDAP_ENDPOINT=%s\nHADES_OPERATOR_AUTHORITY_CONFIG=%s/phase3-authority.json\nHADES_OPERATOR_READER_PASSWORD_FILE=%s/lldap-reader-password\n' \
    "$webui_upstream_port" "$HADES_EPSILON_PHASE3_LLDAP_URL" "$proxy_root" "$proxy_root" > "$auth_tmp"
  chown "$runtime_uid:$runtime_gid" "$auth_tmp"; chmod 0600 "$auth_tmp"; mv -f "$auth_tmp" "$proxy_root/auth.env"
  sed "s|\${HADES_AGENT_ZERO_OPERATOR_NGINX_CONFIG:?set generated Nginx config path}|$proxy_root/nginx.conf|g" \
    "$repo_dir/deploy/templates/agent-zero-operator-proxy.compose.yaml" > "$operator_proxy_compose"
  chmod 0600 "$operator_proxy_compose"
  printf 'HADES_OPEN_WEBUI_BIND=127.0.0.1:%s\nHADES_AGENT_ZERO_OPERATOR_NGINX_CONFIG=%s/nginx.conf\n' "$webui_upstream_port" "$proxy_root" > "$operator_proxy_env"
  chmod 0600 "$operator_proxy_env"
else
  rm -f "$operator_proxy_env" "$operator_proxy_compose" "$operator_proxy_auth"
fi

printf 'manifest_sha256=%s\nrepository_revision=%s\n' "$manifest_sha" "$revision" > "$output/provenance"
chmod 600 "$output/provenance"
printf 'PASS generated deployment records: %s\n' "$output"
