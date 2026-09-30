#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Synthetic authenticated UI proof for the read-only Backup Check freshness route.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
webui_image=${HADES_HINDSIGHT_UI_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
suffix="$$"
webui_name="hades-backup-ui-webui-$suffix"
webui_volume="hades-backup-ui-data-$suffix"
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-backup-ui.XXXXXX")
webui_port=${HADES_BACKUP_UI_WEBUI_PORT:-18888}
gateway_port=${HADES_BACKUP_UI_GATEWAY_PORT:-18889}
api_key="synthetic-hades-backup-ui-$suffix"
gateway_pid=''
step='preflight'

cleanup() {
  local status=$?
  trap - EXIT
  if ((status != 0)); then
    echo "FAIL authenticated backup freshness UI at step '$step'" >&2
    [[ -f "$work/hermes.log" ]] && tail -n 70 "$work/hermes.log" >&2 || true
    if [[ -n "${HADES_BACKUP_UI_DEBUG_DIR:-}" ]]; then
      mkdir -m 700 -p "$HADES_BACKUP_UI_DEBUG_DIR"
      [[ ! -f "$work/hermes.log" ]] || install -m 600 "$work/hermes.log" "$HADES_BACKUP_UI_DEBUG_DIR/hermes.log"
    fi
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

step='creating synthetic owner identity'
signup=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
  -H 'Content-Type: application/json' \
  --data '{"name":"Alpha","email":"alpha-backup@example.invalid","password":"Synthetic-Only-123!"}')
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$signup")
alpha_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$signup")

step='seeding synthetic canonical backup state'
state_file="$work/epsilon.sqlite"
PYTHONPATH="$repo_dir" python3 - "$state_file" "$alpha_id" <<'PY'
import sys
from integrations.automation import BackupObservation, BackupVerificationService, BackupVerificationSpec, LifecycleStore

path, actor = sys.argv[1:]
store = LifecycleStore(path)
store.put(
    "synthetic-backup", actor, "hades-backup-verification",
    {"target_id": "hades-repository", "shared_subjects": []}, "PROMOTED",
    {"automation_id": "synthetic-backup", "production_schedule": True},
)
BackupVerificationService(path, BackupVerificationSpec("synthetic-backup", actor)).observe([
    BackupObservation("hades-repository", "HEALTHY", "synthetic fixture", "2026-09-25T12:34:00+00:00")
])
infra_id = "synthetic-infrastructure-backup"
store.put(
    "synthetic-infrastructure-backup-op", actor, "hades-backup-verification",
    {"target_id": "infrastructure-repository", "shared_subjects": []}, "PROMOTED",
    {"automation_id": infra_id, "production_schedule": True},
)
infra = BackupVerificationService(path, BackupVerificationSpec(infra_id, actor))
infra.observe([
    BackupObservation("infrastructure-repository", "HEALTHY", "synthetic prior success", "2026-09-25T12:00:00+00:00")
])
infra.observe([
    BackupObservation("infrastructure-repository", "STALE", "synthetic stale artifact", "2026-09-26T12:34:00+00:00")
])
PY
before_hash=$(sha256sum "$state_file" | awk '{print $1}')

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

step='authenticated read-only browser acceptance'
report="$work/acceptance.json"
HADES_BACKUP_UI_BASE_URL="http://127.0.0.1:${webui_port}" \
  HADES_BACKUP_UI_PROMPT="${HADES_BACKUP_UI_PROMPT:-Do we have a recent backup?}" \
  HADES_BACKUP_UI_EMAIL=alpha-backup@example.invalid \
  HADES_BACKUP_UI_PASSWORD='Synthetic-Only-123!' HADES_BACKUP_UI_MODEL_ID="$model_id" \
  HADES_BACKUP_UI_DB_SHA256="$before_hash" HADES_BACKUP_UI_STATE_FILE="$state_file" \
  HADES_BACKUP_UI_REPORT="$report" node "$repo_dir/scripts/dom-backup-freshness-authenticated.js"

step='verifying no model call and clean failure diagnostics'
direct_count=$(grep -c 'Phase 2 backup freshness completed without model invocation' "$work/hermes.log" || true)
[[ "$direct_count" == 1 ]] || { echo "FAIL expected one direct read-only freshness route, got $direct_count" >&2; exit 1; }
! grep -q 'HADES compatibility overlay initialization failed' "$work/hermes.log"
install -m 600 "$report" "${HADES_BACKUP_UI_REPORT:-/tmp/hades-backup-freshness-ui-$$.json}"
echo 'PASS authenticated backup freshness wording returns canonical status, persists, makes no model call, and creates no action state'
