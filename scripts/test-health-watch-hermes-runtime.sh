#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(readlink -f "$(command -v hermes || true)")
  [[ -z "$hermes_bin" ]] || hermes_python="$(dirname "$hermes_bin")/python3.11"
fi
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python 3.11 is unavailable' >&2; exit 2; }
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-health-watch-hermes.XXXXXX")
chmod 700 "$work"
trap 'find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true' EXIT
mkdir -m 700 "$work/home" "$work/hermes"

HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$repo_dir/hermes:$repo_dir:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner \
HADES_EPSILON_STATE_FILE="$work/epsilon.sqlite" \
HADES_EPSILON_HEALTH_SOURCES_JSON='{"hades-core":{"display_name":"HADES Core","url":"http://127.0.0.1:9/health"}}' \
HADES_SELF_SERVICE_SHARE_SUBJECTS=household-a:synthetic-household-a \
HADES_TASK_STATE_FILE="$work/tasks.sqlite" \
HADES_GROCY_AUDIT_FILE="$work/grocy-audit.jsonl" \
"$hermes_python" - "$repo_dir" <<'PY'
import time
import os
import run_agent
import sitecustomize as hades
from integrations.automation import HealthSource, HealthWatchService, HealthWatchSpec, HealthWatchStore

# A fresh install with no declared private endpoint must not inherit a
# development-host default.
health_sources_json = os.environ.pop("HADES_EPSILON_HEALTH_SOURCES_JSON", None)
try:
    assert hades._hades_health_watch_sources() == {}
finally:
    if health_sources_json is not None:
        os.environ["HADES_EPSILON_HEALTH_SOURCES_JSON"] = health_sources_json

owner = "synthetic-owner"
household = "synthetic-household-a"
chat = "synthetic-health-watch-race-chat"
conversation = hades._hades_turn_identity("yes", [], chat)
cache_key = f"session:{owner}:{conversation}"
assert conversation and cache_key

store = HealthWatchStore(hades._hades_health_watch_state_path())
source = HealthSource("hades-core", "HADES Core", "http://127.0.0.1:9/health")
service = HealthWatchService(store, {"hades-core": source}, resource_authorizer=lambda actor, resource: actor == owner and resource == "hades-core")
watch = store.create(
    HealthWatchSpec("synthetic-existing-watch", owner, "hades-core", "Existing Synthetic Watch", 10),
    "seed-existing-watch", owner,
)
assert watch["automation_id"] == "synthetic-existing-watch"
share_preview = "synthetic-second-worker-share-preview"
store.store_preview(
    share_preview,
    owner,
    {"kind": "action", "automation_id": watch["automation_id"], "action": "share",
     "grantee": household, "grantee_label": "household-a"},
    int(time.time()) + 600,
    conversation_id=conversation,
)

# Worker A remembers an older create preview locally. Worker B has persisted a
# newer share preview for this same server conversation. A real Hermes turn
# must prefer the shared persisted action when it receives the bare yes.
hades._HADES_PENDING_HEALTH_WATCH[cache_key] = {
    "preview_id": "synthetic-stale-create-preview",
    "request_key": "create:synthetic-stale-create-preview",
}
hades._hades_health_watch_runner = lambda: None
kwargs = {
    "base_url": "http://127.0.0.1:9/v1",
    "api_key": "synthetic-only",
    "provider": "custom",
    "api_mode": "chat_completions",
    "model": "synthetic-no-call",
    "enabled_toolsets": [],
    "disabled_toolsets": [],
    "quiet_mode": True,
    "skip_context_files": True,
    "skip_memory": True,
    "skip_background_review": True,
    "load_soul_identity": False,
}

def confirm(session_id):
    agent = run_agent.AIAgent(
        gateway_session_key=f"hades-user-{owner}",
        session_id=session_id,
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    assert agent._hades_subject == owner and agent._hades_session_scope == "owner"
    return agent.run_conversation(
        "yes",
        conversation_history=[{"role": "assistant", "content": "Shall I apply the current HADES preview?"}],
    )

result = confirm(chat)
assert result.get("completed") is True and result.get("api_calls") == 0, result
assert "updated sharing" in result.get("final_response", "").casefold(), result
assert store.get(watch["automation_id"])["shared_subjects"] == (household,)
assert len(store.list_all()) == 1, "stale local create preview created a duplicate automation"
assert store.latest_preview(owner, conversation_id=conversation) is None
assert cache_key not in hades._HADES_PENDING_HEALTH_WATCH
print("PASS Hermes runtime applied the persisted current share action over stale worker-local create state")

# Verify the inverse race through the same wrapper: a worker-local action cannot
# override the current persisted create preview. The unavailable runner makes
# the create path fail safely without changing automation state.
inverse_chat = "synthetic-health-watch-inverse-race-chat"
inverse_conversation = hades._hades_turn_identity("yes", [], inverse_chat)
inverse_key = f"session:{owner}:{inverse_conversation}"
current_create = service.preview(
    owner, owner=True, resource_id="hades-core", display_name="Current Synthetic Watch",
    interval_minutes=10, conversation_id=inverse_conversation,
)
hades._HADES_PENDING_HEALTH_WATCH[inverse_key] = {
    "automation_id": watch["automation_id"], "action": "unshare",
    "grantee": household, "grantee_label": "household-a",
}
inverse = confirm(inverse_chat)
assert inverse.get("completed") is True and inverse.get("api_calls") == 0, inverse
assert "runner is not available" in inverse.get("final_response", "").casefold(), inverse
assert store.latest_preview(owner, conversation_id=inverse_conversation)["preview_id"] == current_create["preview_id"]
assert store.get(watch["automation_id"])["shared_subjects"] == (household,)
assert len(store.list_all()) == 1
print("PASS Hermes runtime kept the persisted current create preview over stale worker-local action state")
PY
