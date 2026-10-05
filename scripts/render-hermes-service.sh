#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 077

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
inputs=''
output=''
deployment_dir=''
while (($#)); do
  case "$1" in
    --inputs) inputs=${2:?--inputs needs a file}; shift 2 ;;
    --output) output=${2:?--output needs a file}; shift 2 ;;
    --deployment-dir) deployment_dir=${2:?--deployment-dir needs a directory}; shift 2 ;;
    -h|--help)
      printf 'Usage: %s --inputs FILE --output FILE [--deployment-dir DIR]\n' "${0##*/}"
      exit 0
      ;;
    *) echo 'FAIL unknown Hermes service renderer option' >&2; exit 2 ;;
  esac
done

[[ "$inputs" == /* && -f "$inputs" && ! -L "$inputs" ]] || {
  echo 'FAIL Hermes service renderer requires an absolute regular operator-input file' >&2
  exit 2
}
[[ "$output" == /* && ! -L "$output" ]] || {
  echo 'FAIL Hermes service renderer requires an absolute non-symlink output path' >&2
  exit 2
}
[[ ! -e "$output" || -f "$output" ]] || {
  echo 'FAIL Hermes service renderer output is not a regular file' >&2
  exit 2
}
output_parent=$(dirname "$output")
[[ -d "$output_parent" && ! -L "$output_parent" ]] || {
  echo 'FAIL Hermes service renderer output directory is missing or unsafe' >&2
  exit 2
}
input_mode=$(stat -c '%a' "$inputs")
[[ "$input_mode" == 600 || "$input_mode" == 640 ]] || {
  echo 'FAIL Hermes service renderer operator inputs must be mode 0600 or 0640' >&2
  exit 1
}

source "$inputs" 2>/dev/null || {
  echo 'FAIL Hermes service renderer could not read operator inputs' >&2
  exit 1
}
source "$repo_dir/config/versions.env"
: "${HADES_HERMES_WORKING_DIRECTORY:?operator input is missing HADES_HERMES_WORKING_DIRECTORY}"
: "${HADES_HERMES_EXECUTABLE:?operator input is missing HADES_HERMES_EXECUTABLE}"
: "${HADES_HERMES_PROFILE:?operator input is missing HADES_HERMES_PROFILE}"
: "${HADES_CONFIG_ROOT:?operator input is missing HADES_CONFIG_ROOT}"
deployment_dir=${deployment_dir:-${HADES_DEPLOYMENT_DIR:-$HADES_CONFIG_ROOT/private-deployment}}
runtime_user=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
runtime_group=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
agent_zero_client_env_file="$deployment_dir/agent-zero-client-auth.env"
api_bind_host=${HADES_HERMES_API_BIND_HOST:-127.0.0.1}
searxng_port=${HADES_SEARXNG_PORT:-8080}

for value in "$HADES_HERMES_WORKING_DIRECTORY" "$HADES_HERMES_EXECUTABLE" \
  "$HADES_HERMES_PROFILE" "$HADES_CONFIG_ROOT" "$deployment_dir" \
  "$agent_zero_client_env_file"; do
  [[ "$value" == /* && "$value" != *$'\n'* && "$value" != *$'\r'* ]] || {
    echo 'FAIL Hermes service renderer path inputs must be absolute single-line paths' >&2
    exit 1
  }
done
[[ "$runtime_user" =~ ^[a-z_][a-z0-9_-]*[$]?$ && "$runtime_group" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]] || {
  echo 'FAIL Hermes service renderer runtime account names are invalid' >&2
  exit 1
}
[[ "$api_bind_host" =~ ^[A-Za-z0-9._:-]+$ && "$searxng_port" =~ ^[0-9]{1,5}$ ]] || {
  echo 'FAIL Hermes service renderer endpoint settings are invalid' >&2
  exit 1
}

template="$repo_dir/deploy/templates/hermes.service.in"
revision=$(git -c "safe.directory=$repo_dir" -C "$repo_dir" rev-parse HEAD)
manifest_version=$(awk -F= '$1 == "HADES_MANIFEST_VERSION" {print $2; exit}' "$repo_dir/config/versions.env")
[[ "$manifest_version" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo 'FAIL Hermes service renderer manifest version is invalid' >&2
  exit 1
}
text=$(<"$template")
text=${text//@HADES_HERMES_WORKING_DIRECTORY@/$HADES_HERMES_WORKING_DIRECTORY}
text=${text//@HADES_HERMES_RUNTIME_USER@/$runtime_user}
text=${text//@HADES_HERMES_RUNTIME_GROUP@/$runtime_group}
text=${text//@HADES_HERMES_PROFILE@/$HADES_HERMES_PROFILE}
text=${text//@HADES_CONFIG_ROOT@/$HADES_CONFIG_ROOT}
text=${text//@HADES_DEPLOYMENT_DIR@/$deployment_dir}
text=${text//@HADES_AGENT_ZERO_CLIENT_ENV_FILE@/$agent_zero_client_env_file}
text=${text//@HADES_SEARXNG_PORT@/$searxng_port}
text=${text//@HADES_HERMES_EXECUTABLE@/$HADES_HERMES_EXECUTABLE}
text=${text//@HADES_HERMES_API_BIND_HOST@/$api_bind_host}
[[ "$text" != *'@HADES_'* ]] || {
  echo 'FAIL Hermes service renderer left an unresolved template value' >&2
  exit 1
}

temporary_output=$(mktemp "$output_parent/.hermes-service.XXXXXX")
trap 'rm -f -- "$temporary_output"' EXIT
{
  printf '# generated_by=hades\n# manifest_version=%s\n# repository_revision=%s\n# template=deploy/templates/hermes.service.in\n' \
    "$manifest_version" "$revision"
  printf '%s\n' "$text"
} > "$temporary_output"
chmod 0600 "$temporary_output"
mv -f -- "$temporary_output" "$output"
trap - EXIT
echo 'PASS Hermes service unit rendered'
