#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
mkdir -p "$fixture/config" "$fixture/profile" "$fixture/data" "$fixture/hindsight" "$fixture/searxng"
chmod 0755 "$fixture"
chmod 0750 "$fixture/config"
for file in operator-password lldap-reader searxng-secret; do printf 'synthetic-secret-value-123456\n' > "$fixture/$file"; chmod 600 "$fixture/$file"; done
cat > "$fixture/authority.json" <<'JSON'
{"schema":1,"reader_user_id":"hades-reader","subjects":{"synthetic-owner":"owner-id"},"groups":{"hades-owners":{"role":"owner","resources":["hades-core.health"]}}}
JSON
chmod 600 "$fixture/authority.json"
cat > "$fixture/operator.env" <<EOF
HADES_INPUTS_VERSION=2
HADES_CONFIG_ROOT=$fixture/config
HADES_HERMES_PROFILE=$fixture/profile
HADES_HERMES_API_BASE_URL=http://127.0.0.1:8642/v1
HADES_HERMES_MODEL_ENDPOINT=http://127.0.0.1:11434
HADES_OPEN_WEBUI_IMAGE=alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc
HADES_OPEN_WEBUI_DATA=$fixture/data
HADES_HINDSIGHT_DATA=$fixture/hindsight
HADES_SEARXNG_DATA=$fixture/searxng
HADES_SEARXNG_SECRET_FILE=$fixture/searxng-secret
HADES_HERMES_WORKING_DIRECTORY=$repo_dir
HADES_HERMES_EXECUTABLE=/usr/bin/hermes
HADES_HERMES_API_KEY=synthetic-hermes-key
HADES_HINDSIGHT_LLM_API_KEY=synthetic-hindsight-key
HADES_HERMES_RUNTIME_USER=$(id -un)
HADES_HERMES_RUNTIME_GROUP=$(id -gn)
HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE=$fixture/operator-password
HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=true
HADES_AGENT_ZERO_OPERATOR_PORT=7004
HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE=$fixture/authority.json
HADES_EPSILON_PHASE3_LLDAP_URL=http://127.0.0.1:17170
HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE=$fixture/lldap-reader
EOF
chmod 600 "$fixture/operator.env"
records="$fixture/config/private-deployment"
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$records" >/dev/null
test "$(stat -c '%a' "$fixture/config/operator-proxy/phase3-authority.json")" = 600
test "$(stat -c '%a' "$fixture/config/operator-proxy/lldap-reader-password")" = 600
test "$(stat -c '%a' "$fixture/config/operator-proxy/auth.env")" = 600
test "$(stat -c '%a' "$fixture/config/operator-proxy/nginx.conf")" = 644
test "$(stat -c '%u' "$fixture/config/operator-proxy/phase3-authority.json")" = "$(id -u)"
test -f "$fixture/config/operator-proxy/source/integrations/operator-access/proxy_auth_server.py"
test "$(stat -c '%a' "$fixture/config/operator-proxy/source/integrations/operator-access/proxy_auth_server.py")" = 640
acl_marker_sha=$(sha256sum "$fixture/config/operator-proxy/config-root-acl-original" | awk '{print $1}')
bash "$repo_dir/scripts/render-deployment-records.sh" "$fixture/operator.env" "$records" >/dev/null
test "$(sha256sum "$fixture/config/operator-proxy/config-root-acl-original" | awk '{print $1}')" = "$acl_marker_sha"
grep -q 'listen 127.0.0.1:3000' "$fixture/config/operator-proxy/nginx.conf"
grep -q 'proxy_pass http://127.0.0.1:3001' "$fixture/config/operator-proxy/nginx.conf"
grep -q 'listen 127.0.0.1:7004' "$fixture/config/operator-proxy/nginx.conf"
grep -q 'proxy_pass http://127.0.0.1:7002' "$fixture/config/operator-proxy/nginx.conf"
! grep -R 'synthetic-secret-value-123456' "$records" "$fixture/config/operator-proxy" --include='*.yaml' --include='*.conf' --include='*.service' >/dev/null
set -a
source "$repo_dir/config/versions.env"
source "$fixture/operator.env"
source "$records/agent-zero-operator-proxy.env"
set +a
docker compose --env-file "$fixture/operator.env" --env-file "$records/agent-zero-operator-proxy.env" -f "$records/open-webui.compose.yaml" config --format json |
  python3 -c 'import json,sys; assert str(json.load(sys.stdin)["services"]["open-webui"]["ports"][0]["published"]) == "3001"'
docker compose --env-file "$fixture/operator.env" --env-file "$records/agent-zero-operator-proxy.env" \
  -f "$records/agent-zero-operator-proxy.compose.yaml" config --quiet
SYSTEMD_UNIT_PATH=/usr/lib/systemd/system:/lib/systemd/system systemd-analyze verify "$records/agent-zero-operator-auth.service"
echo 'PASS optional Agent Zero Operator gateway records render with private custody and loopback upstreams'
