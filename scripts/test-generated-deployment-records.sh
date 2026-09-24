#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
mkdir -p "$fixture/config" "$fixture/profile" "$fixture/data" "$fixture/hindsight" "$fixture/searxng"
printf 'synthetic-searxng-secret\n' > "$fixture/searxng-secret"
chmod 600 "$fixture/searxng-secret"
cat > "$fixture/operator.env" <<EOF
HADES_INPUTS_VERSION=2
HADES_CONFIG_ROOT=$fixture/config
HADES_HERMES_PROFILE=$fixture/profile
HADES_HERMES_API_BASE_URL=http://127.0.0.1:8642/v1
HADES_HERMES_MODEL_ENDPOINT=http://127.0.0.1:11434
HADES_HERMES_CONTAINER_API_BASE_URL=http://host.docker.internal:8642/v1
HADES_HERMES_CONTAINER_MODEL_ENDPOINT=http://host.docker.internal:11434
HADES_OPEN_WEBUI_IMAGE=alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
HADES_OPEN_WEBUI_DATA=$fixture/data
HADES_HINDSIGHT_DATA=$fixture/hindsight
HADES_SEARXNG_DATA=$fixture/searxng
HADES_SEARXNG_SECRET_FILE=$fixture/searxng-secret
HADES_HERMES_WORKING_DIRECTORY=$repo_dir
HADES_HERMES_EXECUTABLE=/usr/bin/hermes
HADES_HERMES_API_KEY=synthetic-secret
HADES_HINDSIGHT_LLM_API_KEY=synthetic-hindsight-key
EOF
chmod 600 "$fixture/operator.env"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >/dev/null
set -a
# Compose resolves the authoritative image pins from the repository manifest,
# just as the installer does; the operator file supplies deployment values.
source "$repo_dir/config/versions.env"
source "$fixture/operator.env"
set +a
for record in open-webui.compose.yaml hindsight.compose.yaml searxng.compose.yaml hermes.service; do
  test "$(stat -c '%a' "$fixture/records/$record")" = 600
  grep -q '^# generated_by=hades$' "$fixture/records/$record"
done
grep -q "WorkingDirectory=$repo_dir" "$fixture/records/hermes.service"
grep -q "source $fixture/profile/hermes.env" "$fixture/records/hermes.service"
grep -q 'OPENAI_API_KEYS: "\${HADES_HERMES_API_KEY' "$fixture/records/open-webui.compose.yaml"
grep -q 'host.docker.internal:host-gateway' "$fixture/records/open-webui.compose.yaml"
grep -q 'HADES_HERMES_CONTAINER_API_BASE_URL' "$fixture/records/open-webui.compose.yaml"
grep -q 'host.docker.internal:host-gateway' "$fixture/records/hindsight.compose.yaml"
grep -q 'HADES_HERMES_CONTAINER_MODEL_ENDPOINT' "$fixture/records/hindsight.compose.yaml"
! grep -q 'synthetic-secret' "$fixture/records"/*
grep -q 'synthetic-searxng-secret' "$fixture/config/searxng/settings.yml"
docker compose -f "$fixture/records/open-webui.compose.yaml" config --quiet
docker compose -f "$fixture/records/hindsight.compose.yaml" config --quiet
docker compose -f "$fixture/records/searxng.compose.yaml" config --quiet
# Do not consult host-local /etc/systemd/system units while validating this
# disposable record. A live Hermes unit may be intentionally unreadable to
# the test user; vendor dependencies are sufficient for syntax validation.
SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system \
  systemd-analyze verify "$fixture/records/hermes.service"
echo 'PASS generated deployment records render, stay secret-free, and validate'
