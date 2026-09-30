#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Authenticated disposable Hindsight UI proof. Nothing connects to production.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
webui_image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
suffix="$$"
hindsight_name="hades-hindsight-ui-$suffix"
webui_name="hades-hindsight-webui-$suffix"
hindsight_volume="hades-hindsight-data-$suffix"
webui_volume="hades-hindsight-webui-data-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-hindsight-ui.XXXXXX")
webui_port=${HADES_HINDSIGHT_UI_WEBUI_PORT:-18884}
gateway_port=${HADES_HINDSIGHT_UI_GATEWAY_PORT:-18885}
api_key="synthetic-hades-ui-$suffix"
model="synthetic-hindsight-ui-extractor"
gateway_pid=''
mock_pid=''
step='preflight'

cleanup() {
  local exit_status=$?
  trap - EXIT
  if ((exit_status != 0)); then
    echo "FAIL synthetic Hindsight UI harness at step '$step' (exit $exit_status)" >&2
    local debug_dir="${HADES_HINDSIGHT_UI_DEBUG_DIR:-/tmp/hades-hindsight-ui-debug-$$}"
    mkdir -m 700 -p "$debug_dir"
    for artifact in hermes.log model.log model-requests.jsonl; do
      [[ -f "$work/$artifact" ]] && install -m 600 "$work/$artifact" "$debug_dir/$artifact"
    done
    if [[ -d "$work/debug" ]]; then
      find "$work/debug" -maxdepth 1 -type f -exec install -m 600 '{}' "$debug_dir" \;
    fi
    echo "Disposable failure diagnostics saved to $debug_dir" >&2
    [[ -f "$work/hermes.log" ]] && tail -n 80 "$work/hermes.log" >&2 || true
    [[ -f "$work/model.log" ]] && tail -n 20 "$work/model.log" >&2 || true
    docker logs --tail 40 "$hindsight_name" >&2 2>/dev/null || true
    docker logs --tail 40 "$webui_name" >&2 2>/dev/null || true
  fi
  if [[ -n "$gateway_pid" ]]; then kill "$gateway_pid" >/dev/null 2>&1 || true; wait "$gateway_pid" >/dev/null 2>&1 || true; fi
  if [[ -n "$mock_pid" ]]; then kill "$mock_pid" >/dev/null 2>&1 || true; wait "$mock_pid" >/dev/null 2>&1 || true; fi
  docker rm -f "$hindsight_name" "$webui_name" >/dev/null 2>&1 || true
  docker volume rm "$hindsight_volume" "$webui_volume" >/dev/null 2>&1 || true
  if [[ -d "$work" ]]; then find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true; fi
  exit "$exit_status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

command -v docker >/dev/null
command -v hermes >/dev/null
command -v node >/dev/null
command -v curl >/dev/null
export HADES_PLAYWRIGHT_MODULE=${HADES_PLAYWRIGHT_MODULE:-playwright}; node -e 'require(process.env.HADES_PLAYWRIGHT_MODULE)' >/dev/null 2>&1 || {
  echo 'FAIL local Playwright dependency is unavailable' >&2; exit 2;
}
docker image inspect "$HADES_HINDSIGHT_IMAGE" >/dev/null
docker image inspect "$webui_image" >/dev/null
for port in "$webui_port" "$gateway_port"; do
  if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
    echo "FAIL disposable test port is already occupied: $port" >&2
    exit 2
  fi
done
docker_gateway=$(docker network inspect bridge --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' | head -n1)
[[ "$docker_gateway" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || {
  echo 'FAIL Docker bridge gateway is unavailable' >&2; exit 2;
}
mkdir -p "$work"
chmod 700 "$work"
docker volume create "$hindsight_volume" >/dev/null
docker volume create "$webui_volume" >/dev/null

# The extraction stub binds only to the private Docker bridge gateway.
step='starting synthetic extraction endpoint'
python3 "$repo_dir/scripts/synthetic-hindsight-model.py" \
  "$docker_gateway" "$work/model.port" "$work/model-requests.jsonl" \
  >"$work/model.log" 2>&1 &
mock_pid=$!
for _ in $(seq 1 50); do
  [[ -s "$work/model.port" ]] && break
  kill -0 "$mock_pid" 2>/dev/null || { cat "$work/model.log" >&2; echo 'FAIL extraction stub exited' >&2; exit 1; }
  sleep 0.1
done
[[ -s "$work/model.port" ]] || { echo 'FAIL extraction stub did not bind' >&2; exit 1; }
model_port=$(cat "$work/model.port")

step='starting pinned Hindsight service'
docker run -d --name "$hindsight_name" --add-host host.docker.internal:host-gateway \
  -p '127.0.0.1::8888' -v "$hindsight_volume:/home/hindsight/.pg0" \
  -e HINDSIGHT_API_HOST=0.0.0.0 -e HINDSIGHT_API_PORT=8888 \
  -e HINDSIGHT_API_ENABLE_OBSERVATIONS=true -e "HINDSIGHT_API_WORKER_ID=$hindsight_name" \
  -e HINDSIGHT_API_LLM_PROVIDER=ollama -e "HINDSIGHT_API_LLM_MODEL=$model" \
  -e "HINDSIGHT_API_LLM_BASE_URL=http://host.docker.internal:$model_port/v1" \
  -e HINDSIGHT_API_LLM_API_KEY=synthetic-only "$HADES_HINDSIGHT_IMAGE" >/dev/null
hindsight_port=$(docker inspect -f '{{(index (index .NetworkSettings.Ports "8888/tcp") 0).HostPort}}' "$hindsight_name")
hindsight_url="http://127.0.0.1:$hindsight_port"
step='waiting for Hindsight health'
for _ in $(seq 1 120); do
  curl -fsS "$hindsight_url/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "$hindsight_url/health" >/dev/null

step='starting disposable Open WebUI'
docker run -d --name "$webui_name" --add-host host.docker.internal:host-gateway \
  -p "127.0.0.1:${webui_port}:8080" \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
  -e ENABLE_OPENAI_API=true \
  -e "OPENAI_API_BASE_URLS=http://host.docker.internal:${gateway_port}/v1" \
  -e "OPENAI_API_KEYS=$api_key" \
  -e 'OPENAI_API_CONFIGS={"0":{"headers":{"X-Hermes-Session-Key":"hades-user-{{USER_ID}}"}}}' \
  -e RAG_EMBEDDING_ENGINE=ollama -v "$webui_volume:/app/backend/data" \
  "$webui_image" >/dev/null
for _ in $(seq 1 120); do
  curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null
docker exec "$webui_name" python3 -c 'import json,sqlite3; db=sqlite3.connect("file:/app/backend/data/webui.db?mode=ro",uri=True); row=db.execute("select value from config where key=?",("openai.api_configs",)).fetchone(); config=json.loads(row[0]) if row else {}; assert config.get("0",{}).get("headers",{}).get("X-Hermes-Session-Key")=="hades-user-{{USER_ID}}", "Open WebUI did not seed the trusted Hermes identity header"'

step='creating synthetic Open WebUI users'
signup() {
  curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
    -H 'Content-Type: application/json' \
    --data "{\"name\":\"$1\",\"email\":\"$2\",\"password\":\"Synthetic-Only-123!\"}"
}
alpha_json=$(signup Alpha alpha-hindsight@example.invalid)
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$alpha_json")
alpha_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$alpha_json")
for account in Beta Gamma; do
  lower=$(tr '[:upper:]' '[:lower:]' <<<"$account")
  curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" \
    -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
    --data "{\"name\":\"$account\",\"email\":\"${lower}-hindsight@example.invalid\",\"password\":\"Synthetic-Only-123!\",\"role\":\"user\"}" >/dev/null
done
users_json=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/users/" -H "Authorization: Bearer $alpha_token")
beta_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); rows=x if isinstance(x,list) else x.get("users", x.get("items", [])); print(next(u["id"] for u in rows if isinstance(u,dict) and u.get("email")=="beta-hindsight@example.invalid"))' <<<"$users_json")
gamma_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); rows=x if isinstance(x,list) else x.get("users", x.get("items", [])); print(next(u["id"] for u in rows if isinstance(u,dict) and u.get("email")=="gamma-hindsight@example.invalid"))' <<<"$users_json")

# Pre-create only synthetic banks on the fresh disposable Hindsight volume.
step='creating synthetic Hindsight banks'
if [[ "${HADES_HINDSIGHT_UI_SKIP_BANK_BOOTSTRAP:-0}" != 1 ]]; then
HADES_HINDSIGHT_URL="$hindsight_url" python3 - "$alpha_id" "$beta_id" "$gamma_id" <<'PY'
import json, os, sys, urllib.request
base=os.environ['HADES_HINDSIGHT_URL']
for bank in ('hades-owner', *(f'hades-user-{subject}' for subject in sys.argv[1:])):
    req=urllib.request.Request(
        f'{base}/v1/default/banks/{bank}',
        data=json.dumps({'name':'Synthetic authenticated HADES UI acceptance'}).encode(),
        headers={'Content-Type':'application/json'}, method='PUT',
    )
    urllib.request.urlopen(req, timeout=10).read()
PY
else
  printf '%s\n' 'INFO Hindsight bank precreation disabled; authenticated HADES memory flow must create its scoped bank'
fi

step='configuring ephemeral Hermes profile'
export HERMES_HOME="$work/hermes"
mkdir -p "$HERMES_HOME"
chmod 700 "$HERMES_HOME"
hermes profile create hades --no-alias --no-skills >/dev/null
chmod 700 "$HERMES_HOME/profiles" "$HERMES_HOME/profiles/hades"
cat >"$HERMES_HOME/profiles/hades/config.yaml" <<'YAML'
model:
  default: synthetic-no-call
  provider: custom
  base_url: http://127.0.0.1:9/v1
memory:
  provider: hindsight
  bank_id: hades-owner
  bank_id_template: hades-user-{user}
  recall_budget: low
YAML
chmod 600 "$HERMES_HOME/profiles/hades/config.yaml"
hermes_bin=$(readlink -f "$(command -v hermes)")
hermes_python="$(dirname "$hermes_bin")/python3.11"
[[ -x "$hermes_python" ]] || { echo 'FAIL installed Hermes Python 3.11 is unavailable' >&2; exit 2; }
export HADES_HERMES_EXECUTABLE="$hermes_bin"
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
export PYTHONPATH="$repo_dir/hermes:$repo_dir:$hermes_source"
export HADES_HINDSIGHT_URL="$hindsight_url" HINDSIGHT_API_URL="$hindsight_url"
export HADES_TASK_STATE_FILE="$work/tasks.sqlite"
export HADES_OWNER_SUBJECT_IDS="$alpha_id"
export API_SERVER_ENABLED=true API_SERVER_KEY="$api_key"
export API_SERVER_HOST="$docker_gateway" API_SERVER_PORT="$gateway_port"
gateway_url="http://${docker_gateway}:${gateway_port}"
export OPENAI_API_KEY=synthetic-unused OPENAI_BASE_URL=http://127.0.0.1:9/v1
export MODEL=synthetic-no-call HERMES_ACCEPT_HOOKS=1

step='starting Hermes gateway'
hermes -p hades gateway run -v >"$work/hermes.log" 2>&1 &
gateway_pid=$!
for _ in $(seq 1 90); do
  curl -fsS "$gateway_url/health" >/dev/null 2>&1 && break
  kill -0 "$gateway_pid" 2>/dev/null || { cat "$work/hermes.log" >&2; echo 'FAIL Hermes gateway exited' >&2; exit 1; }
  sleep 1
done
curl -fsS "$gateway_url/health" >/dev/null
gateway_models=$(curl -fsS -H "Authorization: Bearer $api_key" "$gateway_url/v1/models")
model_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); print(x["data"][0]["id"] if x.get("data") else "")' <<<"$gateway_models")
[[ -n "$model_id" ]] || { cat "$work/hermes.log" >&2; echo 'FAIL Hermes gateway advertised no model' >&2; exit 1; }

step='configuring synthetic model access'
model_access=$(python3 - "$model_id" "$alpha_id" "$beta_id" "$gamma_id" <<'PY'
import json, sys
model, *users = sys.argv[1:]
print(json.dumps({'id':model, 'name':model, 'access_grants':[
  {'principal_type':'user','principal_id':user,'permission':'read'} for user in users
]}))
PY
)
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/models/model/access/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "$model_access" >/dev/null

step='authenticated browser acceptance'
report="$work/acceptance.json"
HADES_HINDSIGHT_UI_BASE_URL="http://127.0.0.1:${webui_port}" \
  HADES_HINDSIGHT_UI_ALPHA_EMAIL=alpha-hindsight@example.invalid \
  HADES_HINDSIGHT_UI_BETA_EMAIL=beta-hindsight@example.invalid \
  HADES_HINDSIGHT_UI_GAMMA_EMAIL=gamma-hindsight@example.invalid \
  HADES_HINDSIGHT_UI_PASSWORD='Synthetic-Only-123!' \
HADES_HINDSIGHT_UI_MODEL_ID="$model_id" \
HADES_HINDSIGHT_UI_REPORT="$report" \
  HADES_HINDSIGHT_UI_DEBUG_DIR="$work/debug" \
  node "$repo_dir/scripts/dom-hindsight-explicit-memory.js"

# The deterministic route runs before Hermes' normal prefetch step, so expect
# no prefetch marker and require a zero-model deterministic result for all
# five explicit-memory turns: two retains, Alpha recall, and Beta/Gamma.
step='checking explicit-route and cleanup evidence'
prefetch_count=$(grep -c 'Skipping automatic Hindsight prefetch for explicit memory route' "$work/hermes.log" || true)
direct_count=$(grep -c 'Explicit Hindsight deterministic path completed before homelab routing' "$work/hermes.log" || true)
[[ "$prefetch_count" == 0 ]] || { cat "$work/hermes.log" >&2; echo "FAIL deterministic memory route unexpectedly continued into automatic prefetch ($prefetch_count markers)" >&2; exit 1; }
(( direct_count >= 5 )) || { cat "$work/hermes.log" >&2; echo "FAIL expected at least 5 deterministic Hindsight turns; got $direct_count" >&2; exit 1; }
python3 - "$work/model-requests.jsonl" "$model" <<'PY'
import json, sys
from pathlib import Path
rows=[json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
assert rows, 'Hindsight retain did not call the synthetic extraction endpoint'
assert all(row['model']==sys.argv[2] for row in rows), rows
assert {row['path'] for row in rows} <= {'/api/chat','/v1/chat/completions'}, rows
PY
install -m 600 "$report" "${HADES_HINDSIGHT_UI_REPORT:-/tmp/hades-hindsight-explicit-ui-$$.json}"
echo 'PASS disposable authenticated Hindsight retain, correction, fresh recall, isolation, and chat persistence'
