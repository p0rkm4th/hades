#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tag=${1:-hades-open-webui:0.11.1-hades}
command -v docker >/dev/null 2>&1 || { echo 'FAIL docker is required to build Open WebUI' >&2; exit 1; }
docker build --pull=false -t "$tag" "$repo_dir/webui" >/dev/null
image_id=$(docker image inspect "$tag" --format '{{.Id}}')
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'FAIL built Open WebUI image identity is invalid' >&2; exit 1; }
printf 'HADES_OPEN_WEBUI_IMAGE=%s@%s\n' "${tag%%:*}" "$image_id"
printf 'HADES_OPEN_WEBUI_IMAGE_ID=%s\n' "$image_id"
printf 'PASS tracked Open WebUI artifact built from immutable base %s\n' "$image_id" >&2
