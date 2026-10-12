#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
overlay_dir=${HADES_TEST_OVERLAY_DIR:-"$repo_dir/hermes"}
hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(readlink -f "$(command -v hermes || true)" 2>/dev/null || true)
  [[ -z "$hermes_bin" ]] || hermes_python="$(dirname "$hermes_bin")/python"
fi
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes 0.21.2 Python is unavailable' >&2; exit 2; }
tmp=$(mktemp -d "${TMPDIR:-/tmp}/hades-coding-runtime.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
chmod 700 "$tmp"
(
cd "$tmp"
HERMES_HOME="$tmp/hermes-home" \
HOME="$tmp" \
PYTHONPATH="$overlay_dir" \
HADES_HERMES_OVERLAY_DIR="$overlay_dir" \
HADES_CODING_PROJECT_ROOT="$repo_dir" \
HADES_CODING_WORKER_ENABLED=1 \
HADES_CODING_WORKER_CONVERSATION_ID=synthetic-openwebui-chat-id \
HADES_CODING_WORKSPACE_BINDINGS_FILE="$tmp/bindings.json" \
HADES_CODING_WORKSPACE_ROOT="$tmp/workspaces" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner \
"$hermes_python" - <<'PY'
import os
import sys
import run_agent
import sitecustomize as hades
from pathlib import Path
import asyncio
from types import SimpleNamespace

assert Path(hades.__file__).resolve() == Path(__import__("os").environ["HADES_HERMES_OVERLAY_DIR"]) / "sitecustomize.py", hades.__file__
project_root = Path(os.environ["HADES_CODING_PROJECT_ROOT"]).resolve()
assert str(project_root) not in sys.path
coding_worker = hades._hades_import_coding_worker()
assert Path(coding_worker.__file__).resolve() == project_root / "hermes" / "coding_worker.py"
assert str(project_root) in sys.path

assert run_agent.AIAgent.run_conversation.__name__ == "_hades_run_conversation"

# Exercise the same request wrapper used at the Hermes HTTP boundary. Two
# concurrent chats must retain independent Open WebUI IDs through awaits.
async def fake_handler(_self, request):
    return await asyncio.get_running_loop().run_in_executor(
        None, hades._hades_openwebui_chat_id.get
    )
wrapped_handler = hades._hades_wrap_openwebui_chat_id_context(fake_handler)
async def probe_chat_id(chat_id):
    return await wrapped_handler(
        object(), SimpleNamespace(headers={"X-Hades-OpenWebUI-Chat-Id": chat_id})
    )
async def probe_concurrent_chat_ids():
    return await asyncio.gather(
        probe_chat_id("synthetic-chat-left"),
        probe_chat_id("synthetic-chat-right"),
    )
probe_ids = asyncio.run(probe_concurrent_chat_ids())
assert probe_ids == [
    "synthetic-chat-left", "synthetic-chat-right"
], probe_ids

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
from gateway.platforms import api_server
assert hades._hades_install_openwebui_chat_id_context()
assert getattr(
    api_server.APIServerAdapter._handle_chat_completions,
    "_hades_chat_id_context",
    False,
)
assert owner._hades_session_scope == "owner", owner._hades_session_scope
assert owner._hades_conversation_id == "synthetic-owner-coding-conversation", owner._hades_conversation_id
assert owner._hades_ui_conversation_id == "", owner._hades_ui_conversation_id
assert __import__("os").environ["HADES_CODING_WORKER_CONVERSATION_ID"] != owner._hades_conversation_id
# The request-bound ContextVar is the trusted value populated by the Hermes
# API route from the configured Open WebUI CHAT_ID header.
chat_token = hades._hades_openwebui_chat_id.set("synthetic-openwebui-chat-id")
bound_owner = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner",
    session_id="api-session-fingerprint",
    stream_delta_callback=lambda _chunk: None,
    **base,
)
hades._hades_openwebui_chat_id.reset(chat_token)
assert bound_owner._hades_ui_conversation_id == "synthetic-openwebui-chat-id"
result = owner.run_conversation(
    "Show the diff in this repository.",
    conversation_history=[],
)
assert result["final_response"] != "synthetic verified coding result"
result = bound_owner.run_conversation(
    "Show the diff in this repository.",
    conversation_history=[],
)
assert result["completed"] is True and result["final_response"] == "synthetic verified coding result", (result, bound_owner._hades_session_scope, bound_owner._hades_ui_conversation_id, calls, native_calls)
assert len(calls) == 1, calls
assert calls[0]["subject"] == "synthetic-owner"
assert calls[0]["scope"] == "owner"
assert calls[0]["conversation_id"] == "synthetic-openwebui-chat-id"
assert calls[0]["repo_root"] == project_root

# Even with the feature flag enabled, a different conversation stays on the
# ordinary Hermes path; the disposable fixture cannot capture unrelated work.
other = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner",
    session_id="synthetic-owner-coding-conversation",
    stream_delta_callback=lambda _chunk: None,
    **base,
)
other_result = other.run_conversation(
    "Show the diff in this repository.",
    conversation_history=[],
)
assert len(calls) == 1, calls
assert other_result["final_response"] != "synthetic verified coding result"

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
assert household_result["final_response"] != "synthetic verified coding result"

# ContextVar identity remains isolated when separate conversations initialize
# agents concurrently; neither task can inherit the other's UI chat ID.
async def build_bound_chat(chat_id):
    token = hades._hades_openwebui_chat_id.set(chat_id)
    try:
        await asyncio.sleep(0)
        agent = run_agent.AIAgent(
            gateway_session_key="hades-user-synthetic-owner",
            session_id="shared-api-session-fingerprint",
            stream_delta_callback=lambda _chunk: None,
            **base,
        )
        await asyncio.sleep(0)
        return agent._hades_ui_conversation_id
    finally:
        hades._hades_openwebui_chat_id.reset(token)
async def concurrent_bindings():
    return await asyncio.gather(
        build_bound_chat("synthetic-chat-left"),
        build_bound_chat("synthetic-chat-right"),
    )
left, right = asyncio.run(concurrent_bindings())
assert {left, right} == {"synthetic-chat-left", "synthetic-chat-right"}, (left, right)
print("PASS: trusted owner coding request entered worker lane; household did not")
PY
)
