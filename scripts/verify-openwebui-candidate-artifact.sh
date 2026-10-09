#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
image=${1:?usage: verify-openwebui-candidate-artifact.sh IMAGE}
[[ "$HADES_OPEN_WEBUI_CANDIDATE_HADES_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'FAIL candidate HADES build commit is not qualified' >&2; exit 2; }
[[ "$HADES_OPEN_WEBUI_CANDIDATE_HADES_IMAGE_ID" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'FAIL candidate HADES image ID is not qualified' >&2; exit 2; }
[[ "$HADES_OPEN_WEBUI_CANDIDATE_SECURITY_ADAPTERS" == 'fail-closed-jwt,authority-revocation,ldap-empty-group,socket-disconnect-fail-closed' ]] || { echo 'FAIL required security adapter manifest is incomplete' >&2; exit 2; }
image_id=$(docker image inspect "$image" --format '{{.Id}}')
[[ "$image_id" == "$HADES_OPEN_WEBUI_CANDIDATE_HADES_IMAGE_ID" ]] || { echo "FAIL candidate image ID differs from manifest: $image_id" >&2; exit 2; }
version=$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.version"}}')
upstream_commit=$(docker image inspect "$image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')
hades_commit=$(docker image inspect "$image" --format '{{index .Config.Labels "org.hades.open-webui.source-commit"}}')
base_image=$(docker image inspect "$image" --format '{{index .Config.Labels "org.hades.open-webui.base-image"}}')
security_adapters=$(docker image inspect "$image" --format '{{index .Config.Labels "org.hades.open-webui.security-adapters"}}')
[[ "$version" == "$HADES_OPEN_WEBUI_CANDIDATE_VERSION" ]] || { echo "FAIL candidate Open WebUI version mismatch: $version" >&2; exit 2; }
[[ "$upstream_commit" == "$HADES_OPEN_WEBUI_CANDIDATE_SOURCE_COMMIT" ]] || { echo "FAIL candidate upstream revision mismatch: $upstream_commit" >&2; exit 2; }
[[ "$hades_commit" == "$HADES_OPEN_WEBUI_CANDIDATE_HADES_COMMIT" ]] || { echo "FAIL candidate HADES source commit mismatch: $hades_commit" >&2; exit 2; }
[[ "$base_image" == "$HADES_OPEN_WEBUI_CANDIDATE_IMAGE" ]] || { echo "FAIL candidate base image mismatch: $base_image" >&2; exit 2; }
[[ "$security_adapters" == "$HADES_OPEN_WEBUI_CANDIDATE_SECURITY_ADAPTERS" ]] || { echo "FAIL candidate security adapters mismatch: $security_adapters" >&2; exit 2; }
echo "PASS manifest-bound Open WebUI candidate artifact: $image_id ($hades_commit)"
