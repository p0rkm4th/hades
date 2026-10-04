#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Authenticated UI acceptance for Task attention and plain-language device
# troubleshooting clarification. Uses only synthetic identities and state.
# Uses the pinned local Open WebUI image, a temporary Hermes 0.21.2 profile,
# synthetic accounts/tasks, and loopback-only published ports.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
hermes_overlay_dir=${HADES_HERMES_OVERLAY_DIR:-$repo_dir/hermes}
# shellcheck disable=SC1091
source "$repo_dir/config/versions.env"
webui_image=${HADES_TASK_ATTENTION_WEBUI_IMAGE:-hades-open-webui:0.11.1-hades-reconstructed}
suffix="$$"
name="hades-task-attention-ui-$suffix"
volume="hades-task-attention-ui-$suffix"
work=$(mktemp -d "$HOME/.cache/hades-task-attention.XXXXXX")
acceptance_report=${HADES_TASK_ATTENTION_FINAL_REPORT:-${TMPDIR:-/tmp}/hades-task-attention-$$.json}
weekly_partial_mode=${HADES_TASK_ATTENTION_WEEKLY_PARTIAL:-0}
finance_monthly_mode=${HADES_TASK_ATTENTION_FINANCE_MONTHLY:-0}
network_diagnosis_mode=${HADES_TASK_ATTENTION_NETWORK_DIAGNOSIS:-0}
minecraft_preflight_mode=${HADES_TASK_ATTENTION_MINECRAFT_PREFLIGHT:-0}
minecraft_recovery_mode=${HADES_TASK_ATTENTION_MINECRAFT_RECOVERY:-0}
allow_notification_failure=${HADES_TASK_ATTENTION_ALLOW_NOTIFICATION_FAILURE:-0}
active_artifact_diagnostic=${HADES_TASK_ATTENTION_ACTIVE_ARTIFACT_DIAGNOSTIC:-0}
webui_port=${HADES_TASK_ATTENTION_WEBUI_PORT:-18882}
gateway_port=${HADES_TASK_ATTENTION_GATEWAY_PORT:-18883}
api_key="synthetic-api-$suffix"
[[ "$allow_notification_failure" == 0 || "$allow_notification_failure" == 1 ]] || {
  echo 'FAIL HADES_TASK_ATTENTION_ALLOW_NOTIFICATION_FAILURE must be 0 or 1' >&2
  exit 2
}
[[ "$active_artifact_diagnostic" == 0 || "$active_artifact_diagnostic" == 1 ]] || {
  echo 'FAIL HADES_TASK_ATTENTION_ACTIVE_ARTIFACT_DIAGNOSTIC must be 0 or 1' >&2
  exit 2
}
if [[ "$active_artifact_diagnostic" == 1 && ( "$allow_notification_failure" != 1 || "$minecraft_recovery_mode" != 1 ) ]]; then
  echo 'FAIL active-artifact diagnostic requires Minecraft recovery mode and explicit notification-failure characterization' >&2
  exit 2
fi
if [[ "$allow_notification_failure" == 1 && "$active_artifact_diagnostic" != 1 ]]; then
  echo 'FAIL notification failure may be bypassed only in the active-artifact Minecraft diagnostic' >&2
  exit 2
fi
if [[ "$active_artifact_diagnostic" == 1 ]]; then
  overlay_real=$(readlink -f "$hermes_overlay_dir")
  repo_overlay_real=$(readlink -f "$repo_dir/hermes")
  candidate_root=$(dirname "$overlay_real")
  case "$candidate_root/" in
    "$repo_dir/"*) echo 'FAIL active-artifact diagnostic requires a copied overlay outside the repository' >&2; exit 2 ;;
  esac
  [[ "$overlay_real" != "$repo_overlay_real" ]] || { echo 'FAIL active-artifact diagnostic cannot use tracked source as its active overlay' >&2; exit 2; }
  [[ ! -e "$candidate_root/integrations" ]] || { echo 'FAIL synthetic control adapter path already exists; refusing to overwrite' >&2; exit 2; }
  git -C "$repo_dir" archive HEAD integrations | tar -xf - -C "$candidate_root"
  cat >"$candidate_root/integrations/homelab-control/control.py" <<'PY'
"""No-network adapter used only by the active-overlay diagnostic harness."""
import json
import os
from pathlib import Path

def inspect_templates():
    aliases = sorted({
        entry.split(":", 1)[0].strip().lower()
        for entry in os.environ.get("HADES_PROXMOX_TEMPLATE_MAP", "").split(",")
        if ":" in entry and entry.split(":", 1)[1].strip().isdigit()
    })
    nodes = sorted({node.strip() for node in os.environ.get("HADES_PROXMOX_CONTROL_NODES", "").split(",") if node.strip()})
    return {"status": "READY" if aliases and nodes else "UNCONFIGURED", "templates": aliases, "approved_nodes": nodes, "writes_performed": False}

def provision_guest(template, target, *, name, cores=4, memory_mib=8192, disk_gib=0, owner_confirmed=False):
    path = Path(os.environ["HADES_TASK_ATTENTION_SYNTHETIC_CONTROL_CALLS"])
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    record = {"template": template, "name": name, "target": target, "cores": cores, "memory_mib": memory_mib, "disk_gib": disk_gib, "owner_confirmed": owner_confirmed}
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
    return {"status": "FAILED", "error": "synthetic no-network adapter intercepted provisioning", "writes_performed": False}
PY
  chmod 600 "$candidate_root/integrations/homelab-control/control.py"
  export HADES_INTEGRATIONS_ROOT="$candidate_root"
  export HADES_TASK_ATTENTION_SYNTHETIC_CONTROL_CALLS="$work/synthetic-control-calls.jsonl"
fi

cleanup() {
  local exit_code=$?
  if [[ -n ${gateway_pid:-} ]]; then kill "$gateway_pid" >/dev/null 2>&1 || true; wait "$gateway_pid" >/dev/null 2>&1 || true; fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker volume rm "$volume" >/dev/null 2>&1 || true
  if [[ -d "$work" && "$exit_code" -ne 0 && ${HADES_TASK_ATTENTION_KEEP_FAILED:-0} == 1 ]]; then
    printf 'Preserved failed disposable diagnostics at %s\n' "$work" >&2
  elif [[ -d "$work" ]]; then
    find "$work" -depth -mindepth 1 -delete 2>/dev/null || true
    rmdir "$work" 2>/dev/null || true
  fi
}
trap cleanup EXIT

command -v docker >/dev/null
command -v hermes >/dev/null
for port in "$webui_port" "$gateway_port"; do
  if (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
    echo "FAIL disposable test port is already occupied: $port" >&2
    exit 2
  fi
done
docker image inspect "$webui_image" >/dev/null
mkdir -p "$work/home" "$work/hermes"
chmod 700 "$work/home" "$work/hermes"
if [[ "$weekly_partial_mode" == 1 && "$finance_monthly_mode" == 1 ]] ||
   [[ "$network_diagnosis_mode" == 1 && ( "$weekly_partial_mode" == 1 || "$finance_monthly_mode" == 1 ) ]] ||
   [[ "$minecraft_preflight_mode" == 1 && ( "$weekly_partial_mode" == 1 || "$finance_monthly_mode" == 1 || "$network_diagnosis_mode" == 1 || "$minecraft_recovery_mode" == 1 ) ]] ||
   [[ "$minecraft_recovery_mode" == 1 && ( "$weekly_partial_mode" == 1 || "$finance_monthly_mode" == 1 || "$network_diagnosis_mode" == 1 ) ]]; then
  echo 'FAIL authenticated UI acceptance modes are mutually exclusive' >&2
  exit 2
fi
if [[ "$finance_monthly_mode" == 1 ]]; then
  python3 - "$work/finance.csv" <<'PY'
import calendar
import sys
from datetime import date
from pathlib import Path

today = date.today()
previous_year, previous_month = (
    (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
)
cutoff = min(15, today.day)
previous_cutoff = min(cutoff, calendar.monthrange(previous_year, previous_month)[1])
rows = [
    (date(previous_year, previous_month, min(5, previous_cutoff)), "Food Market", "-80.00", "Groceries", "Posted"),
    (date(previous_year, previous_month, previous_cutoff), "Town Cafe", "-20.00", "Restaurants", "Posted"),
    (date(previous_year, previous_month, previous_cutoff), "Power Company", "-100.00", "Utilities", "Posted"),
    (date(today.year, today.month, min(5, cutoff)), "Food Market", "-120.00", "Groceries", "Posted"),
    (date(today.year, today.month, cutoff), "Town Cafe", "-80.00", "Restaurants", "Pending"),
    (date(today.year, today.month, cutoff), "Power Company", "-100.00", "Utilities", "Posted"),
    (date(today.year, today.month, cutoff), "Paycheck", "2500.00", "Income", "Posted"),
]
path = Path(sys.argv[1])
path.write_text(
    "Date,Description,Amount,Category,Status\n"
    + "".join(f"{when},{description},{amount},{category},{status}\n" for when, description, amount, category, status in rows),
    encoding="utf-8",
)
PY
else
cat >"$work/finance.csv" <<'CSV'
Date,Description,Amount,Category,Status
2026-01-05,Main Street Market,-100.00,Groceries,Posted
2026-01-06,Joe's Coffee,-12.00,Coffee,Posted
2026-02-03,Northside Restaurant,-40.00,Restaurants,Posted
2026-02-28,Market,-80.00,Grocery,Posted
CSV
fi
chmod 600 "$work/finance.csv"
if [[ "$minecraft_preflight_mode" == 1 ]]; then
  export HADES_PROXMOX_TEMPLATE_MAP= HADES_PROXMOX_CONTROL_NODES=
elif [[ "$minecraft_recovery_mode" == 1 ]]; then
  export HADES_PROXMOX_TEMPLATE_MAP=minecraft:9001 HADES_PROXMOX_CONTROL_NODES=SyntheticNode
  unset HADES_PROXMOX_CONTROL_URL HADES_PROXMOX_CONTROL_TOKEN_ID HADES_PROXMOX_CONTROL_TOKEN_FILE HADES_PROXMOX_CONTROL_CA_FILE
fi
homelab_root="$work/synthetic-homelab"
mkdir -p "$homelab_root/integrations/homelab-readonly"
cat >"$homelab_root/integrations/homelab-readonly/server.py" <<'PY'
def homelab_summary():
    return {
        "status": "OK",
        "online_names": ["hades-core"],
        "inventory_only_names": [],
        "availability_summary": [
            {"name": "Minecraft Server", "status": "up", "freshness": "FRESH"},
            {"name": "Search", "status": "down", "freshness": "FRESH"},
            {"name": "Router ping", "status": "up", "freshness": "FRESH", "ping_ms": 84},
            {"name": "Jellyfin", "status": "down", "freshness": "STALE"},
            {"name": "specialized-inference-node", "status": "up", "freshness": "FRESH"},
            {"name": "management-node", "status": "down", "freshness": "FRESH"},
            {"name": "Hermes", "status": "up", "freshness": "STALE"},
        ],
        "conflicts": [],
        "errors": [],
        "resources": [{
            "name": "hades-core",
            "runtime_status": "running",
            "currently_online": True,
            "runtime": {"name": "hades-core", "vmid": 802, "status": "running"},
        }, {
            "name": "Minecraft Server",
            "runtime_status": "NOT_OBSERVED",
            "currently_online": False,
            "availability": {"name": "Minecraft Server", "status": "up", "last_updated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
            "availability_freshness": "FRESH",
        }, {
            "name": "specialized-inference-node",
            "runtime_status": "NOT_OBSERVED",
            "currently_online": False,
            "availability": {"name": "specialized-inference-node", "status": "up", "last_updated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
            "availability_freshness": "FRESH",
        }, {
            "name": "management-node",
            "runtime_status": "NOT_OBSERVED",
            "currently_online": False,
            "availability": {"name": "management-node", "status": "down", "last_updated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},
            "availability_freshness": "FRESH",
        }, {
            "name": "Hermes",
            "runtime_status": "NOT_OBSERVED",
            "currently_online": False,
            "availability": {"name": "Hermes", "status": "up", "last_updated": "2000-01-01T00:00:00+00:00"},
            "availability_freshness": "STALE",
        }],
    }

def homelab_compute_capabilities():
    return {"machines": []}
PY
chmod -R go-rwx "$homelab_root"
capability_matrix="$work/capability-matrix.yaml"
cat >"$capability_matrix" <<'YAML'
machines:
  - name: deep-inference-node
    address: 192.0.2.69
    role: synthetic inference node
  - name: specialized-inference-node
    address: 192.0.2.73
    role: synthetic inference node
  - name: management-node
    address: 192.0.2.75
    role: synthetic management node
  - name: Hermes
    address: 192.0.2.152
    role: synthetic inference node
YAML
docker volume create "$volume" >/dev/null

export HERMES_HOME="$work/hermes"
hermes_bin=$(readlink -f "$(command -v hermes)")
export HADES_HERMES_EXECUTABLE="$hermes_bin"
hermes_python=${HADES_HERMES_PYTHON:-"$(dirname "$hermes_bin")/python3.11"}
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python interpreter is unavailable; set HADES_HERMES_PYTHON when using a versioned runtime' >&2; exit 2; }
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
export PYTHONPATH="$hermes_overlay_dir:$repo_dir:$hermes_source"
export HADES_TASK_STATE_FILE="$work/tasks.sqlite"
export HADES_HERMES_WORKING_DIRECTORY="$homelab_root"
export HADES_CAPABILITY_MATRIX_FILE="$capability_matrix"
export HADES_EPSILON_STATE_FILE="$work/epsilon-automation.sqlite"
export HADES_FINANCE_CSV_PATH="$work/finance.csv"
export GROCY_URL=http://127.0.0.1:9 GROCY_API_KEY=synthetic-unreachable
export API_SERVER_ENABLED=true API_SERVER_KEY="$api_key" API_SERVER_MODEL_NAME=hermes-agent
export API_SERVER_HOST=0.0.0.0 API_SERVER_PORT="$gateway_port"
export OPENAI_API_KEY=synthetic-unused
export OPENAI_BASE_URL=http://127.0.0.1:9/v1
export MODEL=synthetic-no-call
export HERMES_ACCEPT_HOOKS=1

docker run -d --name "$name" --add-host host.docker.internal:host-gateway \
  -p "127.0.0.1:${webui_port}:8080" \
  -v "$repo_dir/webui/hades-theme.js:/app/backend/open_webui/static/hades-theme.js:ro" \
  -v "$repo_dir/webui/hades-theme.js:/app/build/static/hades-theme.js:ro" \
  -e ENABLE_SIGNUP=true -e ENABLE_LOGIN_FORM=true -e ENABLE_OLLAMA_API=false \
  -e HADES_TASK_NOTIFICATIONS_HERMES_API_BASE_URL="http://host.docker.internal:${gateway_port}/v1" \
  -e HADES_TASK_NOTIFICATIONS_HERMES_API_KEY="$api_key" \
  -e RAG_EMBEDDING_ENGINE=ollama -v "$volume:/app/backend/data" \
  "$webui_image" >/dev/null

for _ in $(seq 1 120); do
  curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${webui_port}/health" >/dev/null

signup() {
  curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signup" \
    -H 'Content-Type: application/json' \
    --data "{\"name\":\"$1\",\"email\":\"$2\",\"password\":\"Synthetic-Only-123!\"}"
}
alpha_json=$(signup Alpha alpha-attention@example.invalid)
alpha_token=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$alpha_json")
alpha_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"$alpha_json")
for account in Beta Gamma; do
  lower=$(tr '[:upper:]' '[:lower:]' <<<"$account")
  curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/add" \
    -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
    --data "{\"name\":\"$account\",\"email\":\"${lower}-attention@example.invalid\",\"password\":\"Synthetic-Only-123!\",\"role\":\"user\"}" >/dev/null
done
users_json=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/users/" -H "Authorization: Bearer $alpha_token")
beta_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); rows=x if isinstance(x,list) else x.get("users", x.get("items", [])); print(next(u["id"] for u in rows if isinstance(u,dict) and u.get("email")=="beta-attention@example.invalid"))' <<<"$users_json")
gamma_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); rows=x if isinstance(x,list) else x.get("users", x.get("items", [])); print(next(u["id"] for u in rows if isinstance(u,dict) and u.get("email")=="gamma-attention@example.invalid"))' <<<"$users_json")
beta_token=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  --data '{"email":"beta-attention@example.invalid","password":"Synthetic-Only-123!"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
gamma_token=$(curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/auths/signin" \
  -H 'Content-Type: application/json' \
  --data '{"email":"gamma-attention@example.invalid","password":"Synthetic-Only-123!"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')

# The summary path executes before provider/model dispatch. A deliberately
# unreachable model endpoint makes any accidental escalation fail visibly.
HADES_TASK_ATTENTION_WEEKLY_PARTIAL="$weekly_partial_mode" python3 - "$repo_dir" "$HADES_TASK_STATE_FILE" "$alpha_id" "$beta_id" "$gamma_id" "$HADES_EPSILON_STATE_FILE" <<'PY'
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1])))
from integrations.task import TaskStatus, TaskStore
from integrations.automation import (
    BackupObservation,
    BackupVerificationService,
    BackupVerificationSpec,
    LifecycleStore,
    SummaryHistory,
    compose_summary,
)
store = TaskStore(sys.argv[2])
for task_id, subject, goal, status in (
    ("task-alpha-approval", sys.argv[3], "Alpha synthetic dinner plan", TaskStatus.AWAITING_APPROVAL),
    ("task-beta-private", sys.argv[4], "Beta private synthetic plan", TaskStatus.BLOCKED),
    ("task-gamma-private", sys.argv[5], "Gamma private synthetic plan", TaskStatus.FAILED),
):
    store.create(task_id=task_id, actor_subject_id=subject, goal=goal, status=status)
state = sys.argv[6]
automation = LifecycleStore(state)
backup_result = {"automation_id": "synthetic-owner-backup", "production_schedule": True}
automation.put(
    "synthetic-owner-backup-operation", sys.argv[3], "hades-backup-verification",
    {"target_id": "hades-repository", "shared_subjects": []}, "PROMOTED", backup_result,
)
BackupVerificationService(
    state, BackupVerificationSpec("synthetic-owner-backup", sys.argv[3])
).observe([BackupObservation(
    "hades-repository", "HEALTHY", "synthetic test evidence",
    datetime.now(timezone.utc).isoformat(),
)])

def fail_grocy():
    raise OSError("synthetic Grocy outage")

if os.environ.get("HADES_TASK_ATTENTION_WEEKLY_PARTIAL") == "1":
    partial_weekly = compose_summary(
        {
            "grocy.household": ("Groceries", fail_grocy),
            "hades-core.health": ("Servers", lambda: "All servers look okay."),
            "backup.evidence": ("Backups", lambda: "Last verified backup is healthy."),
        },
        lambda _resource: True,
    )
    automation.put(
        "synthetic-owner-weekly-summary", sys.argv[3], "weekly-household-summary",
        {"shared_subjects": [sys.argv[4]]}, "PROMOTED",
        {"status": "PROMOTED", "production_schedule": True},
    )
    SummaryHistory(state).record(sys.argv[3], datetime.now(timezone.utc).isoformat(), partial_weekly, "groceries")
PY

# Start the real Hermes API gateway only after synthetic user IDs and Task
# state exist, so the owner mapping is fixed in the service environment.
export HADES_OWNER_SUBJECT_IDS="$alpha_id"
hermes profile create hades --no-alias --no-skills >/dev/null
cat >"$HERMES_HOME/profiles/hades/config.yaml" <<'YAML'
model:
  default: synthetic-no-call
  provider: custom
  base_url: http://127.0.0.1:9/v1
YAML
chmod 600 "$HERMES_HOME/profiles/hades/config.yaml"
unset OPENROUTER_API_KEY ANTHROPIC_API_KEY GOOGLE_API_KEY GEMINI_API_KEY
hermes -p hades gateway run --quiet >"$work/hermes.log" 2>&1 &
gateway_pid=$!
for _ in $(seq 1 90); do
  curl -fsS "http://127.0.0.1:${gateway_port}/health" >/dev/null 2>&1 && break
  kill -0 "$gateway_pid" 2>/dev/null || { cat "$work/hermes.log" >&2; echo 'FAIL Hermes gateway exited' >&2; exit 1; }
  sleep 1
done
gateway_models=$(curl -fsS -H "Authorization: Bearer $api_key" "http://127.0.0.1:${gateway_port}/v1/models")
model_id=$(python3 -c 'import json,sys; x=json.load(sys.stdin); print(x["data"][0]["id"] if x.get("data") else "")' <<<"$gateway_models")
[[ -n "$model_id" ]] || { echo 'FAIL Hermes gateway advertised no model' >&2; exit 1; }

# The same-origin endpoint must derive the Hermes actor from Open WebUI's
# verified account and return only that account's current Task notifications.
unauthenticated_status=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:${webui_port}/api/v1/hades/tasks/notifications")
[[ "$unauthenticated_status" == 401 ]] || { echo "FAIL unauthenticated Task notification request returned HTTP $unauthenticated_status" >&2; exit 1; }
task_store_before=$(sha256sum "$HADES_TASK_STATE_FILE" | awk '{print $1}')
task_notification_status=$(curl -sS -D "$work/task-notifications.headers" -o "$work/task-notifications.body" -w '%{http_code}' \
  "http://127.0.0.1:${webui_port}/api/v1/hades/tasks/notifications" -H "Authorization: Bearer $alpha_token")
if [[ "$allow_notification_failure" == 1 ]]; then
  [[ "$task_notification_status" == 503 ]] || { echo "FAIL diagnostic expected Task notification HTTP 503, got $task_notification_status" >&2; exit 1; }
  grep -q 'temporarily unavailable' "$work/task-notifications.body" || { echo 'FAIL Task notification 503 was not the sanitized unavailable response' >&2; exit 1; }
  printf '%s\n' 'DIAGNOSTIC: authenticated Task notification feed is unavailable (HTTP 503); continuing only to isolate the requested chat workflow.'
else
  [[ "$task_notification_status" == 200 ]] || { echo "FAIL authenticated Task notification request returned HTTP $task_notification_status" >&2; exit 1; }
  grep -qi '^cache-control: no-store' "$work/task-notifications.headers" || { echo 'FAIL Task notification response is cacheable' >&2; exit 1; }
  for entry in "alpha:$alpha_token:task-alpha-approval:task-beta-private:task-gamma-private" \
               "beta:$beta_token:task-beta-private:task-alpha-approval:task-gamma-private" \
               "gamma:$gamma_token:task-gamma-private:task-alpha-approval:task-beta-private"; do
    IFS=: read -r account token own foreign_one foreign_two <<<"$entry"
    snapshot=$(curl -fsS "http://127.0.0.1:${webui_port}/api/v1/hades/tasks/notifications" -H "Authorization: Bearer $token")
    SNAPSHOT="$snapshot" OWN="$own" FOREIGN_ONE="$foreign_one" FOREIGN_TWO="$foreign_two" python3 - <<'PY'
import json, os
value = json.loads(os.environ['SNAPSHOT'])
assert value['version'] == 1
ids = {row['task_id'] for row in value['tasks']}
assert os.environ['OWN'] in ids, (os.environ['OWN'], ids)
assert os.environ['FOREIGN_ONE'] not in ids and os.environ['FOREIGN_TWO'] not in ids, ids
PY
  done
fi
task_store_after=$(sha256sum "$HADES_TASK_STATE_FILE" | awk '{print $1}')
[[ "$task_store_before" == "$task_store_after" ]] || { echo 'FAIL Task notification reads changed TaskStore bytes' >&2; exit 1; }

# Configure a per-user server-side identity header. Open WebUI itself expands
# USER_ID; the browser never supplies the Hermes subject header.
curl -fsS -X POST "http://127.0.0.1:${webui_port}/openai/config/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "{\"ENABLE_OPENAI_API\":true,\"OPENAI_API_BASE_URLS\":[\"http://host.docker.internal:${gateway_port}/v1\"],\"OPENAI_API_KEYS\":[\"${api_key}\"],\"OPENAI_API_CONFIGS\":{\"0\":{\"headers\":{\"X-Hermes-Session-Key\":\"hades-user-{{USER_ID}}\"}}}}" >/dev/null
model_access=$(python3 - "$model_id" "$alpha_id" "$beta_id" "$gamma_id" <<'PY'
import json, sys
model, *users = sys.argv[1:]
print(json.dumps({"id": model, "name": model, "access_grants": [
    {"principal_type": "user", "principal_id": user, "permission": "read"}
    for user in users
]}))
PY
)
curl -fsS -X POST "http://127.0.0.1:${webui_port}/api/v1/models/model/access/update" \
  -H "Authorization: Bearer $alpha_token" -H 'Content-Type: application/json' \
  --data "$model_access" >/dev/null

task_store_before_ui=$(sha256sum "$HADES_TASK_STATE_FILE" | awk '{print $1}')
finance_csv_before_ui=$(sha256sum "$HADES_FINANCE_CSV_PATH" | awk '{print $1}')
HADES_TASK_ATTENTION_DOM_BASE_URL="http://127.0.0.1:${webui_port}" \
  HADES_TASK_ATTENTION_REPO_DIR="$repo_dir" \
  HADES_TASK_ATTENTION_TASK_DB="$HADES_TASK_STATE_FILE" \
  HADES_TASK_ATTENTION_ALPHA_EMAIL=alpha-attention@example.invalid \
  HADES_TASK_ATTENTION_BETA_EMAIL=beta-attention@example.invalid \
  HADES_TASK_ATTENTION_GAMMA_EMAIL=gamma-attention@example.invalid \
  HADES_TASK_ATTENTION_PASSWORD=Synthetic-Only-123! \
HADES_TASK_ATTENTION_MODEL_ID="$model_id" \
HADES_TASK_ATTENTION_REPORT="$acceptance_report" \
HADES_TASK_ATTENTION_WEEKLY_PARTIAL="$weekly_partial_mode" \
HADES_TASK_ATTENTION_FINANCE_MONTHLY="$finance_monthly_mode" \
HADES_TASK_ATTENTION_MINECRAFT_RECOVERY="$minecraft_recovery_mode" \
HADES_TASK_ATTENTION_ACTIVE_ARTIFACT_DIAGNOSTIC="$active_artifact_diagnostic" \
HADES_TASK_ATTENTION_SYNTHETIC_CONTROL_CALLS="${HADES_TASK_ATTENTION_SYNTHETIC_CONTROL_CALLS:-}" \
HADES_TASK_ATTENTION_EPSILON_DB="$HADES_EPSILON_STATE_FILE" \
node "$repo_dir/scripts/dom-task-attention.js"
! grep -Fq 'HADES compatibility overlay initialization failed' "$work/hermes.log" || {
  echo 'FAIL Hermes overlay did not initialize cleanly' >&2; exit 1;
}

if [[ "$finance_monthly_mode" == 1 ]]; then
  task_store_after_ui=$(sha256sum "$HADES_TASK_STATE_FILE" | awk '{print $1}')
  finance_csv_after_ui=$(sha256sum "$HADES_FINANCE_CSV_PATH" | awk '{print $1}')
  [[ "$task_store_before_ui" == "$task_store_after_ui" ]] || { echo 'FAIL finance question changed TaskStore state' >&2; exit 1; }
  [[ "$finance_csv_before_ui" == "$finance_csv_after_ui" ]] || { echo 'FAIL finance question changed its statement fixture' >&2; exit 1; }
  echo 'PASS finance UI read-only state, owner model-free route, and household pre-inference denial'
fi

python3 - "$repo_dir" "$HADES_TASK_STATE_FILE" "$alpha_id" "$beta_id" "$gamma_id" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from integrations.task import TaskStatus, TaskStore
store = TaskStore(sys.argv[2])
expected = (
    ("task-alpha-approval", sys.argv[3], TaskStatus.AWAITING_APPROVAL),
    ("task-beta-private", sys.argv[4], TaskStatus.BLOCKED),
    ("task-gamma-private", sys.argv[5], TaskStatus.FAILED),
)
for task_id, subject, status in expected:
    current = store.get(task_id, subject)
    assert current["status"] == status.value, current
PY

if [[ "$active_artifact_diagnostic" == 1 ]]; then
  echo 'DIAGNOSTIC ONLY: active-overlay Minecraft transcript characterized with a synthetic no-network control adapter; Task notifications were unavailable and do not count as acceptance.'
elif [[ "$allow_notification_failure" == 1 ]]; then
  echo 'DIAGNOSTIC ONLY: Task notifications were unavailable; this run does not count as full Task attention acceptance.'
else
  echo 'PASS disposable authenticated Open WebUI/Hermes Task attention and TV-device clarification acceptance'
fi
