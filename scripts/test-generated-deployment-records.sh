#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
mkdir -p "$fixture/config" "$fixture/profile" "$fixture/data" "$fixture/hindsight" "$fixture/searxng"
printf 'synthetic-searxng-secret\n' > "$fixture/searxng-secret"
chmod 600 "$fixture/searxng-secret"
printf 'synthetic-agent-zero-password-123456\n' > "$fixture/agent-zero-operator-password"
chmod 600 "$fixture/agent-zero-operator-password"
cat > "$fixture/operator.env" <<EOF
HADES_INPUTS_VERSION=2
HADES_CONFIG_ROOT=$fixture/config
HADES_DEPLOYMENT_DIR=$fixture/records
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
HADES_OWNER_SUBJECT_IDS=synthetic-alpha
HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=$fixture/agent-zero-operator-password
EOF
chmod 600 "$fixture/operator.env"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" \
  --searx-settings-root "$fixture/staging-config" >/dev/null
test -f "$fixture/staging-config/searxng/settings.yml"
test "$(stat -c '%a' "$fixture/staging-config/searxng/settings.yml")" = 600
test ! -e "$fixture/config/searxng/settings.yml"
test "$(stat -c '%a' "$fixture/records/grocy-mcp.env")" = 600
test "$(stat -c '%a' "$fixture/records/hades-owner-policy.env")" = 600
grep -Fxq 'HADES_OWNER_SUBJECT_IDS=synthetic-alpha' "$fixture/records/hades-owner-policy.env"
grep -Fxq 'HADES_GROCY_URL=http://127.0.0.1:7003' "$fixture/records/grocy-mcp.env"
grep -Fqx "HADES_GROCY_API_KEY_FILE=$fixture/config/secrets/grocy-api-key" "$fixture/records/grocy-mcp.env"
test "$(stat -c '%a' "$fixture/records/agent-zero-operator-auth.env")" = 600
grep -qx 'AUTH_LOGIN=hades-operator' "$fixture/records/agent-zero-operator-auth.env"
grep -qx 'AUTH_PASSWORD=synthetic-agent-zero-password-123456' "$fixture/records/agent-zero-operator-auth.env"
! grep -R 'synthetic-agent-zero-password-123456' "$fixture/records" --include='*.compose.yaml' --include='hermes.service' >/dev/null
auth_sha=$(sha256sum "$fixture/records/agent-zero-operator-auth.env" | awk '{print $1}')
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >/dev/null
test "$(sha256sum "$fixture/records/agent-zero-operator-auth.env" | awk '{print $1}')" = "$auth_sha"
policy_sha=$(sha256sum "$fixture/records/hades-owner-policy.env" | awk '{print $1}')
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >/dev/null
test "$(sha256sum "$fixture/records/hades-owner-policy.env" | awk '{print $1}')" = "$policy_sha"
sed 's/^HADES_OWNER_SUBJECT_IDS=.*/HADES_OWNER_SUBJECT_IDS=synthetic-alpha,synthetic-alpha/' "$fixture/operator.env" > "$fixture/operator-duplicate-owner.env"
chmod 600 "$fixture/operator-duplicate-owner.env"
if bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator-duplicate-owner.env" "$fixture/invalid-owner-records" >"$fixture/duplicate-owner.log" 2>&1; then
  echo 'FAIL renderer accepted duplicate owner subjects' >&2
  exit 1
fi
! grep -q 'synthetic-alpha' "$fixture/duplicate-owner.log"
sed "s/^HADES_OWNER_SUBJECT_IDS=.*/HADES_OWNER_SUBJECT_IDS='synthetic-alpha;id'/" "$fixture/operator.env" > "$fixture/operator-invalid-owner.env"
chmod 600 "$fixture/operator-invalid-owner.env"
if bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator-invalid-owner.env" "$fixture/invalid-owner-records-2" >"$fixture/invalid-owner.log" 2>&1; then
  echo 'FAIL renderer accepted shell syntax in owner subjects' >&2
  exit 1
fi
! grep -q 'synthetic-alpha' "$fixture/invalid-owner.log"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >/dev/null
sed 's/^HADES_OWNER_SUBJECT_IDS=.*/HADES_OWNER_SUBJECT_IDS=/' "$fixture/operator.env" > "$fixture/operator-empty-owner.env"
chmod 600 "$fixture/operator-empty-owner.env"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator-empty-owner.env" "$fixture/records" >/dev/null
test ! -e "$fixture/records/hades-owner-policy.env"
chmod 644 "$fixture/agent-zero-operator-password"
if bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >"$fixture/bad-mode.log" 2>&1; then
  echo 'FAIL renderer accepted an unsafe Agent Zero password mode' >&2
  exit 1
fi
! grep -q 'synthetic-agent-zero-password-123456' "$fixture/bad-mode.log"
chmod 600 "$fixture/agent-zero-operator-password"
printf 'synthetic-agent-zero-password-123456\nsecond-line\n' > "$fixture/agent-zero-operator-password"
chmod 600 "$fixture/agent-zero-operator-password"
if bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >"$fixture/multiline.log" 2>&1; then
  echo 'FAIL renderer accepted a multiline Agent Zero password' >&2
  exit 1
fi
! grep -q 'synthetic-agent-zero-password-123456' "$fixture/multiline.log"
printf 'short\n' > "$fixture/agent-zero-operator-password"
chmod 600 "$fixture/agent-zero-operator-password"
if bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >"$fixture/short-password.log" 2>&1; then
  echo 'FAIL renderer accepted a short Agent Zero password' >&2
  exit 1
fi
! grep -q '^AUTH_PASSWORD=short$' "$fixture/short-password.log"
printf 'synthetic-agent-zero-password-123456\n' > "$fixture/agent-zero-operator-password"
chmod 600 "$fixture/agent-zero-operator-password"
printf 'HADES_INPUTS_VERSION=1\nHADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=/tmp/synthetic-agent-zero-password\n' > "$fixture/operator-v1.env"
chmod 600 "$fixture/operator-v1.env"
if bash "$repo_dir/scripts/install-hades.sh" --preflight --inputs "$fixture/operator-v1.env" >"$fixture/v1.log" 2>&1; then
  echo 'FAIL installer accepted optional native Operator auth under legacy v1 records' >&2
  exit 1
fi
grep -q 'Agent Zero native Operator login requires v2 generated deployment records' "$fixture/v1.log"
set -a
# Compose resolves the authoritative image pins from the repository manifest,
# just as the installer does; the operator file supplies deployment values.
source "$repo_dir/config/versions.env"
source "$fixture/operator.env"
HADES_AGENT_ZERO_AUTH_ENV_FILE="$fixture/records/agent-zero-operator-auth.env"
export HADES_AGENT_ZERO_AUTH_ENV_FILE
set +a
for record in open-webui.compose.yaml hindsight.compose.yaml searxng.compose.yaml hermes.service; do
  test "$(stat -c '%a' "$fixture/records/$record")" = 600
  grep -q '^# generated_by=hades$' "$fixture/records/$record"
done
grep -q "WorkingDirectory=$repo_dir" "$fixture/records/hermes.service"
grep -Fqx "Environment=HADES_HERMES_WORKING_DIRECTORY=$repo_dir" "$fixture/records/hermes.service"
grep -q '^Environment=HADES_HERMES_EXECUTABLE=/usr/bin/hermes$' "$fixture/records/hermes.service"
grep -q "source $fixture/profile/hermes.env" "$fixture/records/hermes.service"
grep -q "EnvironmentFile=-$fixture/records/hades-owner-policy.env" "$fixture/records/hermes.service"
grep -q "source $fixture/records/hades-owner-policy.env" "$fixture/records/hermes.service"
grep -q "EnvironmentFile=-$fixture/records/agent-zero-client-auth.env" "$fixture/records/hermes.service"
grep -q "source $fixture/records/agent-zero-client-auth.env" "$fixture/records/hermes.service"
grep -q 'OPENAI_API_KEYS: "\${HADES_HERMES_API_KEY' "$fixture/records/open-webui.compose.yaml"
grep -Fq "OPENAI_API_CONFIGS: '{\"0\":{\"headers\":{\"X-Hermes-Session-Key\":\"hades-user-{{USER_ID}}\"}}}'" "$fixture/records/open-webui.compose.yaml" || { echo 'FAIL Open WebUI deployment does not forward its authenticated stable subject to Hermes' >&2; exit 1; }
grep -q 'host.docker.internal:host-gateway' "$fixture/records/open-webui.compose.yaml"
grep -q 'HADES_HERMES_CONTAINER_API_BASE_URL' "$fixture/records/open-webui.compose.yaml"
grep -q 'host.docker.internal:host-gateway' "$fixture/records/hindsight.compose.yaml"
grep -q 'HADES_HERMES_CONTAINER_MODEL_ENDPOINT' "$fixture/records/hindsight.compose.yaml"
grep -q 'HINDSIGHT_API_WORKER_ID:.*hades-hindsight' "$fixture/records/hindsight.compose.yaml"
! grep -q 'synthetic-secret' "$fixture/records"/*
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$fixture/records" >/dev/null
grep -q 'synthetic-searxng-secret' "$fixture/config/searxng/settings.yml"
docker compose -f "$fixture/records/open-webui.compose.yaml" config --quiet
docker compose -f "$fixture/records/hindsight.compose.yaml" config --quiet
docker compose -f "$fixture/records/searxng.compose.yaml" config --quiet
docker compose -f "$repo_dir/deploy/agent-zero.compose.yaml" config --quiet
sed '/^HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=/d' "$fixture/operator.env" > "$fixture/operator-no-agent-zero-auth.env"
chmod 600 "$fixture/operator-no-agent-zero-auth.env"
unset HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator-no-agent-zero-auth.env" "$fixture/records" >/dev/null
test ! -e "$fixture/records/agent-zero-operator-auth.env"
unset HADES_AGENT_ZERO_AUTH_ENV_FILE
docker compose --env-file "$fixture/operator-no-agent-zero-auth.env" -f "$repo_dir/deploy/agent-zero.compose.yaml" config --quiet
# Do not consult host-local /etc/systemd/system units while validating this
# disposable record. A live Hermes unit may be intentionally unreadable to
# the test user; vendor dependencies are sufficient for syntax validation.
SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system \
  systemd-analyze verify "$fixture/records/hermes.service"
printf 'TEST-KEY-0000001\n' > "$fixture/agent-zero-api-key"
chmod 600 "$fixture/agent-zero-api-key"
sed "/^HADES_INPUTS_VERSION=/a HADES_AGENT_ZERO_CREDENTIAL_FILE=$fixture/agent-zero-api-key" "$fixture/operator-no-agent-zero-auth.env" > "$fixture/operator-external-agent-zero.env"
chmod 600 "$fixture/operator-external-agent-zero.env"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator-external-agent-zero.env" "$fixture/external-records" > "$fixture/external.log"
test "$(stat -c '%a' "$fixture/external-records/agent-zero-client-auth.env")" = 600
grep -qx 'AGENT_ZERO_API_KEY=TEST-KEY-0000001' "$fixture/external-records/agent-zero-client-auth.env"
! grep -q 'TEST-KEY-0000001' "$fixture/external.log"
echo 'PASS generated deployment records render, protect optional credentials, and validate'
