#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

hermes_bin=$(readlink -f "$(command -v hermes || true)")
[[ -n "$hermes_bin" ]] || { echo 'FAIL Hermes executable is unavailable' >&2; exit 2; }
hermes_python=${HADES_HERMES_PYTHON:-$(dirname "$hermes_bin")/python3.11}
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python 3.11 is unavailable' >&2; exit 2; }
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
hermes_overlay_dir=${HADES_HERMES_OVERLAY_DIR:-$PWD/hermes}
[[ -f "$hermes_overlay_dir/sitecustomize.py" ]] || {
  echo "FAIL Hermes overlay is unavailable: $hermes_overlay_dir/sitecustomize.py" >&2
  exit 2
}
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-minecraft-continuation.XXXXXX")
chmod 700 "$work"
trap 'find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true' EXIT
mkdir -m 700 "$work/home" "$work/hermes"

HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$hermes_overlay_dir:$PWD:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner \
HADES_PROXMOX_CONTROL_NODES=SyntheticNode \
HADES_PROXMOX_TEMPLATE_MAP=minecraft:9001 \
HADES_EPSILON_STATE_FILE="$work/lifecycle.sqlite" \
HADES_SELF_SERVICE_REGISTRY_FILE="$work/workloads.json" \
HERMES_ACCEPT_HOOKS=1 \
"$hermes_python" - "$PWD" <<'PY'
import os
import sys
from pathlib import Path

repo = Path(sys.argv[1])
import run_agent
import sitecustomize as hades

assert getattr(run_agent.AIAgent.run_conversation, "__name__", "") == "_hades_run_conversation"
catalog_calls = []
catalog_value = {"status": "READY", "templates": ["minecraft"], "approved_nodes": ["SyntheticNode"], "writes_performed": False}
class SyntheticControl:
    provision_result = None
    provision_calls = []

    @staticmethod
    def inspect_templates():
        catalog_calls.append("inspect")
        return catalog_value

    @staticmethod
    def provision_guest(template, target, **kwargs):
        SyntheticControl.provision_calls.append((template, target, kwargs))
        return SyntheticControl.provision_result

hades._hades_load_control_module = lambda: SyntheticControl
common = {
    "base_url": "http://127.0.0.1:9/v1", "api_key": "synthetic-only",
    "provider": "custom", "api_mode": "chat_completions", "model": "synthetic-no-call",
    "enabled_toolsets": [], "disabled_toolsets": [], "quiet_mode": True,
    "skip_context_files": True, "skip_memory": True,
    "skip_background_review": True, "load_soul_identity": False,
}
chat = "synthetic-minecraft-plan-chat"
first_text = "Can you spin up a Minecraft server for me?"
dogfood_first_text = "Can you spin up a Minecraft server for me and lemme know the server port/ip so I can add it to the firewall?"
catalog_value = {"status": "UNCONFIGURED", "templates": [], "approved_nodes": [], "writes_performed": False}
unconfigured = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id="synthetic-minecraft-unconfigured-chat",
    stream_delta_callback=lambda _chunk: None, **common,
)
unconfigured_result = unconfigured.run_conversation(first_text, conversation_history=[])
assert unconfigured_result.get("completed") is True and unconfigured_result.get("api_calls") == 0, unconfigured_result
assert "no approved `minecraft` template and placement are configured" in unconfigured_result["final_response"], unconfigured_result
assert "Nothing was prepared or created" in unconfigured_result["final_response"], unconfigured_result
from integrations.automation import LifecycleStore
unconfigured_key = hades._hades_pending_provision_keys(unconfigured)[0]
assert LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(unconfigured_key, "synthetic-owner") is None
assert catalog_calls == ["inspect"]
catalog_value = {"status": "READY", "templates": ["minecraft"], "approved_nodes": ["SyntheticNode"], "writes_performed": False}
for text, chat_id, expected in (
    ("Can you spin up a server?", "synthetic-generic-server-chat", "What kind of server do you want"),
    ("Can you spin up a Factorio server?", "synthetic-factorio-server-chat", "don't have an approved `factorio` server template"),
    ("Make a Minecraft server and a website", "synthetic-ambiguous-server-chat", "more than one possible server type"),
):
    probe = run_agent.AIAgent(
        gateway_session_key="hades-user-synthetic-owner", session_id=chat_id,
        stream_delta_callback=lambda _chunk: None, **common,
    )
    probe_result = probe.run_conversation(text, conversation_history=[])
    assert probe_result.get("completed") is True and probe_result.get("api_calls") == 0, probe_result
    assert expected in probe_result["final_response"], probe_result
    probe_key = hades._hades_pending_provision_keys(probe)[0]
    assert LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(probe_key, "synthetic-owner") is None

first = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
assert first._hades_subject == "synthetic-owner" and first._hades_session_scope == "owner"
initial = first.run_conversation(first_text, conversation_history=[])
assert initial.get("completed") is True and initial.get("api_calls") == 0, initial
for expected in (
    "Plan only", "`minecraft`", "`gamma-minecraft`", "4 CPU cores", "8 GiB RAM",
    "40 GiB disk", "SyntheticNode", "owner only", "TCP 25565",
    "does not confirm Minecraft is installed or running", "cannot read back the guest IP",
    "No firewall rule will be changed", "reply `Create it`",
):
    assert expected in initial["final_response"], (expected, initial)
assert catalog_calls == ["inspect", "inspect", "inspect"], "preflight and concrete plan use read-only configured template metadata"
pending_key = hades._hades_pending_provision_keys(first)[0]
pending_before_plan = LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(pending_key, "synthetic-owner")
assert pending_before_plan and pending_before_plan["template_id"] == "hades-self-service-provision" and pending_before_plan["previewed"] is True
assert pending_before_plan["operation"] == "provision_guest"
assert pending_before_plan["target"] == {"node": "SyntheticNode"}
assert pending_before_plan["resources"] == {"cores": 4, "memory_mib": 8192, "disk_gib": 40}
# Pending provisioning state is intentionally durable; no worker-local cache is
# used by this route, so a fresh Hermes worker can recover the same chat plan.
assert not hasattr(hades, "_HADES_PENDING_PROVISION")

# Model the next UI request as a fresh Hermes worker on the same Open WebUI chat.
history = [
    {"role": "user", "content": first_text},
    {"role": "assistant", "content": initial["final_response"]},
    {"role": "user", "content": "Perfect, continue"},
]
second = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
continued = second.run_conversation("Perfect, continue", conversation_history=history)
assert continued.get("completed") is True and continued.get("api_calls") == 0, continued
plan = continued["final_response"]
for expected in (
    "Plan only", "`minecraft`", "`gamma-minecraft`", "4 CPU cores", "8 GiB RAM",
    "40 GiB disk", "SyntheticNode", "owner only", "TCP 25565",
    "does not confirm Minecraft is installed or running",
    "cannot read back the guest IP", "No firewall rule will be changed", "reply `Create it`",
):
    assert expected in plan, (expected, plan)
assert catalog_calls == ["inspect", "inspect", "inspect", "inspect"]
pending_after_plan = LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(pending_key, "synthetic-owner")
assert pending_after_plan and pending_after_plan["previewed"] is True
assert "reply `Create it`" in initial["final_response"]

# Confirm through the real Hermes route with a synthetic Proxmox success result.
# VM state is the only simulated success; no guest application probe is implied.
SyntheticControl.provision_result = {
    "status": "SUCCEEDED",
    "target": {"node": "SyntheticNode", "vmid": 9901},
    "observed_status": "running",
    "writes_performed": True,
    "reconciled": True,
}
confirm_history = history + [
    {"role": "assistant", "content": plan},
    {"role": "user", "content": "Create it"},
]
confirm_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
created = confirm_agent.run_conversation("Create it", conversation_history=confirm_history)
assert created.get("completed") is True and created.get("api_calls") == 0, created
for expected in (
    "Created the `minecraft` VM `gamma-minecraft`",
    "Proxmox reports the VM running",
    "haven't confirmed that Minecraft itself is running",
    "can't give you a firewall-ready endpoint",
    "No firewall rule was changed",
):
    assert expected in created["final_response"], (expected, created)
assert len(SyntheticControl.provision_calls) == 1, SyntheticControl.provision_calls
assert SyntheticControl.provision_calls[0] == (
    "minecraft", {"node": "SyntheticNode"},
    {"name": "gamma-minecraft", "owner_confirmed": True,
     "cores": 4, "memory_mib": 8192, "disk_gib": 40},
), SyntheticControl.provision_calls
from integrations.self_service.registry import WorkloadRegistry
registered = WorkloadRegistry(os.environ["HADES_SELF_SERVICE_REGISTRY_FILE"]).list_for("synthetic-owner")
assert len(registered) == 1 and registered[0]["vmid"] == 9901, registered
unknown_message = hades._hades_self_service_result_message(
    "minecraft", "gamma-minecraft",
    {"status": "OUTCOME_UNKNOWN", "writes_performed": True,
     "error": "https://internal.example/api?token=synthetic-secret"},
)
assert "can't confirm whether" in unknown_message and "won't retry" in unknown_message
assert "synthetic-secret" not in unknown_message and "internal.example" not in unknown_message
assert "No firewall rule was changed" in unknown_message
write_failed_message = hades._hades_self_service_result_message(
    "minecraft", "gamma-minecraft",
    {"status": "FAILED", "writes_performed": True,
     "error": "synthetic raw backend failure"},
)
assert "won't retry" in write_failed_message and "synthetic raw backend failure" not in write_failed_message
registry_failed_message = hades._hades_self_service_result_message(
    "minecraft", "gamma-minecraft", SyntheticControl.provision_result,
    ownership_error=RuntimeError("/private/synthetic/path"),
)
assert "ownership record" in registry_failed_message and "/private/synthetic/path" not in registry_failed_message
assert "not Minecraft or its IP" in registry_failed_message
assert "No firewall rule was changed" in registry_failed_message

# The confirmation is bound to the exact placement from the plan. If that node
# is removed from the approved list before confirmation, no write is allowed.
placement_chat = "synthetic-minecraft-placement-chat"
placement_first = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=placement_chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
placement_request = placement_first.run_conversation(first_text, conversation_history=[])
placement_history = [
    {"role": "user", "content": first_text},
    {"role": "assistant", "content": placement_request["final_response"]},
    {"role": "user", "content": "Perfect, continue"},
]
placement_continue = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=placement_chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
placement_plan = placement_continue.run_conversation("Perfect, continue", conversation_history=placement_history)
assert "approved placement: SyntheticNode" in placement_plan["final_response"]
catalog_value["approved_nodes"] = ["ReplacementNode"]
placement_confirm = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=placement_chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
placement_history += [
    {"role": "assistant", "content": placement_plan["final_response"]},
    {"role": "user", "content": "Create it"},
]
placement_result = placement_confirm.run_conversation("Create it", conversation_history=placement_history)
assert "couldn't create the minecraft VM" in placement_result["final_response"], placement_result
assert "No VM or firewall change was made" in placement_result["final_response"], placement_result
assert len(SyntheticControl.provision_calls) == 1, SyntheticControl.provision_calls
catalog_value["approved_nodes"] = ["SyntheticNode"]

# An ambiguous result is surfaced through the same authenticated confirmation
# route, consumes its confirmation once, and never registers a guessed guest.
retry_initial_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
retry_initial = retry_initial_agent.run_conversation(first_text, conversation_history=[])
retry_continue_history = [
    {"role": "user", "content": first_text},
    {"role": "assistant", "content": retry_initial["final_response"]},
    {"role": "user", "content": "Perfect, continue"},
]
retry_continue_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
retry_plan = retry_continue_agent.run_conversation("Perfect, continue", conversation_history=retry_continue_history)
retry_history = retry_continue_history + [
    {"role": "assistant", "content": retry_plan["final_response"]},
    {"role": "user", "content": "Create it"},
]
SyntheticControl.provision_result = {
    "status": "OUTCOME_UNKNOWN", "writes_performed": True,
    "target": {"node": "SyntheticNode", "vmid": 9902},
    "error": "https://internal.example/api?token=synthetic-secret",
}
unknown_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
unknown_result = unknown_agent.run_conversation("Create it", conversation_history=retry_history)
unknown_response = unknown_result["final_response"]
assert "can't confirm whether" in unknown_response and "won't retry" in unknown_response, unknown_result
assert "synthetic-secret" not in unknown_response and "internal.example" not in unknown_response
assert "No firewall rule was changed" in unknown_response
assert len(SyntheticControl.provision_calls) == 2, SyntheticControl.provision_calls
registered_after_unknown = WorkloadRegistry(os.environ["HADES_SELF_SERVICE_REGISTRY_FILE"]).list_for("synthetic-owner")
assert len(registered_after_unknown) == 1 and registered_after_unknown[0]["vmid"] == 9901, registered_after_unknown
assert LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(pending_key, "synthetic-owner") is None

# If the shared lifecycle state is missing, the exact recorded owner request
# and no-write offer should recover a fresh plan after rechecking the catalog.
LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_take(pending_key, "synthetic-owner")
lost_context_worker = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
dogfood_history = [
    {"role": "user", "content": dogfood_first_text},
    {"role": "assistant", "content": (
        "I can provision an approved household server, but I have not created anything yet. "
        "I will first show the approved template, bounded resources, placement, and sharing plan, "
        "then ask for confirmation before making a change."
    )},
    {"role": "user", "content": "Perfect, continue"},
]
lost_context = lost_context_worker.run_conversation("Perfect, continue", conversation_history=dogfood_history)
assert lost_context.get("completed") is True and lost_context.get("api_calls") == 0, lost_context
for expected in ("Plan only", "Minecraft Java normally uses TCP 25565", "cannot give you a firewall-ready endpoint", "No firewall rule will be changed"):
    assert expected in lost_context["final_response"], (expected, lost_context)
recovered_pending = LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(pending_key, "synthetic-owner")
assert recovered_pending and recovered_pending["previewed"] is True, recovered_pending
LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_take(pending_key, "synthetic-owner")
context_free_worker = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
context_free = context_free_worker.run_conversation("Perfect, continue")
assert context_free.get("completed") is True and context_free.get("api_calls") == 0, context_free
assert "don't have enough context in this chat" in context_free["final_response"], context_free
assert "Nothing was created" in context_free["final_response"], context_free
assert LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(pending_key, "synthetic-owner") is None
recovery_offer = dogfood_history[1]["content"]
for text, chat_id, expected in (
    ("Can you spin up a Factorio server?", "synthetic-recovery-factorio", "don't have an approved `factorio`"),
    ("Make a Minecraft server and a website", "synthetic-recovery-mixed", "couldn't safely recover one server type"),
):
    recovery_history = [
        {"role": "user", "content": text},
        {"role": "assistant", "content": recovery_offer},
        {"role": "user", "content": "Perfect, continue"},
    ]
    recovery_agent = run_agent.AIAgent(
        gateway_session_key="hades-user-synthetic-owner", session_id=chat_id,
        stream_delta_callback=lambda _chunk: None, **common,
    )
    answer = recovery_agent.run_conversation("Perfect, continue", conversation_history=recovery_history)
    assert expected in answer["final_response"], answer
    recovery_key = hades._hades_pending_provision_keys(recovery_agent)[0]
    assert LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(recovery_key, "synthetic-owner") is None
catalog_value = {"status": "UNCONFIGURED", "templates": [], "approved_nodes": [], "writes_performed": False}
unconfigured_chat = "synthetic-recovery-unconfigured"
unconfigured_history = [
    {"role": "user", "content": first_text},
    {"role": "assistant", "content": recovery_offer},
    {"role": "user", "content": "Perfect, continue"},
]
unconfigured_recovery = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id=unconfigured_chat,
    stream_delta_callback=lambda _chunk: None, **common,
)
unconfigured_answer = unconfigured_recovery.run_conversation("Perfect, continue", conversation_history=unconfigured_history)
assert "no approved `minecraft` template and placement are currently configured" in unconfigured_answer["final_response"], unconfigured_answer
unconfigured_recovery_key = hades._hades_pending_provision_keys(unconfigured_recovery)[0]
assert LifecycleStore(os.environ["HADES_EPSILON_STATE_FILE"]).pending_get(unconfigured_recovery_key, "synthetic-owner") is None

# A stale server question from an earlier turn must not override the current
# explicit memory request. The real guest exposed this when the managed-server
# route ran before Hindsight and returned its adapter error for a memory turn.
memory_route_calls = []
original_memory_route = hades._hades_direct_memory_response
def synthetic_memory_route(text, subject, scope):
    memory_route_calls.append((text, subject, scope))
    return "Synthetic Alpha memory turn handled."
hades._hades_direct_memory_response = synthetic_memory_route
stale_server_history = [
    {"role": "user", "content": "Show me my Minecraft server status."},
    {"role": "assistant", "content": "I could not read the server status."},
]
memory_text = "Remember that my harmless Alpha test fruit is synthetic mango."
stale_intent_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id="synthetic-stale-server-history",
    stream_delta_callback=lambda _chunk: None, **common,
)
stale_intent_result = stale_intent_agent.run_conversation(
    memory_text, conversation_history=stale_server_history,
)
assert stale_intent_result.get("final_response") == "Synthetic Alpha memory turn handled.", stale_intent_result
assert stale_intent_result.get("api_calls") == 0, stale_intent_result
assert memory_route_calls == [(memory_text, "synthetic-owner", "owner")], memory_route_calls
memory_route_calls.clear()
marker_collision_text = "Remember that my harmless Alpha test fruit is guest-c-alpha-marker."
marker_collision_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner", session_id="synthetic-memory-guest-word",
    stream_delta_callback=lambda _chunk: None, **common,
)
marker_collision_result = marker_collision_agent.run_conversation(
    marker_collision_text, conversation_history=[],
)
assert marker_collision_result.get("final_response") == "Synthetic Alpha memory turn handled.", marker_collision_result
assert marker_collision_result.get("api_calls") == 0, marker_collision_result
assert memory_route_calls == [(marker_collision_text, "synthetic-owner", "owner")], memory_route_calls
hades._hades_direct_memory_response = original_memory_route
print("PASS actual Hermes first-turn Minecraft request returns the exact no-write plan")
print("PASS cross-worker acknowledgement repeats the plan without creating the VM")
print("PASS owner confirmation reports VM readiness without claiming Minecraft or firewall readiness")
print("PASS unknown and partial provision outcomes are non-retriable and hide backend details")
print("PASS provisioning confirmation preserves the previewed placement and resource plan")
print("PASS missing Minecraft template configuration fails before pending state or infrastructure writes")
print("PASS missing pending state recovers the exact transcript request into a freshly validated no-write plan")
print("PASS context-free continuation is an explicit no-write clarification, not a model fallback")
print("PASS lost-state recovery refuses unsupported, mixed, and unconfigured plans without pending state")
print("PASS generic, unsupported, and mixed-workload requests never silently select a different VM")
print("PASS current explicit memory intent outranks stale server history from a previous turn")
print("PASS explicit memory facts containing the word guest cannot enter managed-server routing")
print("PASS only read-only synthetic template metadata was inspected; model and infrastructure writes were not invoked")
PY
