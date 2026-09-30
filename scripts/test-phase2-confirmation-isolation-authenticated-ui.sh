#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Two synthetic chats share one owner subject; a bare yes must remain chat-scoped.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
overlay_dir=${HADES_HERMES_OVERLAY_DIR:-$repo_dir/hermes}
[[ -f "$overlay_dir/sitecustomize.py" ]] || { echo "FAIL HADES overlay directory has no sitecustomize.py: $overlay_dir" >&2; exit 2; }
webui_image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
suffix="$$"
webui_name="hades-confirm-ui-webui-$suffix"
webui_volume="hades-confirm-ui-data-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-confirm-ui.XXXXXX")
webui_port=${HADES_CONFIRM_UI_WEBUI_PORT:-18890}
gateway_port=${HADES_CONFIRM_UI_GATEWAY_PORT:-18891}
api_key="synthetic-hades-confirm-ui-$suffix"
gateway_pid=''
step='preflight'

cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then
    echo "FAIL authenticated confirmation isolation at step '$step'" >&2
    local debug_dir="${HADES_CONFIRM_UI_DEBUG_DIR:-/tmp/hades-confirm-ui-debug-$$}"
    mkdir -m 700 -p "$debug_dir"
    [[ -f "$work/hermes.log" ]] && install -m 600 "$work/hermes.log" "$debug_dir/hermes.log"
    [[ -f "$work/acceptance.json" ]] && install -m 600 "$work/acceptance.json" "$debug_dir/acceptance.json"
    echo "Synthetic failure diagnostics saved to $debug_dir" >&2
    rg 'Backup Verification|Phase2 backup turn|confirmation|deterministic path' "$work/hermes.log" | tail -n 35 >&2 || true
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

step='creating synthetic owner and confirmation target'
signup=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Alpha","email":"alpha-confirm@example.invalid","password":"Synthetic-Only-123!"}')
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$signup")
alpha_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$signup")
state_file="$work/epsilon.sqlite"
PYTHONPATH="$repo_dir" python3 - "$state_file" "$alpha_id" <<'PY'
import sys
from integrations.automation import LifecycleStore

path, actor = sys.argv[1:]
LifecycleStore(path).put(
    "synthetic-backup-operation", actor, "hades-backup-verification",
    {"target_id": "hades-repository", "interval_minutes": 1440, "shared_subjects": []},
    "PROMOTED",
    {"automation_id": "synthetic-backup", "workflow_id": "synthetic-never-run", "production_schedule": True, "status": "PROMOTED"},
)
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
export PYTHONPATH="$overlay_dir:$repo_dir:$hermes_source"
export HADES_OWNER_SUBJECT_IDS="$alpha_id" HADES_EPSILON_STATE_FILE="$state_file"
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

step='configuring authenticated model access'
curl -fsS -X POST "http://127.0.0.1:${webui_port}/openai/config/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${gateway_port}/v1\"],\"OPENAI_API_KEYS\":[\"${api_key}\"],\"OPENAI_API_CONFIGS\":{\"0\":{\"headers\":{\"X-Hermes-Session-Key\":\"hades-user-{{USER_ID}}\"}}}}" >/dev/null
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/models/model/access/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "$(python3 -c 'import json,sys; print(json.dumps({"id":sys.argv[1],"name":sys.argv[1],"access_grants":[{"principal_type":"user","principal_id":sys.argv[2],"permission":"read"}]}))' "$model_id" "$alpha_id")" >/dev/null

step='authenticated cross-chat confirmation acceptance'
report="$work/acceptance.json"
HADES_CONFIRM_UI_BASE_URL="http://127.0.0.1:${webui_port}" \
  HADES_CONFIRM_UI_EMAIL=alpha-confirm@example.invalid \
  HADES_CONFIRM_UI_PASSWORD='Synthetic-Only-123!' HADES_CONFIRM_UI_MODEL_ID="$model_id" \
  HADES_CONFIRM_UI_STATE_FILE="$state_file" HADES_CONFIRM_UI_REPORT="$report" \
  node "$repo_dir/scripts/dom-phase2-confirmation-isolation.js"

# Optional diagnostic for an instrumented, disposable overlay copy. The report
# retains only equality checks; raw session IDs never leave the synthetic log.
if [[ -n ${HADES_CONFIRM_UI_SESSION_TRACE_REPORT:-} ]]; then
  python3 - "$work/hermes.log" "$HADES_CONFIRM_UI_SESSION_TRACE_REPORT" <<'PY'
import json
import re
import sys
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
pattern = re.compile(r"HADES_CONFIRMATION_TRACE sid_hash=([0-9a-f]+) text='([^']*)'")
seen = {}
for line in lines:
    match = pattern.search(line)
    if match:
        seen.setdefault(match.group(2), []).append(match.group(1))
required = ("Run Backup Check.", "Yes.", "No.")
if any(len(seen.get(prompt, [])) != 1 for prompt in required):
    raise SystemExit("FAIL expected one Hermes session trace for each synthetic user turn")
first, cross_chat, decline = (seen[prompt][0] for prompt in required)
result = {
    "status": "PASS" if first == decline and first != cross_chat else "FAIL",
    "same_chat_stable_across_reload": first == decline,
    "separate_chat_ids_distinct": first != cross_chat,
    "trace_values_redacted": True,
}
if result["status"] != "PASS":
    raise SystemExit("FAIL Hermes-derived conversation identity changed or collided")
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
Path(sys.argv[2]).chmod(0o600)
PY
fi

step='verifying confirmation removal and model-free routing'
PYTHONPATH="$repo_dir" python3 - "$state_file" "$alpha_id" <<'PY'
import sys
from integrations.automation import LifecycleStore

store = LifecycleStore(sys.argv[1])
assert store.pending_for_actor(sys.argv[2]) == [], store.pending_for_actor(sys.argv[2])
PY
! grep -q 'HADES compatibility overlay initialization failed' "$work/hermes.log"
install -m 600 "$report" "${HADES_CONFIRM_UI_REPORT:-/tmp/hades-phase2-confirmation-isolation-$$.json}"
echo 'PASS authenticated two-chat Backup Check confirmation isolation and same-chat decline'
