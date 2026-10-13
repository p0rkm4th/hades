#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tag=${1:-hades-open-webui:0.12.0-qualification}
# shellcheck disable=SC1091
source "$repo_dir/config/openwebui-0.12.0-qualification.pins"
source_commit=$(git -C "$repo_dir" rev-parse HEAD)
if [[ -n "$(git -C "$repo_dir" status --porcelain)" ]]; then
  echo 'FAIL qualification artifact requires a clean tracked worktree' >&2
  exit 1
fi
command -v docker >/dev/null 2>&1 || { echo 'FAIL docker is required to build the qualification image' >&2; exit 1; }
docker build --pull=false --platform "$HADES_OPEN_WEBUI_012_PLATFORM" \
  --build-arg "OPEN_WEBUI_BASE_IMAGE=$HADES_OPEN_WEBUI_012_AMD64_IMAGE" \
  --label "org.hades.open-webui.source-commit=$source_commit" \
  --label "org.hades.open-webui.base-image=$HADES_OPEN_WEBUI_012_AMD64_IMAGE" \
  --label "org.hades.open-webui.upstream-source-commit=$HADES_OPEN_WEBUI_012_UPSTREAM_COMMIT" \
  --label "org.hades.open-webui.security-adapters=fail-closed-jwt,authority-revocation,ldap-empty-group,socket-disconnect-fail-closed" \
  -f "$repo_dir/webui/Dockerfile.openwebui-012-qualification" -t "$tag" "$repo_dir" >/dev/null
image_id=$(docker image inspect "$tag" --format '{{.Id}}')
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'FAIL candidate image identity is invalid' >&2; exit 1; }
printf 'HADES_OPEN_WEBUI_012_QUAL_IMAGE=%s@%s\n' "${tag%%:*}" "$image_id"
printf 'HADES_OPEN_WEBUI_012_QUAL_IMAGE_ID=%s\n' "$image_id"
printf 'HADES_OPEN_WEBUI_012_HADES_SOURCE_COMMIT=%s\n' "$source_commit"
printf 'HADES_OPEN_WEBUI_012_UPSTREAM_IMAGE=%s\n' "$HADES_OPEN_WEBUI_012_AMD64_IMAGE"
