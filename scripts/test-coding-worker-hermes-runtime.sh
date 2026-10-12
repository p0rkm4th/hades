#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(readlink -f "$(command -v hermes || true)" 2>/dev/null || true)
  [[ -z "$hermes_bin" ]] || hermes_python="$(dirname "$hermes_bin")/python"
fi
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes 0.21.2 Python is unavailable' >&2; exit 2; }
tmp=$(mktemp -d "${TMPDIR:-/tmp}/hades-coding-runtime.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
chmod 700 "$tmp"
HERMES_HOME="$tmp/hermes-home" \
HOME="$tmp" \
PYTHONPATH="$repo_dir/hermes" \
HADES_HERMES_OVERLAY_DIR="$repo_dir/hermes" \
HADES_CODING_PROJECT_ROOT="$repo_dir" \
HADES_CODING_WORKER_ENABLED=1 \
HADES_CODING_WORKER_CONVERSATION_ID=synthetic-owner-coding-conversation \
HADES_CODING_WORKSPACE_BINDINGS_FILE="$tmp/bindings.json" \
HADES_CODING_WORKSPACE_ROOT="$tmp/workspaces" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner \
"$hermes_python" - <<'PY'
import run_agent
import sitecustomize as hades
from hermes import coding_worker

assert run_agent.AIAgent.run_conversation.__name__ == "_hades_run_conversation"
calls = []
def fake_worker(**kwargs):
    calls.append(kwargs)
    return {"outcome": "SUCCEEDED", "final_response": "synthetic verified coding result"}

coding_worker.run_coding_worker = fake_worker
native_calls = []
def fake_native(self, *args, **kwargs):
    native_calls.append((self, args, kwargs))
    return {"final_response": "ordinary Hermes path", "messages": [], "api_calls": 1}
hades._hades_original_run_conversation = fake_native
base = {
    "base_url": "http://127.0.0.1:9/v1", "api_key": "synthetic-only",
    "provider": "custom", "api_mode": "chat_completions", "model": "synthetic-no-call",
    "enabled_toolsets": [], "disabled_toolsets": [], "quiet_mode": True,
    "skip_context_files": True, "skip_memory": True, "skip_background_review": True,
}
owner = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner",
    session_id="synthetic-owner-coding-conversation",
    stream_delta_callback=lambda _chunk: None,
    **base,
)
result = owner.run_conversation(
    "Inspect this repository and explain why the focused test fails.",
    conversation_history=[],
)
assert result["completed"] is True and result["final_response"] == "synthetic verified coding result", result
assert len(calls) == 1, calls
assert calls[0]["subject"] == "synthetic-owner"
assert calls[0]["scope"] == "owner"
assert calls[0]["conversation_id"] == "synthetic-owner-coding-conversation"
assert calls[0]["repo_root"] == __import__("pathlib").Path(".").resolve()

# Even with the feature flag enabled, a different conversation stays on the
# ordinary Hermes path; the disposable fixture cannot capture unrelated work.
other = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner",
    session_id="unallowlisted-conversation",
    stream_delta_callback=lambda _chunk: None,
    **base,
)
other_result = other.run_conversation(
    "Inspect this repository and explain why the focused test fails.",
    conversation_history=[],
)
assert len(calls) == 1, calls
assert len(native_calls) == 1 and native_calls[0][0] is other
assert other_result["final_response"] == "ordinary Hermes path"

household = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-household",
    session_id="synthetic-household-coding-conversation",
    stream_delta_callback=lambda _chunk: None,
    **base,
)
household_result = household.run_conversation(
    "Use Agent Zero to inspect this repository and fix the failing test.", conversation_history=[],
)
assert len(calls) == 1, calls
assert household_result["completed"] is True
assert "owner-only" in household_result["final_response"].casefold(), household_result
print("PASS: trusted owner coding request entered worker lane; household did not")
PY
