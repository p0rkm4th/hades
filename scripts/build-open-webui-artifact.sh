#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tag=${1:-hades-open-webui:0.11.4-p0-candidate}
source "$repo_dir/config/versions.env"
base_override=${HADES_OPEN_WEBUI_BASE_IMAGE_OVERRIDE:-$HADES_OPEN_WEBUI_CANDIDATE_IMAGE}
source_commit=$(git -C "$repo_dir" rev-parse HEAD)
if [[ -n "$(git -C "$repo_dir" status --porcelain)" ]]; then
  echo 'FAIL build provenance requires a clean tracked worktree' >&2
  exit 1
fi
command -v docker >/dev/null 2>&1 || { echo 'FAIL docker is required to build Open WebUI' >&2; exit 1; }
if [[ -n "$base_override" && ! "$base_override" =~ ^ghcr\.io/open-webui/open-webui@sha256:[0-9a-f]{64}$ ]]; then
  echo 'FAIL Open WebUI base override must be an immutable GHCR digest' >&2
  exit 1
fi
if [[ "$base_override" != "$HADES_OPEN_WEBUI_CANDIDATE_IMAGE" ]]; then
  echo 'FAIL P0 security artifact must use the exact qualified 0.11.4 upstream candidate digest' >&2
  exit 1
fi
docker build --pull=false \
  --build-arg "OPEN_WEBUI_BASE_IMAGE=$base_override" \
  --label "org.hades.open-webui.source-commit=$source_commit" \
  --label "org.hades.open-webui.base-image=$base_override" \
  --label "org.hades.open-webui.security-adapters=$HADES_OPEN_WEBUI_CANDIDATE_SECURITY_ADAPTERS" \
  -f "$repo_dir/webui/Dockerfile" -t "$tag" "$repo_dir" >/dev/null
image_id=$(docker image inspect "$tag" --format '{{.Id}}')
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'FAIL built Open WebUI image identity is invalid' >&2; exit 1; }
printf 'HADES_OPEN_WEBUI_IMAGE=%s@%s\n' "${tag%%:*}" "$image_id"
printf 'HADES_OPEN_WEBUI_IMAGE_ID=%s\n' "$image_id"
printf 'HADES_OPEN_WEBUI_SOURCE_COMMIT=%s\n' "$source_commit"
printf 'HADES_OPEN_WEBUI_BASE_IMAGE=%s\n' "$base_override"
printf 'PASS tracked Open WebUI artifact built from immutable base %s\n' "$image_id" >&2
