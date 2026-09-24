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
HADES_HERMES_API_BIND_HOST=${HADES_HERMES_API_BIND_HOST:-127.0.0.1}
HADES_HERMES_RUNTIME_USER=${HADES_HERMES_RUNTIME_USER:-hades-runtime}
HADES_HERMES_RUNTIME_GROUP=${HADES_HERMES_RUNTIME_GROUP:-hades-runtime}
[[ "$HADES_OPEN_WEBUI_IMAGE" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || {
  echo 'FAIL HADES_OPEN_WEBUI_IMAGE must be an immutable image reference' >&2; exit 1;
}

mkdir -p "$output"
chmod 700 "$output"
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
revision=$(git -C "$repo_dir" rev-parse HEAD 2>/dev/null || printf 'unknown')
manifest_sha=$(sha256sum "$repo_dir/config/versions.env" | awk '{print $1}')

render() {
  local source=$1 target=$2
  {
    printf '# generated_by=hades\n# manifest_version=%s\n# repository_revision=%s\n# template=%s\n' \
      "$HADES_MANIFEST_VERSION" "$revision" "$source"
    if [[ "$target" == hermes.service ]]; then
      local text
      text=$(<"$repo_dir/$source")
      text=${text//@HADES_HERMES_WORKING_DIRECTORY@/$HADES_HERMES_WORKING_DIRECTORY}
      text=${text//@HADES_HERMES_RUNTIME_USER@/$HADES_HERMES_RUNTIME_USER}
      text=${text//@HADES_HERMES_RUNTIME_GROUP@/$HADES_HERMES_RUNTIME_GROUP}
      text=${text//@HADES_HERMES_PROFILE@/$HADES_HERMES_PROFILE}
      text=${text//@HADES_CONFIG_ROOT@/$HADES_CONFIG_ROOT}
      text=${text//@HADES_SEARXNG_PORT@/${HADES_SEARXNG_PORT:-8080}}
      text=${text//@HADES_HERMES_EXECUTABLE@/$HADES_HERMES_EXECUTABLE}
      text=${text//@HADES_HERMES_API_BIND_HOST@/$HADES_HERMES_API_BIND_HOST}
      printf '%s\n' "$text"
    else
      cat "$repo_dir/$source"
    fi
  } > "$output/$target"
  chmod 600 "$output/$target"
}

render deploy/templates/open-webui.compose.yaml open-webui.compose.yaml
render deploy/templates/hindsight.compose.yaml hindsight.compose.yaml
render deploy/templates/searxng.compose.yaml searxng.compose.yaml
render deploy/templates/hermes.service.in hermes.service

printf 'manifest_sha256=%s\nrepository_revision=%s\n' "$manifest_sha" "$revision" > "$output/provenance"
chmod 600 "$output/provenance"
printf 'PASS generated deployment records: %s\n' "$output"
