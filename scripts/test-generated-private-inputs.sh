#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
image='alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc'
bash "$repo_dir/scripts/create-generated-private-inputs.sh" "$fixture/private" --image-ref "$image" >/dev/null
grep -q '^HADES_INPUTS_VERSION=2$' "$fixture/private/operator.env"
grep -q '^HADES_OPEN_WEBUI_IMAGE='"$image"'$' "$fixture/private/operator.env"
test -f "$fixture/private/profile/config.yaml" && test "$(stat -c '%a' "$fixture/private/profile/config.yaml")" = 600
test -f "$fixture/private/profile/hermes.env" && test "$(stat -c '%a' "$fixture/private/profile/hermes.env")" = 600
for name in jwt_secret key_seed admin_password; do
  test "$(stat -c '%a' "$fixture/private/identity/$name")" = 600
done
for name in grocy-api-key agent-zero-credential searxng-secret; do
  test "$(stat -c '%a' "$fixture/private/secrets/$name")" = 600
done
test ! -e "$fixture/private/secrets/hindsight-database"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/private/operator.env" "$fixture/private/config/private-deployment" >/dev/null
test -f "$fixture/private/config/searxng/settings.yml"
! grep -R 'synthetic-searxng-secret' "$fixture/private/config/private-deployment" >/dev/null
grep -q '^HADES_HERMES_CONTAINER_API_BASE_URL=http://host.docker.internal:8642/v1$' "$fixture/private/operator.env"
grep -q '^HADES_HERMES_CONTAINER_MODEL_ENDPOINT=http://host.docker.internal:18080$' "$fixture/private/operator.env"
echo 'PASS generated v2 private-input bundle'
