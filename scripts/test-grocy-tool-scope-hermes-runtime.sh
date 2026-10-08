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
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-grocy-tool-scope.XXXXXX")
chmod 700 "$work"
mkdir -m 700 "$work/home" "$work/hermes"
if [[ -n "${HADES_HINDSIGHT_PLUGIN:-}" ]]; then
  [[ -d "$HADES_HINDSIGHT_PLUGIN" ]] || { echo 'FAIL configured Hindsight plugin directory is unavailable' >&2; exit 2; }
  mkdir -m 700 "$work/hermes/plugins"
  ln -s "$(realpath "$HADES_HINDSIGHT_PLUGIN")" "$work/hermes/plugins/hindsight"
fi
trap 'find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true' EXIT
hermes_overlay_dir=${HADES_HERMES_OVERLAY_DIR:-$repo_dir/hermes}
[[ -f "$hermes_overlay_dir/sitecustomize.py" ]] || {
  echo "FAIL Hermes overlay is unavailable: $hermes_overlay_dir/sitecustomize.py" >&2
  exit 2
}

HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$hermes_overlay_dir:$repo_dir:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner \
HADES_EPSILON_STATE_FILE="$work/epsilon.sqlite" \
HADES_TASK_STATE_FILE="$work/tasks.sqlite" \
HADES_GROCY_AUDIT_FILE="$work/grocy-audit.jsonl" \
timeout 60s "$hermes_python" - "$repo_dir" <<'PY'
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.disable(logging.CRITICAL)
import run_agent
import sitecustomize as hades

assert "mcp-grocy-recipe-authoring" in hades._HADES_GROCY_TOOLSETS
assert "grocy-recipe-authoring" in hades._HADES_GROCY_TOOLSETS

names = [
    "mcp_recipe_url_ingest_recipe_url_preview",
    "mcp_recipe_url_ingest_recipe_url_apply",
    "mcp_recipe_url_ingest_recipe_paste_preview",
    "mcp_grocy_recipe_create_by_name_tool",
    "mcp_grocy_recipe_create_tool",
    "mcp_grocy_recipe_update_tool",
    "mcp_grocy_recipe_add_ingredient_tool",
    "mcp_grocy_recipe_remove_ingredient_tool",
    "mcp_grocy_recipe_authoring_recipe_set_servings",
    "mcp_grocy_recipes_list_tool",
    "mcp_grocy_recipe_details_tool",
    "mcp_grocy_recipe_add_to_shopping_tool",
]
from tools.registry import registry as deferred_registry
import model_tools
deferred_registry.register(
    name="synthetic_unrelated_finance_decoy",
    toolset="mcp-finance-readonly",
    schema={"description": "synthetic unrelated decoy", "parameters": {
        "type": "object", "properties": {}, "required": [],
    }},
    handler=lambda **_kwargs: "synthetic decoy result",
)
for name in (
    "mcp__grocy__stock_overview_tool",
    "mcp__grocy__shopping_list_view_tool",
    "mcp__grocy__shopping_list_add_tool",
):
    deferred_registry.register(
        name=name,
        toolset="mcp-grocy",
        schema={"description": "synthetic deferred Grocy schema", "parameters": {
            "type": "object", "properties": {}, "required": [],
        }},
        handler=lambda **_kwargs: "synthetic registry result",
    )
native_deferred = model_tools.get_tool_definitions(
    enabled_toolsets=hades._HADES_GROCY_TOOLSETS, quiet_mode=True,
)
native_raw = model_tools.get_tool_definitions(
    enabled_toolsets=hades._HADES_GROCY_TOOLSETS,
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
native_deferred_names = {
    row["function"]["name"] for row in native_deferred
}
native_raw_names = {row["function"]["name"] for row in native_raw}
assert {"tool_search", "tool_describe", "tool_call"}.issubset(native_deferred_names), native_deferred_names
assert not ({"tool_search", "tool_describe", "tool_call"} & native_raw_names), native_raw_names
assert {
    "mcp__grocy__stock_overview_tool",
    "mcp__grocy__shopping_list_view_tool",
    "mcp__grocy__shopping_list_add_tool",
}.issubset(native_raw_names), native_raw_names
assert "synthetic_unrelated_finance_decoy" not in native_raw_names
from tools import tool_search
from unittest.mock import patch
model_tools._clear_tool_defs_cache()
with patch.object(
    tool_search,
    "load_config",
    return_value=tool_search.ToolSearchConfig.from_raw({"enabled": "off"}),
):
    native_eager = model_tools.get_tool_definitions(
        enabled_toolsets=hades._HADES_GROCY_TOOLSETS, quiet_mode=True,
    )
model_tools._clear_tool_defs_cache()
assert {row["function"]["name"] for row in native_eager} == native_raw_names
native_hades_catalog = hades._hades_grocy_tool_definitions(
    model_tools.get_tool_definitions
)
native_hades_names = {
    row["function"]["name"] for row in native_hades_catalog
}
assert native_hades_names == native_raw_names, (native_hades_names, native_raw_names)
assert len(native_hades_catalog) == len(native_hades_names), native_hades_catalog
print("PASS HADES Grocy catalog uses Hermes raw schemas without redundant search bridge")

# The raw serving-count operation is not a HADES model tool. A historical
# exact-name registry fallback could re-add it even when the current Hermes
# toolset snapshot did not contain it; keep the schema hidden and route changes
# through the HADES preview/confirmation adapter instead.
serving_name = "mcp_grocy_recipe_authoring_recipe_set_servings"
deferred_registry.register(
    name=serving_name,
    toolset="synthetic-serving-companion-only",
    schema={"description": "synthetic raw serving writer", "parameters": {
        "type": "object", "properties": {}, "required": [],
    }},
    handler=lambda **_kwargs: "must never be invoked",
)
without_serving_companion = hades._hades_grocy_tool_definitions(
    lambda **_kwargs: native_raw
)
assert {row["function"]["name"] for row in without_serving_companion} == native_raw_names
assert serving_name not in {row["function"]["name"] for row in without_serving_companion}
print("PASS Grocy schema lookup does not re-add the unsupported raw serving writer")

homelab_read_names = {
    "mcp_homelab_readonly_homelab_summary",
    "mcp_homelab_readonly_homelab_recent_activity",
    "mcp_homelab_readonly_homelab_backup_status",
}
for name in homelab_read_names:
    deferred_registry.register(
        name=name,
        toolset="mcp-homelab-readonly",
        schema={"description": "synthetic homelab schema", "parameters": {
            "type": "object", "properties": {}, "required": [],
        }},
        handler=lambda **_kwargs: "synthetic registry result",
    )
homelab_native_deferred = model_tools.get_tool_definitions(
    enabled_toolsets=hades._HADES_HOMELAB_TOOLSETS, quiet_mode=True,
)
homelab_native_raw = model_tools.get_tool_definitions(
    enabled_toolsets=hades._HADES_HOMELAB_TOOLSETS,
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
homelab_native_names = {
    row["function"]["name"] for row in homelab_native_raw
}
assert {"tool_search", "tool_describe", "tool_call"}.issubset({
    row["function"]["name"] for row in homelab_native_deferred
})
assert homelab_read_names.issubset(homelab_native_names), homelab_native_names
assert "synthetic_unrelated_finance_decoy" not in homelab_native_names
assert not ({"tool_search", "tool_describe", "tool_call"} & homelab_native_names)
homelab_hades_catalog = hades._hades_homelab_tool_definitions(
    model_tools.get_tool_definitions
)
assert {
    row["function"]["name"] for row in homelab_hades_catalog
} == homelab_native_names
assert hades._hades_filter_tools_for_scope(
    homelab_hades_catalog, "household"
) == []
print("PASS HADES read-only homelab catalog uses Hermes raw schemas without redundant search bridge")

# A cold/failed homelab lookup may retry discovery, but must only start the
# server whose catalog is being requested. Hermes' unfiltered discovery starts
# every configured MCP server and can add unrelated cold-start latency.
from tools import mcp_tool_discovery
read_discovery_calls = []
read_results = iter(([], homelab_native_raw))
hades._HADES_HOMELAB_DISCOVERY_ATTEMPTED = False
with patch.object(
    mcp_tool_discovery, "discover_mcp_tools",
    side_effect=lambda allowed=None: read_discovery_calls.append(allowed),
):
    read_retry_catalog = hades._hades_homelab_tool_definitions(
        lambda **_kwargs: next(read_results)
    )
assert read_discovery_calls == [["homelab-readonly"]], read_discovery_calls
assert {row["function"]["name"] for row in read_retry_catalog} == homelab_native_names
print("PASS read-only homelab retry scopes Hermes MCP discovery to its server")

control_names = {
    "mcp__homelab_control__homelab_control_templates",
    "mcp__homelab_control__homelab_provision_guest",
}
for name in control_names:
    deferred_registry.register(
        name=name,
        toolset="mcp-homelab-control",
        schema={"description": "synthetic homelab control schema", "parameters": {
            "type": "object", "properties": {}, "required": [],
        }},
        handler=lambda **_kwargs: "synthetic registry result",
    )
control_native_raw = model_tools.get_tool_definitions(
    enabled_toolsets=hades._HADES_HOMELAB_CONTROL_TOOLSETS,
    quiet_mode=True,
    skip_tool_search_assembly=True,
)
control_native_names = {
    row["function"]["name"] for row in control_native_raw
}
control_hades_catalog = hades._hades_homelab_control_tool_definitions(
    model_tools.get_tool_definitions
)
assert {
    row["function"]["name"] for row in control_hades_catalog
} == control_native_names == control_names
assert "synthetic_unrelated_finance_decoy" not in control_native_names
assert hades._hades_filter_tools_for_scope(control_hades_catalog, "household") == []
print("PASS owner homelab control catalog uses Hermes raw schemas with exact-name bounds")

control_discovery_calls = []
control_results = iter(([], control_native_raw))
with patch.object(
    mcp_tool_discovery, "discover_mcp_tools",
    side_effect=lambda allowed=None: control_discovery_calls.append(allowed),
):
    control_retry_catalog = hades._hades_homelab_control_tool_definitions(
        lambda **_kwargs: next(control_results)
    )
assert control_discovery_calls == [["homelab-control"]], control_discovery_calls
assert {row["function"]["name"] for row in control_retry_catalog} == control_native_names
print("PASS homelab control retry scopes Hermes MCP discovery to its server")

catalog = [
    {"type": "function", "function": {
        "name": name, "description": "synthetic scope fixture",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }}
    for name in names
]
hades._hades_grocy_tool_definitions = lambda _getter: catalog
class ServingAdapter:
    calls = []
    outcome = "SUCCEEDED"
    async def preview_servings(self, recipe, servings):
        self.calls.append(("preview", recipe, servings))
        return {"outcome": "PREVIEW", "recipe_id": 7, "recipe": "Synthetic Pancakes",
                "current_servings": 4, "requested_servings": servings}
    async def apply_servings_preview(self, recipe_id, expected_current, servings):
        self.calls.append(("apply", recipe_id, expected_current, servings))
        if self.outcome == "STALE PREVIEW":
            return {"outcome": self.outcome, "current_servings": 5}
        if self.outcome == "OUTCOME UNKNOWN":
            return {"outcome": self.outcome}
        return {"outcome": "SUCCEEDED", "recipe_id": recipe_id, "base_servings": servings}

hades._HADES_RECIPE_SERVINGS_ADAPTER = ServingAdapter()
observed = []

class Model(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        observed.append([row["function"]["name"] for row in request.get("tools", [])])
        now = int(time.time())
        ident = "synthetic-scope-check"
        chunks = [
            {"id": ident, "object": "chat.completion.chunk", "created": now,
             "model": "synthetic-no-call", "choices": [{"index": 0,
             "delta": {"role": "assistant", "content": "No canonical change was made."},
             "finish_reason": None}]},
            {"id": ident, "object": "chat.completion.chunk", "created": now,
             "model": "synthetic-no-call", "choices": [{"index": 0,
             "delta": {}, "finish_reason": "stop"}]},
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(("data: " + json.dumps(chunk) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

server = ThreadingHTTPServer(("127.0.0.1", 0), Model)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
kwargs = {
    "base_url": f"http://127.0.0.1:{server.server_port}/v1",
    "api_key": "synthetic-only", "provider": "custom",
    "api_mode": "chat_completions", "model": "synthetic-no-call",
    "enabled_toolsets": (
        hades._HADES_GROCY_TOOLSETS
        + hades._HADES_HOMELAB_TOOLSETS
        + hades._HADES_HOMELAB_CONTROL_TOOLSETS
    ),
    "disabled_toolsets": [], "quiet_mode": True,
    "skip_context_files": True, "skip_memory": True,
    "skip_background_review": True, "load_soul_identity": False,
}

def run(subject):
    agent = run_agent.AIAgent(
        gateway_session_key=f"hades-user-{subject}",
        session_id=f"synthetic-recipe-scope-{subject}",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    assert agent._hades_subject == subject
    result = agent.run_conversation(
        "Please preview this recipe from https://recipes.example.test/synthetic.",
        conversation_history=[],
    )
    assert result.get("completed") is True, result
    assert result.get("final_response") == "No canonical change was made.", result
    return observed[-1]

def chat_turn(subject, chat, text):
    agent = run_agent.AIAgent(
        gateway_session_key=f"hades-user-{subject}",
        session_id=chat,
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    return agent.run_conversation(text, conversation_history=[])

household_tools = run("synthetic-household")
owner_tools = run("synthetic-owner")

owner_only = {
    name for name in names
    if any(marker in name for marker in (
        "recipe_url_ingest", "recipe-url-ingest", "grocy_recipe_authoring",
        "recipe_create_tool", "recipe_create_by_name_tool", "recipe_update_tool",
        "recipe_add_ingredient_tool", "recipe_remove_ingredient_tool",
        "recipe_set_servings",
    ))
}
household_expected = set(names) - owner_only
owner_expected = set(names) - {"mcp_grocy_recipe_authoring_recipe_set_servings"}
assert set(owner_tools) == owner_expected, owner_tools
assert set(household_tools) == household_expected, household_tools
assert not (set(household_tools) & owner_only), household_tools
assert "mcp_grocy_recipes_list_tool" in household_tools
assert "mcp_grocy_recipe_details_tool" in household_tools
assert "mcp_grocy_recipe_add_to_shopping_tool" in household_tools
assert "mcp_grocy_recipe_authoring_recipe_set_servings" not in owner_tools
print("PASS authenticated Hermes owner retains recipe tools; household receives only recipe reads and shared-list actions")

# Bypass only the earlier direct-read shortcut so this focused fixture can
# observe the authenticated API route's model-visible tool schemas.
original_direct_homelab_read = hades._hades_direct_homelab_read
hades._hades_direct_homelab_read = lambda *_args, **_kwargs: ""
homelab_status = chat_turn(
    "synthetic-owner", "homelab-read-schema-chat", "Is the homelab online?",
)
assert homelab_status.get("completed") is True, homelab_status
assert set(observed[-1]) == {"mcp_homelab_readonly_homelab_summary"}, observed[-1]
homelab_control = chat_turn(
    "synthetic-owner", "homelab-control-schema-chat",
    "Create a VM on the Proxmox homelab.",
)
assert homelab_control.get("completed") is True, homelab_control
assert set(observed[-1]) == control_names, observed[-1]
assert "synthetic_unrelated_finance_decoy" not in observed[-1]
hades._hades_direct_homelab_read = original_direct_homelab_read
print("PASS API homelab read/control turns expose only their exact raw-schema catalogs")

# Exercise the real deferred bridge catalog and raw tool_call boundary, which
# must preserve the same owner/household scope as eager model schemas.
import model_tools
from tools import tool_search
from tools.registry import registry
from types import SimpleNamespace
import agent.tool_executor as agent_tool_executor

def scoped_agent(subject):
    return run_agent.AIAgent(
        gateway_session_key=f"hades-user-{subject}",
        session_id=f"synthetic-deferred-recipe-scope-{subject}",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )

household_agent = scoped_agent("synthetic-household")
owner_agent = scoped_agent("synthetic-owner")
# Simulate an accidentally over-broad model catalog: the pre-dispatch policy
# must enforce actor scope even if an owner-only schema slips through.
household_agent.valid_tool_names = set(names)
owner_agent.valid_tool_names = set(names)

synthetic_dispatches = []
def synthetic_handler(args, **_kwargs):
    synthetic_dispatches.append(dict(args))
    return "synthetic dispatch recorded"

for name, toolset in (
    ("mcp_grocy_recipe_create_tool", "mcp-grocy"),
    ("mcp_grocy_recipe_authoring_recipe_set_servings", "mcp-grocy-recipe-authoring"),
    ("mcp_recipe_url_ingest_recipe_url_apply", "recipe-url-ingest"),
):
    registry.register(
        name=name,
        toolset=toolset,
        schema={"description": "synthetic owner-scope fixture", "parameters": {
            "type": "object", "properties": {}, "required": [],
        }},
        handler=synthetic_handler,
    )

def parse_direct(agent, name):
    return agent_tool_executor._parse_tool_call(
        agent,
        SimpleNamespace(function=SimpleNamespace(name=name, arguments="{}")),
    )

for agent, forbidden in (
    (household_agent, "mcp_grocy_recipe_create_tool"),
    (household_agent, "mcp_recipe_url_ingest_recipe_url_apply"),
    (owner_agent, "mcp_grocy_recipe_authoring_recipe_set_servings"),
):
    parsed = parse_direct(agent, forbidden)
    assert parsed.scope_block and "not available in this HADES session" in parsed.scope_block, parsed
    managed = agent_tool_executor._run_agent_tool_execution_middleware(
        agent,
        function_name=parsed.name,
        function_args=parsed.args,
        effective_task_id="synthetic-direct-scope",
        tool_call_id=f"direct-{forbidden}",
        execute=synthetic_handler,
        scope_block=parsed.scope_block,
    )
    assert managed.blocked, managed
    assert not synthetic_dispatches, synthetic_dispatches
print("PASS direct forged owner-only tool calls are blocked before registered handler dispatch")
assert parse_direct(household_agent, "mcp_grocy_recipes_list_tool").scope_block is None
assert parse_direct(owner_agent, "mcp_grocy_recipe_create_tool").scope_block is None
invalid_identity = SimpleNamespace(
    _hades_gateway_session_key="hades-user-",
    _hades_subject="",
    _hades_session_scope="",
    valid_tool_names=set(names),
)
invalid = parse_direct(invalid_identity, "mcp_grocy_recipes_list_tool")
assert invalid.scope_block and "not available in this HADES session" in invalid.scope_block, invalid
non_hades_agent = SimpleNamespace(valid_tool_names=set(names))
assert parse_direct(non_hades_agent, "mcp_grocy_recipe_create_tool").scope_block is None
print("PASS invalid HADES identity fails closed and non-HADES agent remains unaffected")
print("PASS direct in-scope recipe tools remain available")

for agent, must_omit in (
    (household_agent, "mcp_grocy_recipe_create_tool"),
    (owner_agent, None),
):
    result, reroute = model_tools._dispatch_bridge_tool(
        tool_search.TOOL_SEARCH_NAME,
        {"queries": ["recipe_create_tool"], "limit": 20},
        agent.enabled_toolsets, agent.disabled_toolsets,
    )
    assert reroute is None, reroute
    rendered = str(result)
    if must_omit:
        assert must_omit not in rendered, rendered
    else:
        assert "recipe_create_tool" in rendered, rendered
    assert "synthetic_unrelated_finance_decoy" not in rendered, rendered
household_result, household_reroute = model_tools._dispatch_bridge_tool(
    tool_search.TOOL_CALL_NAME,
    {"name": "mcp_grocy_recipe_create_tool", "arguments": {
        "name": "Unauthorized Synthetic Recipe", "description": "", "ingredients": "[]",
    }},
    household_agent.enabled_toolsets, household_agent.disabled_toolsets,
)
assert household_reroute is None, household_reroute
denial = str(household_result).lower()
assert "not available in this session" in denial or "not a deferrable tool" in denial, household_result
print("PASS deferred recipe discovery and raw tool_call keep generic creation owner-only")

ServingAdapter.calls.clear()
preview = chat_turn("synthetic-owner", "servings-confirm-chat", "Change the servings for Synthetic Pancakes to six.")
assert preview.get("completed") and preview.get("api_calls") == 0, preview
assert "currently serves 4" in preview.get("final_response", "") and "Reply yes to confirm or no to cancel" in preview.get("final_response", ""), preview
assert ServingAdapter.calls == [("preview", "Synthetic Pancakes", 6)], ServingAdapter.calls
from integrations.automation import LifecycleStore
pending_store = LifecycleStore(hades._hades_health_watch_state_path())
pending_rows = pending_store.pending_for_actor("synthetic-owner")
assert any(row["payload"].get("kind") == "recipe-serving-change" for row in pending_rows), pending_rows
expected_pending_key = "session:synthetic-owner:" + hades._hades_turn_identity("yes", [], "servings-confirm-chat")
assert any(row["pending_key"] == expected_pending_key for row in pending_rows), (expected_pending_key, pending_rows)
cross_chat = chat_turn("synthetic-owner", "servings-other-chat", "Yes, do it.")
assert "couldn't match that confirmation to this chat" in cross_chat.get("final_response", ""), cross_chat
assert [call[0] for call in ServingAdapter.calls] == ["preview"], ServingAdapter.calls
confirmed = chat_turn("synthetic-owner", "servings-confirm-chat", "Yes, do it.")
assert confirmed.get("completed") and confirmed.get("api_calls") == 0, confirmed
assert "Updated Synthetic Pancakes to serve 6" in confirmed.get("final_response", ""), confirmed
assert ServingAdapter.calls[-1] == ("apply", 7, 4, 6), ServingAdapter.calls

ServingAdapter.calls.clear()
cancel_preview = chat_turn("synthetic-owner", "servings-cancel-chat", "Set Synthetic Pancakes to 7 servings.")
assert "Reply yes to confirm or no to cancel" in cancel_preview.get("final_response", ""), cancel_preview
cancelled = chat_turn("synthetic-owner", "servings-cancel-chat", "No thanks.")
assert "left the saved recipe unchanged" in cancelled.get("final_response", ""), cancelled
assert [call[0] for call in ServingAdapter.calls] == ["preview"], ServingAdapter.calls

ServingAdapter.calls.clear()
stale_preview = chat_turn("synthetic-owner", "servings-stale-chat", "Make Synthetic Pancakes serve 8.")
assert "Reply yes to confirm or no to cancel" in stale_preview.get("final_response", ""), stale_preview
ServingAdapter.outcome = "STALE PREVIEW"
stale = chat_turn("synthetic-owner", "servings-stale-chat", "Confirm")
assert "changed after the preview" in stale.get("final_response", ""), stale
assert [call[0] for call in ServingAdapter.calls] == ["preview", "apply"], ServingAdapter.calls
ServingAdapter.outcome = "SUCCEEDED"

ServingAdapter.calls.clear()
unknown_preview = chat_turn("synthetic-owner", "servings-unknown-chat", "Set Synthetic Pancakes to 9 servings.")
assert "Reply yes to confirm or no to cancel" in unknown_preview.get("final_response", ""), unknown_preview
ServingAdapter.outcome = "OUTCOME UNKNOWN"
unknown = chat_turn("synthetic-owner", "servings-unknown-chat", "Go ahead.")
assert "result is uncertain" in unknown.get("final_response", ""), unknown
assert [call[0] for call in ServingAdapter.calls] == ["preview", "apply"], ServingAdapter.calls
ServingAdapter.outcome = "SUCCEEDED"

ServingAdapter.calls.clear()
household_denied = chat_turn("synthetic-household", "servings-household-chat", "Change the servings for Synthetic Pancakes to 6.")
assert "Only the owner can change" in household_denied.get("final_response", ""), household_denied
assert not ServingAdapter.calls, ServingAdapter.calls
print("PASS owner serving change previews before confirmation, cancels without write, rejects stale preview, and denies household mutation")
server.shutdown()
server.server_close()
PY
