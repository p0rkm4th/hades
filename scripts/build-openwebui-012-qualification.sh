#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tag=${1:-hades-open-webui:0.12.0-qualification}
artifact=${2:-"${TMPDIR:-/tmp}/hades-openwebui-012-$(git -C "$repo_dir" rev-parse --short=12 HEAD).docker.tar"}
manifest="${artifact}.manifest.json"
# shellcheck disable=SC1091
source "$repo_dir/config/openwebui-0.12.0-qualification.pins"
source_commit=$(git -C "$repo_dir" rev-parse HEAD)
source_epoch=$(git -C "$repo_dir" show -s --format=%ct "$source_commit")
if [[ -n "$(git -C "$repo_dir" status --porcelain)" ]]; then
  echo 'FAIL qualification artifact requires a clean worktree' >&2
  exit 1
fi
command -v docker >/dev/null 2>&1 || { echo 'FAIL docker is required to build the qualification image' >&2; exit 1; }
docker buildx version >/dev/null 2>&1 || { echo 'FAIL Docker Buildx is required for reproducible image export' >&2; exit 1; }
[[ ! -e "$artifact" && ! -e "$manifest" ]] || { echo 'FAIL artifact or manifest path already exists' >&2; exit 1; }
mkdir -p "$(dirname "$artifact")"
builder="hades-webui-012-$$-${RANDOM}"
cleanup() { docker buildx rm --force "$builder" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker buildx create --name "$builder" --driver docker-container \
  --driver-opt "image=$HADES_OPEN_WEBUI_012_BUILDKIT_IMAGE" >/dev/null
docker buildx inspect "$builder" --bootstrap >/dev/null

docker buildx build --builder "$builder" --no-cache --provenance=false \
  --platform "$HADES_OPEN_WEBUI_012_PLATFORM" \
  --build-arg "SOURCE_DATE_EPOCH=$source_epoch" \
  --build-arg "OPEN_WEBUI_BASE_IMAGE=$HADES_OPEN_WEBUI_012_AMD64_IMAGE" \
  --label "org.hades.open-webui.source-commit=$source_commit" \
  --label "org.hades.open-webui.base-image=$HADES_OPEN_WEBUI_012_AMD64_IMAGE" \
  --label "org.hades.open-webui.upstream-source-commit=$HADES_OPEN_WEBUI_012_UPSTREAM_COMMIT" \
  --label 'org.hades.open-webui.security-adapters=fail-closed-jwt,authority-revocation,ldap-empty-group,socket-disconnect-fail-closed' \
  -f "$repo_dir/webui/Dockerfile.openwebui-012-qualification" \
  --output "type=docker,dest=$artifact,rewrite-timestamp=true" "$repo_dir"

artifact_sha=$(sha256sum "$artifact" | awk '{print $1}')
load_output=$(docker load --input "$artifact")
image_id=$(sed -n 's/^Loaded image ID: //p' <<<"$load_output")
[[ "$image_id" =~ ^sha256:[0-9a-f]{64}$ ]] || { printf '%s\n' "$load_output" >&2; echo 'FAIL loaded candidate image ID is missing' >&2; exit 1; }
docker image tag "$image_id" "$tag"
buildx_version=$(docker buildx version | awk '{print $2}')
dockerfile_sha=$(sha256sum "$repo_dir/webui/Dockerfile.openwebui-012-qualification" | awk '{print $1}')
python3 - "$manifest" "$source_commit" "$source_epoch" "$HADES_OPEN_WEBUI_012_UPSTREAM_COMMIT" \
  "$HADES_OPEN_WEBUI_012_OCI_INDEX" "$HADES_OPEN_WEBUI_012_AMD64_IMAGE" \
  "$HADES_OPEN_WEBUI_012_PLATFORM" "$HADES_OPEN_WEBUI_012_BUILDKIT_IMAGE" \
  "$buildx_version" "$dockerfile_sha" "$artifact_sha" "$image_id" <<'PY'
import json
import sys
from pathlib import Path

(output, source, epoch, upstream, index_digest, image, platform, buildkit,
 buildx, dockerfile, artifact, image_id) = sys.argv[1:]
payload = {
    "artifact_sha256": artifact,
    "buildx_version": buildx,
    "dockerfile_sha256": dockerfile,
    "hades_source_commit": source,
    "image_config_id": image_id,
    "platform": platform,
    "source_date_epoch": int(epoch),
    "upstream_amd64_image": image,
    "upstream_buildkit_image": buildkit,
    "upstream_oci_index_digest": index_digest,
    "upstream_source_commit": upstream,
}
Path(output).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

printf 'HADES_OPEN_WEBUI_012_QUAL_IMAGE=%s@%s\n' "${tag%%:*}" "$image_id"
printf 'HADES_OPEN_WEBUI_012_QUAL_IMAGE_ID=%s\n' "$image_id"
printf 'HADES_OPEN_WEBUI_012_QUAL_ARTIFACT=%s\n' "$artifact"
printf 'HADES_OPEN_WEBUI_012_QUAL_ARTIFACT_SHA256=%s\n' "$artifact_sha"
printf 'HADES_OPEN_WEBUI_012_QUAL_MANIFEST=%s\n' "$manifest"
