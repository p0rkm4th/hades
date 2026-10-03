#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(command -v hermes || true)
  if [[ -n "$hermes_bin" ]]; then
    hermes_bin=$(readlink -f "$hermes_bin")
    candidate="$(dirname "$hermes_bin")/python3.11"
    [[ -x "$candidate" ]] && hermes_python=$candidate
  fi
fi
if [[ -z "$hermes_python" || ! -x "$hermes_python" ]]; then
  echo 'FAIL Hermes Python 3.11 was not found; set HADES_HERMES_PYTHON to the Hermes venv interpreter' >&2
  exit 2
fi

python3 - "$PWD" "$hermes_python" <<'PY'
import os
import subprocess
import sys
import tempfile
import json
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
interpreter = Path(sys.argv[2]).absolute()
overlay_setting = os.environ.get("HADES_HERMES_OVERLAY_DIR", "").strip()
if os.environ.get("HADES_COMPOSED_HOMELAB_ONLY") == "1" and not overlay_setting:
    raise SystemExit("FAIL composed homelab runtime mode requires HADES_HERMES_OVERLAY_DIR pointing to the composed candidate")
overlay_dir = Path(overlay_setting or str(repo / "hermes")).resolve()
if not (overlay_dir / "sitecustomize.py").is_file():
    raise SystemExit(f"FAIL HADES overlay directory has no sitecustomize.py: {overlay_dir}")
child = r'''import os
import json
import importlib.util
import tempfile
from pathlib import Path
import run_agent
import sitecustomize as hades
import threading
import tools.registry as hermes_registry_module

class SyntheticHomelabRegistry:
    """Exercise the registered-MCP boundary without external sources."""
    _tools = {
        "homelab_summary",
        "homelab_owner_snapshot",
        "homelab_backup_status",
        "homelab_compute_capabilities",
        "homelab_inference_inventory",
    }

    def __init__(self):
        self.calls = []

    def get_entry(self, name):
        canonical = "mcp__homelab_readonly__"
        legacy = "mcp_homelab_readonly_"
        if name.startswith(canonical):
            tool = name[len(canonical):]
        elif name.startswith(legacy):
            tool = name[len(legacy):]
        else:
            return None
        return object() if tool in self._tools else None

    def dispatch(self, name, arguments):
        assert arguments == {}
        if name.startswith("mcp__homelab_readonly__"):
            tool = name.removeprefix("mcp__homelab_readonly__")
        else:
            tool = name.removeprefix("mcp_homelab_readonly_")
        self.calls.append(tool)
        adapter = os.path.join(
            os.environ["HADES_HERMES_WORKING_DIRECTORY"],
            "integrations", "homelab-readonly", "server.py",
        )
        spec = importlib.util.spec_from_file_location("synthetic_homelab_mcp", adapter)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            result = getattr(module, tool)()
        except Exception as exc:
            return json.dumps({"error": type(exc).__name__})
        return json.dumps({"result": json.dumps(result)})

hermes_registry_module.registry = SyntheticHomelabRegistry()
assert hades._HADES_HOMELAB_INTENT.search("What models are available?")
assert hades._HADES_HOMELAB_INTENT.search("Which inference models are available right now?")
assert hades._HADES_HOMELAB_INTENT.search("Where's qwen3.6:35b?")
assert hades._HADES_HOMELAB_INTENT.search("Which GPUs are free?")
assert hades._HADES_HOMELAB_INTENT.search("Where should I run another model?")
assert hades._HADES_HOMELAB_INTENT.search("Check Synthetic Node B.")
assert hades._hades_homelab_target_from_question("Check Synthetic Node B.") == "synthetic node b"
assert hades._hades_homelab_named_check_target("Check my shopping list") is None
assert not hades._hades_positive_homelab_control_request(
    "Check the homelab and do not change anything."
)
assert hades._hades_positive_homelab_control_request("Restart the synthetic server.")
assert hades._hades_service_placement_intent(
    "Where is the Minecraft server running?", "owner"
)
if os.environ.get("HADES_COMPOSED_HOMELAB_ONLY") != "1":
    assert not hades._hades_managed_server_status_intent(
        "Where is the Minecraft server running?", "owner"
    )
    assert not hades._hades_managed_server_status_intent(
        "Where is the Minecraft server running?", "household"
    )
    assert hades._hades_managed_server_status_intent("Show my managed server status", "owner")
household_model_denial = hades._hades_direct_homelab_read(
    "What models are available?", scope="household",
)
assert "available only in an owner session" in household_model_denial
household_ai_availability = hades._hades_direct_homelab_read(
    "Can we use the AI thing right now?", "synthetic-beta", "household",
)
assert "AI service checks are responding" in household_ai_availability, household_ai_availability
assert "haven't confirmed a prompt will work" in household_ai_availability, household_ai_availability
assert "Synthetic Inference Node A" not in household_ai_availability and "qwen" not in household_ai_availability, household_ai_availability
household_gpu_denial = hades._hades_direct_homelab_read(
    "Which GPUs are free?", scope="household",
)
assert "available only in an owner session" in household_gpu_denial
household_computer_denial = hades._hades_direct_homelab_read(
    "Are all the computers okay?", scope="household",
)
assert "can't verify private infrastructure or computer status" in household_computer_denial, household_computer_denial
household_named_node_denial = hades._hades_direct_homelab_read(
    "Check Synthetic Node B.", "synthetic-beta", "household",
)
assert "private infrastructure" in household_named_node_denial, household_named_node_denial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from integrations.task import TaskStatus, TaskStore

store = TaskStore(os.environ["HADES_TASK_STATE_FILE"])
owner, beta = "synthetic-owner", "synthetic-beta"
store.create(task_id="task-owner-approval01", actor_subject_id=owner, goal="Prepare Friday dinner", status=TaskStatus.AWAITING_APPROVAL)
store.create(task_id="task-beta-failed0001", actor_subject_id=beta, goal="Review Beta's private plan", status=TaskStatus.FAILED)
agent_class = run_agent.AIAgent
assert getattr(agent_class.run_conversation, "__name__", "") == "_hades_run_conversation", "HADES hook did not patch the Hermes agent runtime"
def fixture_source(label):
    def respond(text="", *_args, **_kwargs):
        if label == "expiry" and not __import__("re").search(
            r"\b(?:expir|going bad|best.before)\w*\b", str(text), __import__("re").IGNORECASE
        ):
            return None
        return f"synthetic {label} status"
    return respond
actual_homelab_read = hades._hades_direct_homelab_read
actual_backup_read = hades._hades_phase2_backup_response
actual_finance_read = hades._hades_direct_finance_guidance
actual_household_grocy_read = hades._hades_direct_household_grocy_read
actual_grocy_expiry_read = hades._hades_direct_grocy_expiry_read
hades._hades_direct_homelab_read = fixture_source("infrastructure")
hades._hades_phase2_backup_response = fixture_source("backup")
hades._hades_direct_household_grocy_read = fixture_source("household stock")
hades._hades_direct_grocy_expiry_read = fixture_source("expiry")
hades._hades_direct_finance_guidance = fixture_source("finance")
kwargs = {
    "base_url": "http://127.0.0.1:9/v1", "api_key": "synthetic-only",
    "provider": "custom", "api_mode": "chat_completions", "model": "synthetic-no-call",
    "enabled_toolsets": [], "disabled_toolsets": [], "quiet_mode": True,
    "skip_context_files": True, "skip_memory": True,
    "skip_background_review": True, "load_soul_identity": False,
}
if os.environ.get("HADES_COMPOSED_HOMELAB_ONLY") == "1":
    hades._hades_direct_homelab_read = actual_homelab_read
    hades._hades_phase2_backup_response = actual_backup_read
    hades._hades_direct_finance_guidance = actual_finance_read
    hades._hades_direct_household_grocy_read = actual_household_grocy_read
    hades._hades_direct_grocy_expiry_read = actual_grocy_expiry_read
    owner_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}",
        session_id="synthetic-composed-named-node-owner",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    registry = hermes_registry_module.registry
    registry.calls.clear()
    broad_owner_status = owner_agent.run_conversation(
        "Is everything okay with my homelab?", conversation_history=[]
    )
    assert broad_owner_status.get("completed") is True and broad_owner_status.get("api_calls") == 0, broad_owner_status
    assert "Live inference reads:" in broad_owner_status["final_response"], broad_owner_status
    assert "do not prove generation or available GPU capacity" in broad_owner_status["final_response"], broad_owner_status
    assert registry.calls[:2] == ["homelab_summary", "homelab_inference_inventory"], registry.calls

    registry.calls.clear()
    owner_result = owner_agent.run_conversation("Check Synthetic Node B.", conversation_history=[])
    assert owner_result.get("completed") is True and owner_result.get("api_calls") == 0, owner_result
    assert "Observed hardware inventory lists Synthetic Node B." in owner_result["final_response"], owner_result
    assert "can't say whether it's online" in owner_result["final_response"], owner_result
    assert "running normally" not in owner_result["final_response"].casefold(), owner_result
    assert registry.calls[:2] == ["homelab_inference_inventory", "homelab_owner_snapshot"], registry.calls
    assert set(registry.calls) <= {
        "homelab_inference_inventory", "homelab_owner_snapshot",
        "homelab_summary", "homelab_compute_capabilities",
    }, registry.calls

    registry.calls.clear()
    natural_owner_result = owner_agent.run_conversation(
        "What's Synthetic Node B doing right now?", conversation_history=[]
    )
    assert natural_owner_result.get("completed") is True and natural_owner_result.get("api_calls") == 0, natural_owner_result
    assert "Observed hardware inventory lists Synthetic Node B." in natural_owner_result["final_response"], natural_owner_result
    assert "can't say whether it's online" in natural_owner_result["final_response"], natural_owner_result
    assert registry.calls[:2] == ["homelab_inference_inventory", "homelab_owner_snapshot"], registry.calls
    assert set(registry.calls) <= {
        "homelab_inference_inventory", "homelab_owner_snapshot",
        "homelab_summary", "homelab_compute_capabilities",
    }, registry.calls

    registry.calls.clear()
    household_agent = agent_class(
        gateway_session_key=f"hades-user-{beta}",
        session_id="synthetic-composed-named-node-household",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    household_result = household_agent.run_conversation("Check Synthetic Node B.", conversation_history=[])
    assert household_result.get("completed") is True and household_result.get("api_calls") == 0, household_result
    assert "private infrastructure" in household_result["final_response"].casefold(), household_result
    assert "Synthetic Node B" not in household_result["final_response"], household_result
    assert not registry.calls, registry.calls

    registry.calls.clear()
    household_computer_status = household_agent.run_conversation(
        "Are all the computers okay?", conversation_history=[]
    )
    assert household_computer_status.get("completed") is True, household_computer_status
    assert household_computer_status.get("api_calls") == 0, household_computer_status
    assert "can't verify private infrastructure or computer status" in household_computer_status["final_response"].casefold(), household_computer_status
    assert "Synthetic Node B" not in household_computer_status["final_response"], household_computer_status
    assert not registry.calls, registry.calls

    registry.calls.clear()
    household_network_status = household_agent.run_conversation(
        "Why does the network feel slow?", conversation_history=[]
    )
    assert household_network_status.get("completed") is True, household_network_status
    assert household_network_status.get("api_calls") == 0, household_network_status
    assert "can't verify private infrastructure or computer status" in household_network_status["final_response"].casefold(), household_network_status
    assert "Synthetic Node B" not in household_network_status["final_response"], household_network_status
    assert not registry.calls, registry.calls

    registry.calls.clear()
    household_change_status = household_agent.run_conversation(
        "What changed since yesterday?", conversation_history=[]
    )
    assert household_change_status.get("completed") is True, household_change_status
    assert household_change_status.get("api_calls") == 0, household_change_status
    assert "can't verify private infrastructure changes" in household_change_status["final_response"].casefold(), household_change_status
    assert "proxmox" not in household_change_status["final_response"].casefold(), household_change_status
    assert not registry.calls, registry.calls

    registry.calls.clear()
    household_provenance_status = household_agent.run_conversation(
        "How do you know that?",
        conversation_history=[
            {"role": "user", "content": "Is everything okay with the homelab?"},
            {"role": "assistant", "content": "I can't verify private infrastructure or computer status from this account."},
        ],
    )
    assert household_provenance_status.get("completed") is True, household_provenance_status
    assert household_provenance_status.get("api_calls") == 0, household_provenance_status
    assert "can't verify private infrastructure or computer status" in household_provenance_status["final_response"].casefold(), household_provenance_status
    assert "refrigeration" not in household_provenance_status["final_response"].casefold(), household_provenance_status
    assert not registry.calls, registry.calls

    registry.calls.clear()
    owner_network_status = owner_agent.run_conversation(
        "Why does the network feel slow?", conversation_history=[]
    )
    assert owner_network_status.get("completed") is True, owner_network_status
    assert owner_network_status.get("api_calls") == 0, owner_network_status
    assert "cannot identify a network bottleneck or trend from this evidence" in owner_network_status["final_response"], owner_network_status
    assert "homelab_inference_inventory" not in registry.calls, registry.calls

    registry.calls.clear()
    owner_provenance_status = owner_agent.run_conversation(
        "How do you know that?",
        conversation_history=[
            {"role": "user", "content": "Is everything okay with the homelab?"},
            {"role": "assistant", "content": "The live homelab view is partial."},
        ],
    )
    assert owner_provenance_status.get("completed") is True, owner_provenance_status
    assert owner_provenance_status.get("api_calls") == 0, owner_provenance_status
    assert "source read at" in owner_provenance_status["final_response"], owner_provenance_status
    assert "NetBox describes intended inventory" in owner_provenance_status["final_response"], owner_provenance_status

    registry.calls.clear()
    household_game_status = household_agent.run_conversation(
        "Is the game server working?", conversation_history=[]
    )
    assert household_game_status.get("completed") is True, household_game_status
    assert household_game_status.get("api_calls") == 0, household_game_status
    assert "game-server check" in household_game_status["final_response"].casefold() or "current check" in household_game_status["final_response"].casefold(), household_game_status
    assert "Test Host" not in household_game_status["final_response"]
    assert "192.0.2." not in household_game_status["final_response"]
    assert set(registry.calls) <= {"homelab_summary"}, registry.calls

    registry.calls.clear()
    os.environ["HADES_TEST_SOURCE_UNAVAILABLE"] = "1"
    try:
        outage_result = owner_agent.run_conversation("Check Synthetic Node B.", conversation_history=[])
    finally:
        os.environ.pop("HADES_TEST_SOURCE_UNAVAILABLE", None)
    assert outage_result.get("completed") is True and outage_result.get("api_calls") == 0, outage_result
    assert "running normally" not in outage_result["final_response"].casefold(), outage_result
    assert "can't say whether it's online" in outage_result["final_response"], outage_result
    assert registry.calls[:2] == ["homelab_inference_inventory", "homelab_owner_snapshot"], registry.calls
    assert set(registry.calls) <= {
        "homelab_inference_inventory", "homelab_owner_snapshot",
        "homelab_summary", "homelab_compute_capabilities",
    }, registry.calls
    print("PASS composed Hermes candidate routes named-node reads, preserves household redaction, and fails closed on source outage")
    raise SystemExit(0)
results = {}
for subject in (owner, beta):
    chunks = []
    agent = agent_class(
        gateway_session_key=f"hades-user-{subject}",
        session_id=f"synthetic-chat-{subject}",
        stream_delta_callback=chunks.append,
        **kwargs,
    )
    assert agent._hades_subject == subject
    assert agent._hades_session_scope == ("owner" if subject == owner else "household")
    result = agent.run_conversation("What needs my attention?", conversation_history=[])
    results[subject] = result
    assert result.get("completed") is True and result.get("api_calls") == 0, result
    assert chunks and chunks[-1] == result["final_response"]
assert "Prepare Friday dinner is waiting for your approval." in results[owner]["final_response"], results[owner]
assert "INFRASTRUCTURE: synthetic infrastructure status" in results[owner]["final_response"]
assert "BACKUPS: synthetic backup status" in results[owner]["final_response"]
assert "HOUSEHOLD: synthetic household stock status" in results[owner]["final_response"]
assert "EXPIRY: synthetic expiry status" in results[owner]["final_response"]
assert "FINANCE: synthetic finance status" in results[owner]["final_response"]
assert "TASKS: Prepare Friday dinner is waiting for your approval." in results[owner]["final_response"]
assert "Review Beta's private plan" not in results[owner]["final_response"]
assert "Review Beta's private plan" in results[beta]["final_response"]
assert "synthetic infrastructure status" not in results[beta]["final_response"]
assert "task-owner-approval01" not in results[owner]["final_response"]

# If canonical Task state is unavailable, the live Hermes route must surface
# the bounded retry message and never fall through to the unreachable model.
def unavailable_task_store():
    raise OSError("synthetic Task store outage")
hades._hades_task_store = unavailable_task_store
for subject, prompt in ((owner, "What needs my attention?"), (beta, "Anything I need to do?")):
    outage_agent = agent_class(
        gateway_session_key=f"hades-user-{subject}",
        session_id=f"synthetic-task-store-outage-{subject}",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    outage = outage_agent.run_conversation(prompt, conversation_history=[])
    assert outage.get("completed") is True and outage.get("api_calls") == 0, outage
    assert "I can't check your task updates right now. Please try again shortly." in outage["final_response"], outage

# Restore the source homelab classifier and route a normal plural owner
# question through a synthetic read-only adapter. It must not reach inference.
hades._hades_direct_homelab_read = actual_homelab_read
hades._hades_phase2_backup_response = lambda *_args, **_kwargs: None
hades._hades_direct_household_grocy_read = lambda *_args, **_kwargs: None
hades._hades_direct_grocy_expiry_read = lambda *_args, **_kwargs: None
hades._hades_direct_finance_guidance = lambda *_args, **_kwargs: None

# A diagnostic mentioning a monitor must not be consumed as a request to
# create a Server Health Watch before it reaches the current read-only source.
monitor_read_calls = []
monitor_diagnosis_text = (
    "Uptime Kuma's configured check for service-netbox is down. "
    "That shows the probe failed, but not why. NetBox inventory responded, "
    "but I can't confirm that this probe targets NetBox."
)
def synthetic_monitor_diagnosis(text, subject, scope, context_text=""):
    monitor_read_calls.append((text, subject, scope))
    if text == "Why is the NetBox monitor down?":
        return monitor_diagnosis_text
    return None

hades._hades_direct_homelab_read = synthetic_monitor_diagnosis
try:
    monitor_diagnosis_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}",
        session_id="synthetic-monitor-diagnosis-route",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    monitor_diagnosis_result = monitor_diagnosis_agent.run_conversation(
        "Why is the NetBox monitor down?", conversation_history=[]
    )
finally:
    hades._hades_direct_homelab_read = actual_homelab_read
assert monitor_diagnosis_result.get("completed") is True and monitor_diagnosis_result.get("api_calls") == 0, monitor_diagnosis_result
assert monitor_diagnosis_result.get("final_response") == monitor_diagnosis_text, monitor_diagnosis_result
assert monitor_read_calls == [("Why is the NetBox monitor down?", owner, "owner")], monitor_read_calls

owner_server_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-server-overview",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
class SyntheticManagedGuestControl:
    def list_managed_guests(self):
        return {"status": "READY", "guests": [{
            "name": "gamma-sandbox", "status": "running", "node": "test-pve", "vmid": 900,
        }]}

control_loader_calls = []
actual_control_loader = hades._hades_load_control_module
def synthetic_control_loader():
    control_loader_calls.append("list_managed_guests")
    return SyntheticManagedGuestControl()
hades._hades_load_control_module = synthetic_control_loader
try:
    owner_minecraft_location_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}", session_id="synthetic-minecraft-location-owner",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    owner_minecraft_location = owner_minecraft_location_agent.run_conversation(
        "Where is the Minecraft server running?", conversation_history=[]
    )
    household_minecraft_location_agent = agent_class(
        gateway_session_key=f"hades-user-{beta}", session_id="synthetic-minecraft-location-household",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    household_minecraft_location = household_minecraft_location_agent.run_conversation(
        "Where is the Minecraft server running?", conversation_history=[]
    )
finally:
    hades._hades_load_control_module = actual_control_loader
assert owner_minecraft_location.get("completed") is True and owner_minecraft_location.get("api_calls") == 0, owner_minecraft_location
assert "NetBox service inventory is empty" in owner_minecraft_location["final_response"], owner_minecraft_location
assert "gamma-sandbox" not in owner_minecraft_location["final_response"] and "test-pve" not in owner_minecraft_location["final_response"], owner_minecraft_location
assert household_minecraft_location.get("completed") is True and household_minecraft_location.get("api_calls") == 0, household_minecraft_location
assert "can't provide internal host or address details" in household_minecraft_location["final_response"], household_minecraft_location
assert "gamma-sandbox" not in household_minecraft_location["final_response"] and "test-pve" not in household_minecraft_location["final_response"], household_minecraft_location
assert control_loader_calls == [], control_loader_calls
server_overview = owner_server_agent.run_conversation(
    "Is everything okay with the servers?", conversation_history=[]
)
assert server_overview.get("completed") is True and server_overview.get("api_calls") == 0, server_overview
assert "Live Proxmox currently reports: hades-core." in server_overview["final_response"], server_overview
assert "memory update" not in server_overview["final_response"].casefold(), server_overview
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

os.environ["HADES_TEST_INFERENCE_ONLY"] = "1"
model_location_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-model-location",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
model_location = model_location_agent.run_conversation(
    "Where's sample:small?", conversation_history=[]
)
assert model_location.get("completed") is True and model_location.get("api_calls") == 0, model_location
assert "sample:small is listed at Compute Node A" in model_location["final_response"], model_location
assert "generation request was not made" in model_location["final_response"], model_location

model_inventory_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-model-inventory",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
model_inventory = model_inventory_agent.run_conversation(
    "Which inference models are available right now?", conversation_history=[]
)
assert model_inventory.get("completed") is True and model_inventory.get("api_calls") == 0, model_inventory
assert "sample:small is listed at Compute Node A" in model_inventory["final_response"], model_inventory

for index, prompt in enumerate(("Which GPUs are free?", "Where should I run another model?")):
    placement_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}",
        session_id=f"synthetic-model-placement-{index}",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    placement = placement_agent.run_conversation(prompt, conversation_history=[])
    assert placement.get("completed") is True and placement.get("api_calls") == 0, (prompt, placement)
    assert "can't determine which GPU has room" in placement["final_response"], (prompt, placement)
os.environ.pop("HADES_TEST_INFERENCE_ONLY", None)

# Ordinary status wording should stay on the same deterministic, read-only
# route even when it says "doing" or "computers" instead of "server status".
# The configured model endpoint is deliberately unavailable, so any fallthrough
# to inference fails this contract instead of returning a fabricated answer.
for index, prompt in enumerate((
    "Is everything okay?",
    "What's down?",
    "How are the servers doing?",
    "Are all the computers okay?",
    "Why does the network feel slow?",
    "What changed since yesterday?",
)):
    hermes_registry_module.registry.calls.clear()
    variant_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}",
        session_id=f"synthetic-server-overview-variant-{index}",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    variant = variant_agent.run_conversation(prompt, conversation_history=[])
    assert variant.get("completed") is True and variant.get("api_calls") == 0, (prompt, variant)
    assert "Live Proxmox currently reports: hades-core." in variant["final_response"], (prompt, variant)
    assert "memory update" not in variant["final_response"].casefold(), (prompt, variant)
    if prompt == "What changed since yesterday?":
        assert "No recent Proxmox or NetBox activity source is configured" in variant["final_response"], variant
        assert "homelab_inference_inventory" not in hermes_registry_module.registry.calls, hermes_registry_module.registry.calls
    assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

ai_availability_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-ai-availability",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
ai_availability = ai_availability_agent.run_conversation(
    "Can we use the AI thing right now?", conversation_history=[]
)
assert ai_availability.get("completed") is True and ai_availability.get("api_calls") == 0, ai_availability
assert "provider checks are responding to catalog reads" in ai_availability["final_response"], ai_availability
assert "haven't tested a generation" in ai_availability["final_response"], ai_availability
# A definition request should stay conversational instead of consulting the
# managed guest inventory. Instrument the real Hermes shortcut loader.
control_loader_calls = []
actual_control_loader = hades._hades_load_control_module
def counted_control_loader(*args, **kwargs):
    control_loader_calls.append(True)
    return actual_control_loader(*args, **kwargs)
hades._hades_load_control_module = counted_control_loader
definition_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-server-definition",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
definition = definition_agent.run_conversation("What is a server?", conversation_history=[])
hades._hades_load_control_module = actual_control_loader
assert not control_loader_calls, control_loader_calls
assert "Live Proxmox currently reports" not in definition.get("final_response", ""), definition
assert "HADES-managed server" not in definition.get("final_response", ""), definition

# One ordinary owner turn can ask for current infrastructure and backup
# coverage together; both bounded sources must contribute to the answer.
compound_calls = {"infrastructure": 0, "backup": 0}
def compound_infrastructure(*_args, **_kwargs):
    compound_calls["infrastructure"] += 1
    return "Live Proxmox reports synthetic-hades-core running."
def compound_backup(*_args, **_kwargs):
    compound_calls["backup"] += 1
    return "Your Backup Checks: HADES repository — enabled."
hades._hades_direct_homelab_read = compound_infrastructure
hades._hades_phase2_backup_response = compound_backup
compound_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-compound-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
compound_status = compound_agent.run_conversation(
    "Are all the servers okay, and what backup coverage do I have?",
    conversation_history=[],
)
assert compound_status.get("completed") is True and compound_status.get("api_calls") == 0, compound_status
assert "SERVER STATUS:" in compound_status["final_response"] and "synthetic-hades-core running" in compound_status["final_response"], compound_status
assert "BACKUP COVERAGE:" in compound_status["final_response"] and "HADES repository — enabled" in compound_status["final_response"], compound_status
assert compound_calls == {"infrastructure": 1, "backup": 1}, compound_calls
assert hades._hades_direct_homelab_backup_compound(
    "Are all the servers okay, and what backup coverage do I have?", beta, "household", "test-chat"
) is None
assert hades._hades_direct_homelab_backup_compound(
    "Check the servers and run a backup check", owner, "owner", "test-chat"
) is None
assert hades._hades_direct_homelab_backup_compound(
    "Yes, what backup coverage do I have and are the servers okay?", owner, "owner", "test-chat"
) is None
assert hades._hades_direct_homelab_backup_compound(
    "Cancel the backup request and tell me whether the servers are okay", owner, "owner", "test-chat"
) is None
hades._hades_direct_homelab_read = actual_homelab_read
hades._hades_phase2_backup_response = actual_backup_read
actual_compound_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-real-compound-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
actual_compound_status = actual_compound_agent.run_conversation(
    "Are all the servers okay, and what backup coverage do I have?",
    conversation_history=[],
)
assert actual_compound_status.get("completed") is True and actual_compound_status.get("api_calls") == 0, actual_compound_status
assert "Live Proxmox currently reports: hades-core." in actual_compound_status["final_response"], actual_compound_status
assert "No Backup Check exists yet." in actual_compound_status["final_response"], actual_compound_status
assert "can't verify host, VM, service, or household-data backup coverage" in actual_compound_status["final_response"], actual_compound_status
actual_proxmox_backup_read = hades._hades_direct_proxmox_backup_read
actual_homelab_tool_result = hades._hades_direct_homelab_tool_result
backup_tool_calls = []
def synthetic_scoped_backup_tool_result(tool_name):
    backup_tool_calls.append(tool_name)
    return {
        "status": "PARTIAL",
        "formatted_summary": (
            "No archived task was returned for the selected guest(s). "
            "Other guest task history is unknown."
        ),
    }
hades._hades_direct_homelab_tool_result = synthetic_scoped_backup_tool_result
old_working_directory = os.environ.get("HADES_HERMES_WORKING_DIRECTORY")
try:
    with tempfile.TemporaryDirectory(prefix="hades-stale-backup-formatter-") as stale_root:
        stale_adapter = Path(stale_root) / "integrations" / "homelab-readonly" / "server.py"
        stale_adapter.parent.mkdir(parents=True)
        stale_adapter.write_text("raise AssertionError('stale adapter formatter imported')\n")
        os.environ["HADES_HERMES_WORKING_DIRECTORY"] = stale_root
        scope_aware_backup_answer = hades._hades_direct_proxmox_backup_read(
            "Are my backups okay?", owner, "owner", "synthetic-backup-scope",
            include_hades_checks=False,
        )
        assert "No archived task was returned for the selected guest(s)" in scope_aware_backup_answer
        assert "Other guest task history is unknown" in scope_aware_backup_answer
        assert backup_tool_calls == ["homelab_backup_status"], backup_tool_calls
finally:
    if old_working_directory is None:
        os.environ.pop("HADES_HERMES_WORKING_DIRECTORY", None)
    else:
        os.environ["HADES_HERMES_WORKING_DIRECTORY"] = old_working_directory
hades._hades_direct_homelab_tool_result = lambda _name: {
    "status": "PARTIAL", "tasks": [{"guest_id": "must-not-escape"}],
}
missing_scope_summary = hades._hades_direct_proxmox_backup_read(
    "Are my backups okay?", owner, "owner", "synthetic-backup-missing-summary",
    include_hades_checks=False,
)
assert "did not provide a scope-verified backup summary" in missing_scope_summary
assert "must-not-escape" not in missing_scope_summary
hades._hades_direct_homelab_tool_result = actual_homelab_tool_result
proxmox_backup_calls = []
def synthetic_proxmox_backup(text, subject, scope, session_key, *, allow_homelab_context=False, **_kwargs):
    proxmox_backup_calls.append((text, subject, scope, allow_homelab_context))
    if "proxmox" in text.lower() and not allow_homelab_context:
        return None
    return "PROXMOX VZDUMP: no configured jobs or recent archived tasks."
hades._hades_direct_proxmox_backup_read = synthetic_proxmox_backup
proxmox_backup_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-proxmox-backup-read",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
proxmox_backup_status = proxmox_backup_agent.run_conversation(
    "Are my Proxmox backups current?", conversation_history=[]
)
hades._hades_direct_proxmox_backup_read = actual_proxmox_backup_read
assert proxmox_backup_status.get("completed") is True and proxmox_backup_status.get("api_calls") == 0, proxmox_backup_status
assert "PROXMOX VZDUMP: no configured jobs" in proxmox_backup_status["final_response"], proxmox_backup_status
assert proxmox_backup_calls == [
    ("Are my Proxmox backups current?", owner, "owner", False),
    ("Are my backups okay?", owner, "owner", True),
], proxmox_backup_calls
generic_backup_calls = []
def synthetic_generic_backup(text, subject, scope, session_key, *, allow_homelab_context=False, **_kwargs):
    generic_backup_calls.append((text, subject, scope, allow_homelab_context))
    return "PROXMOX VZDUMP: bounded evidence. HADES BACKUP CHECKS: repository status."
hades._hades_direct_proxmox_backup_read = synthetic_generic_backup
generic_backup_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-generic-backup-read",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
generic_backup_status = generic_backup_agent.run_conversation(
    "Are my backups current?", conversation_history=[]
)
hades._hades_direct_proxmox_backup_read = actual_proxmox_backup_read
assert generic_backup_status.get("completed") is True and generic_backup_status.get("api_calls") == 0, generic_backup_status
assert "PROXMOX VZDUMP: bounded evidence." in generic_backup_status["final_response"], generic_backup_status
assert generic_backup_calls == [("Are my backups current?", owner, "owner", True)], generic_backup_calls
read_only_summary_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-explicit-read-only",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
read_only_summary = read_only_summary_agent.run_conversation(
    "Is everything okay with the homelab? Please only check and report; do not change anything.",
    conversation_history=[],
)
assert read_only_summary.get("completed") is True and read_only_summary.get("api_calls") == 0, read_only_summary
assert "Live Proxmox currently reports: hades-core." in read_only_summary["final_response"], read_only_summary
os.environ["HADES_TEST_LEGACY_GUEST_VISIBILITY"] = "1"
try:
    legacy_summary_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}", session_id="synthetic-legacy-proxmox-scope",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    legacy_summary = legacy_summary_agent.run_conversation(
        "Is everything okay?", conversation_history=[]
    )
finally:
    os.environ.pop("HADES_TEST_LEGACY_GUEST_VISIBILITY", None)
assert legacy_summary.get("completed") is True and legacy_summary.get("api_calls") == 0, legacy_summary
assert "couldn't verify the Proxmox guest-visibility scope" in legacy_summary["final_response"], legacy_summary
assert "unreported guests may be missing" in legacy_summary["final_response"], legacy_summary
household_game_agent = agent_class(
    gateway_session_key=f"hades-user-{beta}", session_id="synthetic-household-game-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
household_ai_availability = household_game_agent.run_conversation(
    "Can we use the AI thing right now?", conversation_history=[]
)
assert household_ai_availability.get("completed") is True and household_ai_availability.get("api_calls") == 0, household_ai_availability
assert "AI service checks are responding" in household_ai_availability["final_response"], household_ai_availability
assert "haven't confirmed a prompt will work" in household_ai_availability["final_response"], household_ai_availability
assert "Synthetic Inference Node A" not in household_ai_availability["final_response"], household_ai_availability
household_game_status = household_game_agent.run_conversation(
    "Is Minecraft working?", conversation_history=[],
)
assert household_game_status.get("completed") is True and household_game_status.get("api_calls") == 0, household_game_status
assert "can't confirm whether the game server is working" in household_game_status["final_response"], household_game_status
assert "192.0.2." not in household_game_status["final_response"], household_game_status
household_game_location = household_game_agent.run_conversation(
    "Where does Minecraft run?", conversation_history=[],
)
assert household_game_location.get("completed") is True and household_game_location.get("api_calls") == 0, household_game_location
assert "can't provide internal host or address details" in household_game_location["final_response"], household_game_location
assert "192.0.2." not in household_game_location["final_response"], household_game_location
actual_phase3_response = hades._hades_phase3_response
def forbid_monitor_diagnosis_phase3(text, *_args, **_kwargs):
    if text == "Why is the NetBox monitor down?":
        raise AssertionError("household monitor diagnosis must stop before staged automation routing")
    return actual_phase3_response(text, *_args, **_kwargs)

hades._hades_phase3_response = forbid_monitor_diagnosis_phase3
try:
    household_monitor_diagnosis = household_game_agent.run_conversation(
        "Why is the NetBox monitor down?", conversation_history=[]
    )
finally:
    hades._hades_phase3_response = actual_phase3_response
assert household_monitor_diagnosis.get("completed") is True and household_monitor_diagnosis.get("api_calls") == 0, household_monitor_diagnosis
assert "can't verify private infrastructure or computer status from this account" in household_monitor_diagnosis["final_response"].casefold(), household_monitor_diagnosis
assert "NetBox" not in household_monitor_diagnosis["final_response"] and "Kuma" not in household_monitor_diagnosis["final_response"]
os.environ["HADES_TEST_SOURCE_UNAVAILABLE"] = "1"
try:
    unavailable_summary = hades._hades_direct_homelab_tool_result("homelab_summary")
    assert unavailable_summary.get("status") == "SOURCE_UNAVAILABLE", unavailable_summary
    failed_owner_read_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-source-outage",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    failed_owner_read = failed_owner_read_agent.run_conversation(
        "Is everything okay with the homelab?", conversation_history=[]
    )
    assert failed_owner_read.get("completed") is True and failed_owner_read.get("api_calls") == 0, failed_owner_read
    assert "couldn't verify the current homelab sources" in failed_owner_read["final_response"], failed_owner_read
    failed_household_read = household_game_agent.run_conversation(
        "Is Minecraft working?", conversation_history=[]
    )
    assert failed_household_read.get("completed") is True and failed_household_read.get("api_calls") == 0, failed_household_read
    assert "because the current check could not be read" in failed_household_read["final_response"], failed_household_read
    assert "synthetic source unavailable" not in failed_household_read["final_response"], failed_household_read
finally:
    os.environ.pop("HADES_TEST_SOURCE_UNAVAILABLE", None)
print("PASS registered homelab MCP source outages return explicit unknown owner/household answers without model fallback")
registered_homelab_registry = hermes_registry_module.registry
class MissingHomelabRegistry:
    def get_entry(self, _name):
        return None

    def dispatch(self, *_args, **_kwargs):
        raise AssertionError("unregistered homelab tool must not dispatch or use a parent adapter")

hermes_registry_module.registry = MissingHomelabRegistry()
try:
    unconfigured_owner = agent_class(
        gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-not-registered",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    ).run_conversation("Is everything okay with the homelab?", conversation_history=[])
    assert unconfigured_owner.get("completed") is True and unconfigured_owner.get("api_calls") == 0, unconfigured_owner
    assert "couldn't verify the current homelab sources" in unconfigured_owner["final_response"], unconfigured_owner
    unconfigured_household = household_game_agent.run_conversation(
        "Is Minecraft working?", conversation_history=[],
    )
    assert unconfigured_household.get("completed") is True and unconfigured_household.get("api_calls") == 0, unconfigured_household
    assert "because the current check could not be read" in unconfigured_household["final_response"], unconfigured_household
finally:
    hermes_registry_module.registry = registered_homelab_registry
print("PASS missing homelab MCP registration fails closed for owner and household")
hades._hades_phase2_backup_response = lambda *_args, **_kwargs: None
provenance_history = [
    {"role": "user", "content": "Is everything okay with the homelab?"},
    {"role": "assistant", "content": "The live homelab view is partial."},
]
provenance_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-provenance",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
provenance_result = provenance_agent.run_conversation(
    "When was that checked?", conversation_history=provenance_history,
)
assert provenance_result.get("completed") is True and provenance_result.get("api_calls") == 0, provenance_result
assert "refreshed the configured homelab sources" in provenance_result["final_response"], provenance_result
assert "Proxmox: healthy; source read at 2026-10-02T14:00:00+00:00" in provenance_result["final_response"], provenance_result
assert "NetBox: healthy; source read at 2026-10-02T14:00:01+00:00" in provenance_result["final_response"], provenance_result
assert "they are not interchangeable" in provenance_result["final_response"], provenance_result
assert hades._hades_direct_homelab_read("When was that checked?", owner, "owner") is None
household_provenance_direct = hades._hades_direct_homelab_read(
    "When was that checked?", beta, "household",
    context_text="Is everything okay with the homelab?",
)
assert "can't verify private infrastructure or computer status" in household_provenance_direct.casefold(), household_provenance_direct
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

# A speech-like named-node question composes linked inference state with the
# observed hardware inventory without turning it into live load/health evidence.
compute_node_a_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-compute-node-a-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
compute_node_a_status = compute_node_a_agent.run_conversation(
    "whats compute-node-a doing rn", conversation_history=[]
)
assert compute_node_a_status.get("completed") is True and compute_node_a_status.get("api_calls") == 0, compute_node_a_status
compute_node_a_text = compute_node_a_status["final_response"]
assert "sample:small is listed at Compute Node A" in compute_node_a_text, compute_node_a_text
assert "Observed hardware inventory lists Compute Node A." in compute_node_a_text, compute_node_a_text
assert "Role: synthetic inference node." in compute_node_a_text, compute_node_a_text
assert "Host CPU/GPU load and free VRAM are not connected." in compute_node_a_text, compute_node_a_text
assert "I don't have a current host runtime check for it" in compute_node_a_text, compute_node_a_text
assert "192.0.2.69" not in compute_node_a_text, compute_node_a_text
registry = hermes_registry_module.registry
registry.calls.clear()
check_synthetic_node_b = hades._hades_direct_homelab_read(
    "Check Synthetic Node B.", owner, "owner",
)
assert registry.calls == ["homelab_inference_inventory", "homelab_owner_snapshot"], registry.calls
assert "Observed hardware inventory lists Synthetic Node B." in check_synthetic_node_b, check_synthetic_node_b
assert "can't say whether it's online" in check_synthetic_node_b, check_synthetic_node_b
assert "running normally" not in check_synthetic_node_b.casefold(), check_synthetic_node_b
check_synthetic_node_b_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-named-check-current-source",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
check_synthetic_node_b_result = check_synthetic_node_b_agent.run_conversation(
    "Check Synthetic Node B.", conversation_history=[]
)
assert check_synthetic_node_b_result.get("completed") is True and check_synthetic_node_b_result.get("api_calls") == 0, check_synthetic_node_b_result
assert "Observed hardware inventory lists Synthetic Node B." in check_synthetic_node_b_result["final_response"], check_synthetic_node_b_result
assert "running normally" not in check_synthetic_node_b_result["final_response"].casefold(), check_synthetic_node_b_result
os.environ["HADES_TEST_SOURCE_UNAVAILABLE"] = "1"
try:
    unavailable_source_check = hades._hades_direct_homelab_read(
        "Check Synthetic Node B.", owner, "owner",
    )
finally:
    os.environ.pop("HADES_TEST_SOURCE_UNAVAILABLE", None)
assert "can't say whether it's online" in unavailable_source_check, unavailable_source_check
assert "running normally" not in unavailable_source_check.casefold(), unavailable_source_check
assert hades._hades_direct_homelab_read("Check my shopping list", owner, "owner") is None
registry.calls.clear()
direct_node_status = hades._hades_direct_homelab_read(
    "What's Compute Node A doing right now?", owner, "owner",
)
assert registry.calls == ["homelab_inference_inventory", "homelab_owner_snapshot"], registry.calls
assert "Observed hardware inventory lists Compute Node A." in direct_node_status, direct_node_status
issue_status = compute_node_a_agent.run_conversation(
    "What's wrong with Compute Node A?", conversation_history=[],
)
assert issue_status.get("completed") is True and issue_status.get("api_calls") == 0, issue_status
assert "sample:small is listed at Compute Node A" in issue_status["final_response"], issue_status
assert "I don't have a current host runtime check for it" in issue_status["final_response"], issue_status
capacity_history = [
    {"role": "user", "content": "What's wrong with Compute Node A?"},
    {"role": "assistant", "content": "Compute Node A has one provider-reported model."},
    {"role": "user", "content": "Could I put another model there?"},
    {"role": "assistant", "content": "Current free VRAM is unknown for Compute Node A."},
]
capacity_context = "\n".join(item["content"] for item in capacity_history) + "\nWhat about a 20 GB one?"
os.environ["HADES_TEST_FOLLOWUP_NODE"] = "1"
try:
    resolved_capacity_prompt = hades._hades_homelab_followup_prompt(
        "What about a 20 GB one?", "owner", capacity_context,
    )
    assert resolved_capacity_prompt == "Can Compute Node A host a 20 GB model?", resolved_capacity_prompt
    capacity_followup = compute_node_a_agent.run_conversation(
        "What about a 20 GB one?", conversation_history=capacity_history,
    )
    unanchored_capacity_followup = compute_node_a_agent.run_conversation(
        "What about a 20 GB one?", conversation_history=[],
    )
finally:
    os.environ.pop("HADES_TEST_FOLLOWUP_NODE", None)
assert capacity_followup.get("completed") is True and capacity_followup.get("api_calls") == 0, capacity_followup
assert "can't confirm whether that model fits" in capacity_followup["final_response"], capacity_followup
assert unanchored_capacity_followup.get("completed") is True and unanchored_capacity_followup.get("api_calls") == 0, unanchored_capacity_followup
assert "can't confirm whether that model fits" in unanchored_capacity_followup["final_response"], unanchored_capacity_followup
actual_node_read = hades._hades_direct_homelab_read
hades._hades_direct_homelab_read = lambda *_args, **_kwargs: None
unavailable_node_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-unavailable-node-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
unavailable_node = unavailable_node_agent.run_conversation(
    "What is Synthetic Node B running?", conversation_history=[]
)
unavailable_check_node = unavailable_node_agent.run_conversation(
    "Check Synthetic Node B.", conversation_history=[]
)
unavailable_issue = unavailable_node_agent.run_conversation(
    "What's wrong with Synthetic Inference Node A?", conversation_history=[]
)
def unexpected_capacity_read(*_args, **_kwargs):
    raise AssertionError("owner capacity follow-up must fail closed before starting a slow live read")

hades._hades_direct_homelab_read = unexpected_capacity_read
unavailable_size = unavailable_node_agent.run_conversation(
    "What about a 20 GB one?", conversation_history=[]
)
hades._hades_direct_homelab_read = actual_node_read
assert unavailable_node.get("completed") is True and unavailable_node.get("api_calls") == 0, unavailable_node
assert "couldn't verify current runtime or workload status for synthetic node b" in unavailable_node["final_response"], unavailable_node
assert unavailable_check_node.get("completed") is True and unavailable_check_node.get("api_calls") == 0, unavailable_check_node
assert "couldn't verify current runtime or workload status for synthetic node b" in unavailable_check_node["final_response"].casefold(), unavailable_check_node
assert unavailable_issue.get("completed") is True and unavailable_issue.get("api_calls") == 0, unavailable_issue
assert "couldn't verify current runtime or workload status for synthetic inference node a" in unavailable_issue["final_response"].casefold(), unavailable_issue
assert unavailable_size.get("completed") is True and unavailable_size.get("api_calls") == 0, unavailable_size
assert "can't confirm whether that model fits" in unavailable_size["final_response"], unavailable_size
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

# A fresh, similarly named Kuma check with no stable identity link is useful
# evidence, but must not be collapsed into proof that the physical host is up.
os.environ["HADES_TEST_HOMELAB_UNLINKED_NODE_B"] = "1"
unlinked_monitor = hades._hades_direct_homelab_read(
    "Is Inference Node B alive?", owner, "owner",
)
assert "Uptime Kuma's separate monitor named host-inference-node-b reports up (fresh observation)." in unlinked_monitor, unlinked_monitor
assert "can't confirm that this monitor targets inference node b" in unlinked_monitor.casefold(), unlinked_monitor
assert "couldn't verify inference node b" in unlinked_monitor.casefold(), unlinked_monitor
assert "inference node b is online" not in unlinked_monitor.casefold(), unlinked_monitor
del os.environ["HADES_TEST_HOMELAB_UNLINKED_NODE_B"]

# A physical host may be visible to Kuma without a Proxmox runtime row. Its
# fresh probe is useful reachability evidence, but must not be relabeled as a
# Proxmox status or as proof of workload health.
os.environ["HADES_TEST_HOMELAB_NODE_A_MONITOR"] = "1"
compute_node_a_monitor_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-compute-node-a-monitor-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
compute_node_a_monitor_status = compute_node_a_monitor_agent.run_conversation(
    "whats compute-node-a doing rn", conversation_history=[]
)
assert compute_node_a_monitor_status.get("completed") is True and compute_node_a_monitor_status.get("api_calls") == 0, compute_node_a_monitor_status
compute_node_a_monitor_text = compute_node_a_monitor_status["final_response"]
assert "the compute node a ssh check is responding (fresh observation)" in compute_node_a_monitor_text.casefold(), compute_node_a_monitor_text
assert "current host workload or operating-system status" in compute_node_a_monitor_text, compute_node_a_monitor_text
assert "No stable identity link confirms that this monitor targets the named host." in compute_node_a_monitor_text, compute_node_a_monitor_text
assert "Proxmox runtime status is NOT_OBSERVED" not in compute_node_a_monitor_text, compute_node_a_monitor_text
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
for status, freshness, expected in (
    ("down", "FRESH", "the Compute Node A SSH check is failing (fresh observation)"),
    ("up", "STALE", "the Compute Node A SSH check last reported up, but that observation is stale"),
):
    os.environ["HADES_TEST_NODE_A_MONITOR_STATUS"] = status
    os.environ["HADES_TEST_NODE_A_MONITOR_FRESHNESS"] = freshness
    monitor_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}", session_id=f"synthetic-compute-node-a-monitor-{status}-{freshness}",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    monitor_result = monitor_agent.run_conversation("whats compute-node-a doing rn", conversation_history=[])
    assert monitor_result.get("completed") is True and monitor_result.get("api_calls") == 0, monitor_result
    assert expected.casefold() in monitor_result["final_response"].casefold(), monitor_result
    assert "No stable identity link confirms that this monitor targets the named host." in monitor_result["final_response"], monitor_result
    assert "Proxmox runtime status is NOT_OBSERVED" not in monitor_result["final_response"], monitor_result
    assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
del os.environ["HADES_TEST_NODE_A_MONITOR_STATUS"]
del os.environ["HADES_TEST_NODE_A_MONITOR_FRESHNESS"]
del os.environ["HADES_TEST_HOMELAB_NODE_A_MONITOR"]

blockers_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-blockers",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
blocker_summary = blockers_agent.run_conversation(
    "Are there any blockers in the homelab?", conversation_history=[]
)
assert blocker_summary.get("completed") is True and blocker_summary.get("api_calls") == 0, blocker_summary
assert "Live Proxmox currently reports: hades-core." in blocker_summary["final_response"], blocker_summary
assert "No service availability observations are available, so I can't confirm service health." in blocker_summary["final_response"], blocker_summary
assert "No blocker was reported by the configured live sources." not in blocker_summary["final_response"], blocker_summary
assert "HADES Core runtime is running." in blocker_summary["final_response"], blocker_summary

# A normal-language performance complaint must combine live resource and
# service-probe evidence while clearly stating that neither proves a network
# bottleneck. The model endpoint is unavailable and must not be consulted.
os.environ["HADES_TEST_HOMELAB_BOTTLENECK"] = "1"
network_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-network-diagnosis",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
registry.calls.clear()
network_diagnosis = network_agent.run_conversation(
    "Something feels slow on the network; check node status, network health, recent resource usage, and services, then tell me what looks abnormal.",
    conversation_history=[],
)
assert network_diagnosis.get("completed") is True and network_diagnosis.get("api_calls") == 0, network_diagnosis
network_text = network_diagnosis["final_response"]
assert "Live Proxmox currently reports: hades-core." in network_text, network_text
assert "CPU 94.0%" in network_text, network_text
assert "Uptime Kuma's configured probes failed: Search latency check." in network_text, network_text
assert "Fresh configured-probe response-time samples: Router ping: 84 ms." in network_text, network_text
assert "Packet-loss, throughput, and historical comparison data are unavailable" in network_text, network_text
assert "cannot identify a network bottleneck or trend from this evidence" in network_text, network_text
assert "homelab_inference_inventory" not in registry.calls, registry.calls
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
registry.calls.clear()
natural_network_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-natural-network-diagnosis",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
natural_network = natural_network_agent.run_conversation(
    "Why does the network feel slow?", conversation_history=[],
)
assert natural_network.get("completed") is True and natural_network.get("api_calls") == 0, natural_network
assert "Fresh configured-probe response-time samples:" in natural_network["final_response"], natural_network
assert "cannot identify a network bottleneck or trend from this evidence" in natural_network["final_response"], natural_network
assert "homelab_inference_inventory" not in registry.calls, registry.calls
del os.environ["HADES_TEST_HOMELAB_BOTTLENECK"]

# A nontechnical household user who cannot name the TV device gets a focused
# question instead of an invented homelab diagnosis or a model/tool detour.
for subject in (owner, beta):
    media_agent = agent_class(
        gateway_session_key=f"hades-user-{subject}", session_id=f"synthetic-media-{subject}",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    media_help = media_agent.run_conversation(
        "The thing we watch movies on isn't working.", conversation_history=[]
    )
    assert media_help.get("completed") is True and media_help.get("api_calls") == 0, media_help
    assert "Do you mean the TV, a streaming box, or an app?" in media_help["final_response"], media_help
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
assert store.get("task-beta-failed0001", beta)["status"] == TaskStatus.FAILED.value

seen = []
class ResultHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(request["requester_subject_id"])
        rows = ([{
            "template_type": "low-inventory-summary",
            "resource_scope": ["grocy.household"],
            "completed_at": 123,
            "result": {"hades_state": "READY", "low": '["Rice"]', "out": [], "no_minimum": []},
        }] if request["requester_subject_id"] == owner else [])
        raw = json.dumps({"results": rows}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def log_message(self, *_args):
        return

server = ThreadingHTTPServer(("127.0.0.1", 0), ResultHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
key_path = os.environ["HADES_TEST_RESULT_KEY_FILE"]
with open(key_path, "wb") as key_file:
    key_file.write(b"synthetic-hermes-result-query-key-material")
os.chmod(key_path, 0o600)
os.environ["HADES_EPSILON_PHASE3_RESULT_QUERY_URL"] = f"http://127.0.0.1:{server.server_port}/v1/epsilon/phase3/results"
os.environ["HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE"] = key_path
try:
    query_responses = {}
    for subject in (owner, beta):
        agent = agent_class(gateway_session_key=f"hades-user-{subject}", session_id=f"result-chat-{subject}", **kwargs)
        result = agent.run_conversation("Show my latest automation results", conversation_history=[])
        assert result.get("completed") is True and result.get("api_calls") == 0, result
        query_responses[subject] = result["final_response"]
    assert "1 item(s) below minimum" in query_responses[owner]
    assert "Rice" in query_responses[owner]
    assert "no completed automation results" in query_responses[beta].casefold()
    assert "run_id" not in query_responses[owner] and "automation_id" not in query_responses[owner]
    assert seen == [owner, beta], seen
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
print("PASS Hermes 0.21.2 HADES runtime: owner attention briefing combines live-source and private Task summaries; household Task attention and authenticated-subject result summaries remain scoped, zero model calls")
print("PASS plural owner server-status question bypasses non-confirming task approval language and uses the deterministic read-only homelab route with no model call")
print("PASS one read-only owner turn composes live homelab status and Backup Check coverage, while household and action requests stay outside the shortcut")
print("PASS speech-like named-node status separates Compute Node A's hardware listing from missing live runtime evidence")
print("PASS physical-node wording uses a fresh monitor as reachability evidence without relabeling it as Proxmox runtime or workload health")
print("PASS detailed homelab summary reports missing service observations as unknown, not as no blockers")
print("PASS network-slowness question combines synthetic Proxmox and Kuma evidence, states missing network trends, and makes zero model calls")
print("PASS ambiguous household entertainment-device trouble gets a plain-language clarification for owner and household without task changes or model calls")
'''

with tempfile.TemporaryDirectory(prefix="hades-hermes-task-runtime-") as tmp:
    root = Path(tmp)
    home = root / "home"
    hermes_home = root / "hermes"
    home.mkdir(mode=0o700)
    hermes_home.mkdir(mode=0o700)
    homelab = root / "homelab"
    adapter = homelab / "integrations" / "homelab-readonly"
    adapter.mkdir(parents=True, mode=0o700)
    (adapter / "server.py").write_text(
        'def homelab_summary():\n'
        '    if __import__("os").environ.get("HADES_TEST_SOURCE_UNAVAILABLE") == "1":\n'
        '        raise RuntimeError("synthetic source unavailable")\n'
        '    if __import__("os").environ.get("HADES_TEST_INFERENCE_ONLY") == "1":\n'
        '        raise AssertionError("inference-only query must not read broad homelab summary")\n'
        '    resources = [{"name": "hades-core", "runtime_status": "running",\n'
        '                  "currently_online": True,\n'
        '                  "runtime": {"name": "hades-core", "vmid": 1802, "status": "running",\n'
        '                              "cpu": 0.94, "mem": 32212254720, "maxmem": 34359738368,\n'
        '                              "disk": 85899345920, "maxdisk": 96636764160}}]\n'
        '    if __import__("os").environ.get("HADES_TEST_FOLLOWUP_NODE") == "1":\n'
        '        resources.append({"name": "Compute Node A", "inventory": {"name": "Compute Node A"},\n'
        '                          "identity": {"canonical_id": "netbox:device:7"}})\n'
        '    if __import__("os").environ.get("HADES_TEST_HOMELAB_NODE_A_MONITOR") == "1":\n'
        '        resources.append({"name": "Compute Node A SSH", "runtime_status": "NOT_OBSERVED",\n'
        '                          "currently_online": False, "inventory": None,\n'
        '                          "availability": {"name": "Compute Node A SSH",\n'
        '                                           "status": __import__("os").environ.get("HADES_TEST_NODE_A_MONITOR_STATUS", "up"),\n'
        '                                           "last_updated": "2026-09-27T00:00:00Z"},\n'
        '                          "availability_freshness": __import__("os").environ.get("HADES_TEST_NODE_A_MONITOR_FRESHNESS", "FRESH"),\n'
        '                          "conflicts": []})\n'
        '    return {\n'
        '        "status": "OK",\n'
        '        "online_names": ["hades-core"],\n'
        '        "inventory_only_names": [],\n'
        '        "proxmox_guest_visibility": (None if __import__("os").environ.get("HADES_TEST_LEGACY_GUEST_VISIBILITY") == "1" else {"status": "COMPLETE", "scope": "ALL_GUESTS", "endpoints": [{"source_identity": "proxmox:pve-main", "status": "HEALTHY", "scope": "ALL_GUESTS", "scoped_guest_count": None}]}),\n'
        '        "availability_summary": ([{"name": "Search latency check", "status": "down", "freshness": "FRESH"},\n'
        '                                  {"name": "Router ping", "status": "up", "freshness": "FRESH", "ping_ms": 84}]\n'
        '                                if __import__("os").environ.get("HADES_TEST_HOMELAB_BOTTLENECK") == "1" else []) +\n'
        '                               ([{"name": "host-inference-node-b", "status": "up", "freshness": "FRESH",\n'
        '                                  "source_identity": "kuma:monitor:17"}]\n'
        '                                if __import__("os").environ.get("HADES_TEST_HOMELAB_UNLINKED_NODE_B") == "1" else []),\n'
        '        "conflicts": [],\n'
        '        "errors": [],\n'
        '        "sources": [{"source": "Proxmox", "status": "HEALTHY", "retrieved_at": "2026-10-02T14:00:00+00:00"},\n'
        '                    {"source": "NetBox", "status": "HEALTHY", "retrieved_at": "2026-10-02T14:00:01+00:00"}],\n'
        '        "service_catalog": {"status": "OK", "coverage": "EMPTY", "services": []},\n'
        '        "resources": resources,\n'
        '    }\n'
        'def homelab_compute_capabilities():\n'
        '    return {"machines": []}\n'
        'def homelab_owner_snapshot():\n'
        '    return {"status": "OK", "summary": homelab_summary(), "compute": homelab_compute_capabilities()}\n'
        'def homelab_inference_inventory():\n'
        '    if __import__("os").environ.get("HADES_TEST_SOURCE_UNAVAILABLE") == "1":\n'
        '        raise RuntimeError("synthetic source unavailable")\n'
        '    return {"status": "READABLE", "endpoints": [{"source_identity": "inference:provider-a", "node_identity": "netbox:device:7", "status": "READABLE", "loaded_status": "CURRENT", "models": [{"name": "sample:small"}], "loaded_models": [{"name": "sample:small"}]}]}\n'
        'def resolve_inference_node_labels(_inventory):\n'
        '    return {"netbox:device:7": "Compute Node A"}\n'
        'def format_inference_inventory_response(question, _inventory, _summary):\n'
        '    if "20 gb model" in question.casefold():\n'
        '        return "I can\'t determine which GPU has room because live VRAM is unavailable."\n'
        '    if "synthetic node b" in question.casefold():\n'
        '        return "No provider-linked model is recorded for Synthetic Node B."\n'
        '    if "ai thing" in question.casefold() or "ai available" in question.casefold():\n'
        '        return "All 1 configured AI provider checks are responding to catalog reads. I haven\'t tested a generation, so I can\'t confirm the AI can answer a prompt right now."\n'
        '    if "gpu" in question.casefold() or "another model" in question.casefold():\n'
        '        return "I can\'t determine which GPU has room or whether another model will fit. Live telemetry is not connected."\n'
        '    return "sample:small is listed at Compute Node A. Loaded now. A generation request was not made."\n',
        encoding="utf-8",
    )
    capability_matrix = root / "capability-matrix.yaml"
    capability_matrix.write_text(
        "machines:\n"
        "  - name: Compute Node A\n"
        "    address: 192.0.2.69\n"
        "    role: synthetic inference node\n"
        "  - name: Synthetic Node B\n"
        "    role: synthetic specialized inference node\n",
        encoding="utf-8",
    )
    workload_registry = root / "self-service-workloads.json"
    workload_registry.write_text(json.dumps({
        "version": 1,
        "workloads": {
            "synthetic-resource-900": {
                "owner": "synthetic-owner", "node": "test-pve", "vmid": 900,
                "template": "linux-sandbox", "name": "gamma-sandbox",
                "shared_with": ["synthetic-beta"],
            },
        },
    }), encoding="utf-8")
    workload_registry.chmod(0o600)
    script = root / "probe.py"
    script.write_text(child, encoding="utf-8")
    probe_env = os.environ.copy()
    probe_env.pop("PYTHONPATH", None)
    hermes_source = Path(subprocess.check_output(
        [str(interpreter), "-c", "import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)"],
        env=probe_env, text=True,
    ).strip())
    env = {
        key: os.environ[key]
        for key in ("PATH", "LANG", "LC_ALL", "TZ")
        if key in os.environ
    }
    env.update({
        "HOME": str(home),
        "HERMES_HOME": str(hermes_home),
        "PYTHONPATH": f"{overlay_dir}:{repo}:{hermes_source}",
        "HADES_TASK_STATE_FILE": str(root / "tasks.sqlite"),
        "HADES_EPSILON_STATE_FILE": str(root / "epsilon.sqlite"),
        "HADES_HERMES_WORKING_DIRECTORY": str(homelab),
        "HADES_CAPABILITY_MATRIX_FILE": str(capability_matrix),
        "HADES_SELF_SERVICE_REGISTRY_FILE": str(workload_registry),
        "HADES_OWNER_SUBJECT_IDS": "synthetic-owner,synthetic-owner-clean",
        "HADES_TEST_RESULT_KEY_FILE": str(root / "result-query.key"),
    })
    if os.environ.get("HADES_COMPOSED_HOMELAB_ONLY") == "1":
        env["HADES_COMPOSED_HOMELAB_ONLY"] = "1"
    result = subprocess.run(
        [str(interpreter), str(script)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise SystemExit("FAIL Hermes runtime contract\n" + result.stdout + result.stderr[-6000:])
    print(result.stdout.strip())
PY
