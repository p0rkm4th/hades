#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Authenticated household UI proof for readable, honest staged automation state.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
webui_image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
suffix="$$"
webui_name="hades-phase3-ui-webui-$suffix"
webui_volume="hades-phase3-ui-data-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-phase3-ui.XXXXXX")
webui_port=${HADES_PHASE3_UI_WEBUI_PORT:-18892}
gateway_port=${HADES_PHASE3_UI_GATEWAY_PORT:-18893}
api_key="synthetic-hades-phase3-ui-$suffix"
gateway_pid=''
step='preflight'

cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then
    echo "FAIL authenticated Phase 3 draft transparency at step '$step'" >&2
    local debug_dir="${HADES_PHASE3_UI_DEBUG_DIR:-/tmp/hades-phase3-ui-debug-$$}"
    mkdir -m 700 -p "$debug_dir"
    [[ -f "$work/hermes.log" ]] && install -m 600 "$work/hermes.log" "$debug_dir/hermes.log"
    [[ -f "$work/acceptance.json" ]] && install -m 600 "$work/acceptance.json" "$debug_dir/acceptance.json"
    echo "Synthetic failure diagnostics saved to $debug_dir" >&2
    rg 'Phase 3|staged|draft|run' "$work/hermes.log" | tail -n 30 >&2 || true
  fi
  if [[ -n "$gateway_pid" ]]; then kill "$gateway_pid" >/dev/null 2>&1 || true; wait "$gateway_pid" >/dev/null 2>&1 || true; fi
  docker rm -f "$webui_name" >/dev/null 2>&1 || true
  docker volume rm "$webui_volume" >/dev/null 2>&1 || true
  find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
  rmdir "$work" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

for binary in docker hermes node curl python3; do command -v "$binary" >/dev/null; done
export HADES_PLAYWRIGHT_MODULE=${HADES_PLAYWRIGHT_MODULE:-playwright}; node -e 'require(process.env.HADES_PLAYWRIGHT_MODULE)' >/dev/null 2>&1 || { echo 'FAIL local Playwright dependency is unavailable' >&2; exit 2; }
docker image inspect "$webui_image" >/dev/null
for port in "$webui_port" "$gateway_port"; do
  if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then echo "FAIL occupied test port: $port" >&2; exit 2; fi
done
docker_gateway=$(docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' | head -n1)
[[ "$docker_gateway" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo 'FAIL Docker bridge gateway unavailable' >&2; exit 2; }
chmod 700 "$work"

step='starting disposable Open WebUI'
docker volume create "$webui_volume" >/dev/null
docker run -d --name "$webui_name" --add-host host.docker.internal:host-gateway \
  -p "127.0.0.1:${webui_port}:8080" -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true \
  -e ENABLE_OLLAMA_API=false -e RAG_EMBEDDING_ENGINE=ollama \
  -v "$webui_volume:/app/backend/data" "$webui_image" >/dev/null
for _ in $(seq 1 120); do curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break; sleep 1; done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null

step='creating synthetic Alpha/Beta identities'
signup=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Alpha","email":"alpha-phase3@example.invalid","password":"Synthetic-Only-123!"}')
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$signup")
alpha_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$signup")
beta_json=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data '{"name":"Beta","email":"beta-phase3@example.invalid","password":"Synthetic-Only-123!","role":"user"}')
beta_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$beta_json")
gamma_json=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data '{"name":"Gamma","email":"gamma-phase3@example.invalid","password":"Synthetic-Only-123!","role":"user"}')
gamma_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$gamma_json")

step='initializing synthetic Phase 3 state'
state_file="$work/phase3.sqlite"
PYTHONPATH="$repo_dir" python3 - "$state_file" <<'PY'
import sys
from integrations.automation.phase3_self_service import Phase3Store
Phase3Store(sys.argv[1])
PY

step='configuring Hermes gateway'
export HERMES_HOME="$work/hermes"
mkdir -m 700 "$HERMES_HOME"
hermes profile create hades --no-alias --no-skills >/dev/null
chmod 700 "$HERMES_HOME/profiles" "$HERMES_HOME/profiles/hades"
cat >"$HERMES_HOME/profiles/hades/config.yaml" <<'YAML'
model:
  default: synthetic-no-call
  provider: custom
  base_url: http://127.0.0.1:9/v1
YAML
chmod 600 "$HERMES_HOME/profiles/hades/config.yaml"
hermes_bin=$(readlink -f "$(command -v hermes)")
hermes_python="$(dirname "$hermes_bin")/python3.11"
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python 3.11 unavailable' >&2; exit 2; }
export HADES_HERMES_EXECUTABLE="$hermes_bin"
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
export PYTHONPATH="$repo_dir/hermes:$repo_dir:$hermes_source"
export HADES_OWNER_SUBJECT_IDS="$alpha_id"
export HADES_EPSILON_PHASE3_HOUSEHOLD_CREATION=staged
export HADES_EPSILON_PHASE3_STATE_FILE="$state_file"
export HADES_EPSILON_PHASE2_RESOURCE_SHARES="$beta_id:grocy.household,$gamma_id:grocy.household"
export HADES_SELF_SERVICE_SHARE_SUBJECTS="Gamma:$gamma_id"
export API_SERVER_ENABLED=true API_SERVER_KEY="$api_key" API_SERVER_HOST="$docker_gateway" API_SERVER_PORT="$gateway_port"
export OPENAI_API_KEY=synthetic-unused OPENAI_BASE_URL=http://127.0.0.1:9/v1 MODEL=synthetic-no-call HERMES_ACCEPT_HOOKS=1
gateway_url="http://${docker_gateway}:${gateway_port}"
hermes -p hades gateway run -v >"$work/hermes.log" 2>&1 &
gateway_pid=$!
for _ in $(seq 1 90); do curl -fsS "$gateway_url/health" >/dev/null 2>&1 && break; kill -0 "$gateway_pid" 2>/dev/null || { cat "$work/hermes.log" >&2; exit 1; }; sleep 1; done
curl -fsS "$gateway_url/health" >/dev/null
models=$(curl -fsS -H "Authorization: Bearer $api_key" "$gateway_url/v1/models")
model_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); print(x["data"][0]["id"] if x.get("data") else "")' <<<"$models")
[[ -n "$model_id" ]] || { cat "$work/hermes.log" >&2; echo 'FAIL Hermes advertised no model' >&2; exit 1; }

step='configuring authenticated household model access'
curl -fsS -X POST "http://127.0.0.1:${webui_port}/openai/config/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${gateway_port}/v1\"],\"OPENAI_API_KEYS\":[\"${api_key}\"],\"OPENAI_API_CONFIGS\":{\"0\":{\"headers\":{\"X-Hermes-Session-Key\":\"hades-user-{{USER_ID}}\"}}}}" >/dev/null
access=$(python3 - "$model_id" "$alpha_id" "$beta_id" "$gamma_id" <<'PY'
import json, sys
model, *users = sys.argv[1:]
print(json.dumps({"id": model, "name": model, "access_grants": [
    {"principal_type": "user", "principal_id": user, "permission": "read"} for user in users
]}))
PY
)
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/models/model/access/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' --data "$access" >/dev/null

step='authenticated draft transparency UI acceptance'
report="$work/acceptance.json"
HADES_PHASE3_UI_BASE_URL="http://127.0.0.1:${webui_port}" \
  HADES_PHASE3_UI_EMAIL=beta-phase3@example.invalid \
  HADES_PHASE3_UI_PASSWORD='Synthetic-Only-123!' HADES_PHASE3_UI_MODEL_ID="$model_id" \
  HADES_PHASE3_UI_GAMMA_EMAIL=gamma-phase3@example.invalid HADES_PHASE3_UI_GAMMA_PASSWORD='Synthetic-Only-123!' \
  HADES_PHASE3_UI_STATE_FILE="$state_file" HADES_PHASE3_UI_REPORT="$report" \
  node "$repo_dir/scripts/dom-phase3-draft-transparency.js"

step='verifying staged state and failure diagnostics'
PYTHONPATH="$repo_dir" python3 - "$state_file" <<'PY'
import sys
from integrations.automation.phase3_self_service import Phase3Store
items = Phase3Store(sys.argv[1]).list_admin()
assert len(items) == 2, items
assert {item["template_type"] for item in items} == {"low-inventory-summary", "weekly-household-summary"}, items
assert all(item["status"] == "STAGED" and item["manual_runs"] == 0 and item["enabled"] is True for item in items), items
assert all(item["manual_runs"] == 0 for item in items), items
for item in items:
    audit = Phase3Store(sys.argv[1]).audit_for(item["automation_id"])
    assert sum(row["action"] == "create" for row in audit) == 1
low = next(item for item in items if item["template_type"] == "low-inventory-summary")
assert low["shared_with"] == [], low
assert [row["action"] for row in Phase3Store(sys.argv[1]).audit_for(low["automation_id"])].count("share") == 1
assert [row["action"] for row in Phase3Store(sys.argv[1]).audit_for(low["automation_id"])].count("revoke-share") == 1
PY
! grep -q 'HADES compatibility overlay initialization failed' "$work/hermes.log"
install -m 600 "$report" "${HADES_PHASE3_UI_REPORT:-/tmp/hades-phase3-draft-transparency-$$.json}"
echo 'PASS household draft confirmation is chat-scoped; sharing/revocation, granted drafts, duplicate protection, and honest no-run behavior are verified'
