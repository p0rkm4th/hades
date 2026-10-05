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
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
interpreter = Path(sys.argv[2]).absolute()
overlay_dir = Path(os.environ.get("HADES_HERMES_OVERLAY_DIR", str(repo / "hermes"))).resolve()
if not (overlay_dir / "sitecustomize.py").is_file():
    raise SystemExit(f"FAIL HADES overlay directory has no sitecustomize.py: {overlay_dir}")
child = r'''import os
import json
import sys
import run_agent
import sitecustomize as hades
import threading
os.environ["HADES_CORE_PROXMOX_GUEST_NAMES"] = "synthetic-core-node"
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from integrations.task import TaskStatus, TaskStore

# Production reads must go through Hermes' registered MCP handler so the
# server's protected child-process configuration is preserved. This runtime
# contract substitutes only that dispatch boundary with the synthetic adapter.
homelab_dispatch_calls = []
def synthetic_homelab_tool_result(tool_name, arguments=None):
    homelab_dispatch_calls.append(tool_name)
    adapter = Path(os.environ["HADES_HERMES_WORKING_DIRECTORY"]) / "integrations" / "homelab-readonly" / "server.py"
    if str(adapter.parent) not in sys.path:
        sys.path.insert(0, str(adapter.parent))
    spec = __import__("importlib.util", fromlist=["spec_from_file_location"]).spec_from_file_location(
        "synthetic_homelab_registry", adapter
    )
    module = __import__("importlib.util", fromlist=["module_from_spec"]).module_from_spec(spec)
    spec.loader.exec_module(module)
    readers = {
        "homelab_summary": module.homelab_summary,
        "homelab_compute_capabilities": module.homelab_compute_capabilities,
        "homelab_inference_inventory": module.homelab_inference_inventory,
        "homelab_gpu_telemetry": module.homelab_gpu_telemetry,
        "homelab_backup_status": module.homelab_backup_status,
        "homelab_recent_activity": module.homelab_recent_activity,
    }
    return readers[tool_name]()

hades._hades_direct_homelab_tool_result = synthetic_homelab_tool_result

store = TaskStore(os.environ["HADES_TASK_STATE_FILE"])
owner, beta = "synthetic-owner", "synthetic-beta"
store.create(task_id="task-owner-approval01", actor_subject_id=owner, goal="Prepare Friday dinner", status=TaskStatus.AWAITING_APPROVAL)
store.create(task_id="task-beta-failed0001", actor_subject_id=beta, goal="Review Beta's private plan", status=TaskStatus.FAILED)
agent_class = run_agent.AIAgent
assert getattr(agent_class.run_conversation, "__name__", "") == "_hades_run_conversation", "HADES hook did not patch the Hermes agent runtime"
assert hades._hades_is_homelab_intent("Which models are available?"), "inference catalog question missed the live homelab route"
assert hades._hades_is_homelab_intent("Where should I run another model?"), "model placement question missed the live homelab route"
assert hades._hades_is_homelab_intent("What changed since yesterday?"), "recent activity question missed the live homelab route"
node_followup_history = [
    {"role": "user", "content": "What is wrong with deep-inference-node?"},
    {"role": "assistant", "content": "I checked the current inference host."},
]
assert hades._hades_homelab_inference_followup_prompt(
    "What about specialized-inference-node?", "owner", node_followup_history,
) == "What is specialized-inference-node doing right now?"
placement_followup_history = [
    {"role": "user", "content": "Which one has more room?"},
    {"role": "assistant", "content": "Responding inference endpoints: A; the largest free-memory reading was 8000 MiB."},
]
assert hades._hades_homelab_inference_followup_prompt(
    "Could I put another model there?", "owner", placement_followup_history,
) == "Where should I run another model?"
assert hades._hades_homelab_inference_followup_prompt(
    "What about a 20 GB one?", "owner", placement_followup_history,
) == "Can a 20 GB model fit?"
assert hades._hades_homelab_inference_followup_prompt(
    "What about specialized-inference-node?", "household", node_followup_history,
) == "What about specialized-inference-node?"
proxmox_backup_answer = hades._hades_direct_proxmox_backup_status(
    "What is the Proxmox backup status?", owner, "owner"
)
assert "synthetic Proxmox backup report" in proxmox_backup_answer, proxmox_backup_answer
household_backup_denial = hades._hades_direct_proxmox_backup_status(
    "What is the Proxmox backup status?", beta, "household"
)
assert "can't check infrastructure backup details" in household_backup_denial
unverified_backup_denial = hades._hades_direct_proxmox_backup_status(
    "What is the Proxmox backup status?", "", "denied"
)
assert "couldn't verify this HADES session" in unverified_backup_denial
activity_answer = hades._hades_direct_homelab_recent_activity(
    "What changed since yesterday?", owner, "owner"
)
assert "synthetic recent homelab activity" in activity_answer, activity_answer
assert hades._hades_direct_homelab_recent_activity(
    "What changed since yesterday?", beta, "household"
) is None
model_location_answer = hades._hades_direct_homelab_inference_read(
    "Where's model-a:8b?", owner, "owner"
)
assert model_location_answer.startswith("model-a:8b is listed by Compute Alpha"), model_location_answer
model_fit_answer = hades._hades_direct_homelab_inference_read(
    "Can this handle a 20 GB model?", owner, "owner"
)
assert "Current point-in-time GPU readings" in model_fit_answer, model_fit_answer
assert "8000 MiB free" in model_fit_answer and "not a fit guarantee" in model_fit_answer, model_fit_answer
working_homelab_reader = hades._hades_direct_homelab_tool_result
hades._hades_direct_homelab_tool_result = lambda *_args, **_kwargs: {
    "status": "NOT_CONFIGURED",
    "errors": ["The configured read-only homelab tool is unavailable."],
}
assert hades._hades_direct_homelab_inference_read(
    "Can this handle a 20 GB model?", owner, "owner"
) is None
hades._hades_direct_homelab_tool_result = working_homelab_reader
assert hades._hades_direct_homelab_inference_read(
    "Where's model-a:8b?", beta, "household"
) is None
assert hades._hades_direct_proxmox_backup_status(
    "Restore that Proxmox backup", owner, "owner"
) is None
assert hades._hades_phase2_backup_freshness_response(
    "What is the Proxmox backup status?", owner, "owner"
) is None
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
saved_finance_guidance = hades._hades_direct_finance_guidance
saved_phase2_backup = hades._hades_phase2_backup_response
hades._hades_direct_finance_guidance = lambda *_args, **_kwargs: None
hades._hades_phase2_backup_response = lambda *_args, **_kwargs: None
model_location_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-model-location",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
model_location = model_location_agent.run_conversation(
    "Where's model-a:8b?", conversation_history=[]
)
assert model_location.get("completed") is True and model_location.get("api_calls") == 0, model_location
assert model_location["final_response"].startswith("model-a:8b is listed by Compute Alpha"), model_location
hades._hades_direct_finance_guidance = saved_finance_guidance
hades._hades_phase2_backup_response = saved_phase2_backup
backup_dispatch_count = len(homelab_dispatch_calls)
household_backup_agent = agent_class(
    gateway_session_key=f"hades-user-{beta}", session_id="synthetic-household-proxmox-backup",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
household_backup_result = household_backup_agent.run_conversation(
    "Are the Proxmox backups okay?", conversation_history=[]
)
assert household_backup_result.get("completed") is True, household_backup_result
assert household_backup_result.get("api_calls") == 0, household_backup_result
assert len(homelab_dispatch_calls) == backup_dispatch_count, homelab_dispatch_calls
assert "household chat" in household_backup_result["final_response"].casefold()
assert "owner" in household_backup_result["final_response"].casefold()
for private_marker in ("nightly", "guest 102", "hypervisor-alpha", "synthetic Proxmox"):
    assert private_marker not in household_backup_result["final_response"], household_backup_result
unverified_backup_dispatch_count = len(homelab_dispatch_calls)
unverified_backup_agent = agent_class(
    gateway_session_key="hades-user-", session_id="synthetic-unverified-proxmox-backup",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
unverified_backup_result = unverified_backup_agent.run_conversation(
    "Are the Proxmox backups okay?", conversation_history=[]
)
assert unverified_backup_result.get("completed") is True, unverified_backup_result
assert unverified_backup_result.get("api_calls") == 0, unverified_backup_result
assert len(homelab_dispatch_calls) == unverified_backup_dispatch_count, homelab_dispatch_calls
assert "couldn't verify this HADES session" in unverified_backup_result["final_response"]
for private_marker in ("nightly", "guest 102", "hypervisor-alpha", "synthetic Proxmox"):
    assert private_marker not in unverified_backup_result["final_response"], unverified_backup_result
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
assert "Prepare Friday dinner is waiting for your approval." in results[owner]["final_response"]
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
owner_server_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-server-overview",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
server_overview = owner_server_agent.run_conversation(
    "Is everything okay with the servers?", conversation_history=[]
)
assert server_overview.get("completed") is True and server_overview.get("api_calls") == 0, server_overview
assert "Live Proxmox currently reports: synthetic-core-node." in server_overview["final_response"], server_overview
assert "memory update" not in server_overview["final_response"].casefold(), server_overview
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

# Ordinary status wording should stay on the same deterministic, read-only
# route even when it says "doing" or "computers" instead of "server status".
# The configured model endpoint is deliberately unavailable, so any fallthrough
# to inference fails this contract instead of returning a fabricated answer.
for index, prompt in enumerate((
    "How are the servers doing?",
    "Are all the computers okay?",
)):
    variant_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}",
        session_id=f"synthetic-server-overview-variant-{index}",
        stream_delta_callback=lambda _chunk: None,
        **kwargs,
    )
    variant = variant_agent.run_conversation(prompt, conversation_history=[])
    assert variant.get("completed") is True and variant.get("api_calls") == 0, (prompt, variant)
    assert "Live Proxmox currently reports: synthetic-core-node." in variant["final_response"], (prompt, variant)
    assert "memory update" not in variant["final_response"].casefold(), (prompt, variant)
    assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

down_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-what-is-down",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
down_answer = down_agent.run_conversation("What's down?", conversation_history=[])
assert down_answer.get("completed") is True and down_answer.get("api_calls") == 0, down_answer
assert "No fresh configured probe is reporting a failure" in down_answer["final_response"], down_answer
assert "unmonitored services remain unknown" in down_answer["final_response"], down_answer
provenance_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-provenance",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
provenance_history = [
    {"role": "user", "content": "What's down?"},
    {"role": "assistant", "content": down_answer["final_response"]},
    {"role": "user", "content": "How do you know that?"},
]
provenance_answer = provenance_agent.run_conversation(
    "How do you know that?", conversation_history=provenance_history
)
assert provenance_answer.get("completed") is True and provenance_answer.get("api_calls") == 0, provenance_answer
assert "Synthetic Proxmox: readable" in provenance_answer["final_response"], provenance_answer
conflict_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-conflicts",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
conflict_answer = conflict_agent.run_conversation(
    "Do any sources disagree?", conversation_history=[]
)
assert conflict_answer.get("completed") is True and conflict_answer.get("api_calls") == 0, conflict_answer
assert "I can't confirm whether the sources disagree" in conflict_answer["final_response"], conflict_answer
assert "Proxmox guest visibility is partial or unknown" in conflict_answer["final_response"], conflict_answer
assert "does not establish that the sources agree" in conflict_answer["final_response"], conflict_answer
visibility_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-guest-visibility",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
visibility_answer = visibility_agent.run_conversation(
    "Are all VMs visible?", conversation_history=[]
)
assert visibility_answer.get("completed") is True and visibility_answer.get("api_calls") == 0, visibility_answer
assert "selected guests only" in visibility_answer["final_response"], visibility_answer
placement_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-service-placement",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
placement_answer = placement_agent.run_conversation(
    "Where is NetBox running?", conversation_history=[]
)
assert placement_answer.get("completed") is True and placement_answer.get("api_calls") == 0, placement_answer
assert "application-service catalog is reachable but empty" in placement_answer["final_response"], placement_answer
assert "remembered location" in placement_answer["final_response"], placement_answer
ranking_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-resource-ranking",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
ranking_answer = ranking_agent.run_conversation(
    "What's the most loaded server?", conversation_history=[]
)
assert ranking_answer.get("completed") is True and ranking_answer.get("api_calls") == 0, ranking_answer
assert "synthetic-core-node at 94.0%" in ranking_answer["final_response"], ranking_answer
assert "host and guest readings are separate" in ranking_answer["final_response"], ranking_answer

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
    return "Live Proxmox reports synthetic-synthetic-core-node running."
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
assert "SERVER STATUS:" in compound_status["final_response"] and "synthetic-synthetic-core-node running" in compound_status["final_response"], compound_status
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
assert "Live Proxmox currently reports: synthetic-core-node." in actual_compound_status["final_response"], actual_compound_status
assert "No Backup Check exists yet." in actual_compound_status["final_response"], actual_compound_status
hades._hades_phase2_backup_response = lambda *_args, **_kwargs: None
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

# A speech-like named-node question must not be sent to inference or turn a
# static hardware inventory row into a live online/runtime claim.
deep_node_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-deep-inference-node-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
deep_node_status = deep_node_agent.run_conversation(
    "whats deep-inference-node doing rn", conversation_history=[]
)
assert deep_node_status.get("completed") is True and deep_node_status.get("api_calls") == 0, deep_node_status
deep_node_text = deep_node_status["final_response"]
assert "I found deep-inference-node in the hardware inventory." in deep_node_text, deep_node_text
assert "The recorded address is 192.0.2.69." in deep_node_text, deep_node_text
assert "It is listed as synthetic inference node." in deep_node_text, deep_node_text
assert "I don't have a current runtime check for it" in deep_node_text, deep_node_text
assert "I can't say whether it's online." in deep_node_text, deep_node_text
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

placement_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-model-placement",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
placement = placement_agent.run_conversation(
    "Which machine should host another AI model?", conversation_history=[]
)
assert placement.get("completed") is True and placement.get("api_calls") == 0, placement
assert "can't recommend a host yet" in placement["final_response"], placement
assert "I haven't deployed or changed anything." in placement["final_response"], placement
assert "deep-inference-node" not in placement["final_response"]
assert "specialized-inference-node" not in placement["final_response"]

household_named_node_agent = agent_class(
    gateway_session_key=f"hades-user-{beta}", session_id="synthetic-household-named-node",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
household_named_node = household_named_node_agent.run_conversation(
    "Is deep-inference-node okay?", conversation_history=[]
)
assert household_named_node.get("completed") is True and household_named_node.get("api_calls") == 0, household_named_node
assert "deep-inference-node" not in household_named_node["final_response"]
assert "can't verify" in household_named_node["final_response"].casefold()

# A physical host may be visible to Kuma without a Proxmox runtime row. Its
# fresh probe is useful reachability evidence, but must not be relabeled as a
# Proxmox status or as proof of workload health.
os.environ["HADES_TEST_HOMELAB_deep_node_MONITOR"] = "1"
deep_node_monitor_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-deep-inference-node-monitor-status",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
deep_node_monitor_status = deep_node_monitor_agent.run_conversation(
    "whats deep-inference-node doing rn", conversation_history=[]
)
assert deep_node_monitor_status.get("completed") is True and deep_node_monitor_status.get("api_calls") == 0, deep_node_monitor_status
deep_node_monitor_text = deep_node_monitor_status["final_response"]
assert "the deep-inference-node SSH check is responding (fresh observation)" in deep_node_monitor_text, deep_node_monitor_text
assert "current host workload or operating-system status" in deep_node_monitor_text, deep_node_monitor_text
assert "Proxmox runtime status is NOT_OBSERVED" not in deep_node_monitor_text, deep_node_monitor_text
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
for status, freshness, expected in (
    ("down", "FRESH", "the deep-inference-node SSH check is failing (fresh observation)"),
    ("up", "STALE", "the deep-inference-node SSH check last reported up, but that observation is stale"),
):
    os.environ["HADES_TEST_deep_node_MONITOR_STATUS"] = status
    os.environ["HADES_TEST_deep_node_MONITOR_FRESHNESS"] = freshness
    monitor_agent = agent_class(
        gateway_session_key=f"hades-user-{owner}", session_id=f"synthetic-deep-inference-node-monitor-{status}-{freshness}",
        stream_delta_callback=lambda _chunk: None, **kwargs,
    )
    monitor_result = monitor_agent.run_conversation("whats deep-inference-node doing rn", conversation_history=[])
    assert monitor_result.get("completed") is True and monitor_result.get("api_calls") == 0, monitor_result
    assert expected in monitor_result["final_response"], monitor_result
    assert "Proxmox runtime status is NOT_OBSERVED" not in monitor_result["final_response"], monitor_result
    assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
del os.environ["HADES_TEST_deep_node_MONITOR_STATUS"]
del os.environ["HADES_TEST_deep_node_MONITOR_FRESHNESS"]
del os.environ["HADES_TEST_HOMELAB_deep_node_MONITOR"]

blockers_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-homelab-blockers",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
blocker_summary = blockers_agent.run_conversation(
    "Are there any blockers in the homelab?", conversation_history=[]
)
assert blocker_summary.get("completed") is True and blocker_summary.get("api_calls") == 0, blocker_summary
assert "Live Proxmox currently reports: synthetic-core-node." in blocker_summary["final_response"], blocker_summary
assert "No blocker was reported by the configured live sources." in blocker_summary["final_response"], blocker_summary
assert "HADES Core runtime is running." in blocker_summary["final_response"], blocker_summary

# A normal-language performance complaint must combine live resource and
# service-probe evidence while clearly stating that neither proves a network
# bottleneck. The model endpoint is unavailable and must not be consulted.
os.environ["HADES_TEST_HOMELAB_BOTTLENECK"] = "1"
network_agent = agent_class(
    gateway_session_key=f"hades-user-{owner}", session_id="synthetic-network-diagnosis",
    stream_delta_callback=lambda _chunk: None, **kwargs,
)
network_diagnosis = network_agent.run_conversation(
    "Something feels slow on the network; check node status, network health, recent resource usage, and services, then tell me what looks abnormal.",
    conversation_history=[],
)
assert network_diagnosis.get("completed") is True and network_diagnosis.get("api_calls") == 0, network_diagnosis
network_text = network_diagnosis["final_response"]
assert "Live Proxmox currently reports: synthetic-core-node." in network_text, network_text
assert "CPU 94.0%" in network_text, network_text
assert "Uptime Kuma's configured probes failed: Search latency check." in network_text, network_text
assert "Fresh configured-probe response-time samples: Router ping: 84 ms." in network_text, network_text
assert "Packet-loss, throughput, and historical comparison data are unavailable" in network_text, network_text
assert "cannot identify a network bottleneck or trend from this evidence" in network_text, network_text
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value
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
print("PASS household Proxmox backup questions receive a generic owner-session boundary without MCP or model calls")
print("PASS speech-like named-node status separates deep-inference-node's hardware listing from missing live runtime evidence")
print("PASS physical-node wording uses a fresh monitor as reachability evidence without relabeling it as Proxmox runtime or workload health")
print("PASS detailed homelab blocker summary remains deterministic when optional availability has no rows")
print("PASS network-slowness question combines synthetic Proxmox and Kuma evidence, states missing network trends, and makes zero model calls")
print("PASS ambiguous household entertainment-device trouble gets a plain-language clarification for owner and household without task changes or model calls")
print("PASS Proxmox backup status uses the owner-only live source, skips repository-check fallback, and rejects restore actions")
print("PASS recent homelab activity uses bounded live sources, has natural intent routing, and remains owner-only")
print("PASS model-location owner route resolves stable host identity without exposing details to household")
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
        (
        'def homelab_summary():\n'
        '    resources = [{"name": "synthetic-core-node", "runtime_status": "running",\n'
        '                  "currently_online": True,\n'
        '                  "identity": {"canonical_id": "netbox:device:42"},\n'
        '                  "inventory": {"name": "Compute Alpha", "role": "inference"},\n'
        '                  "runtime": {"name": "synthetic-core-node", "vmid": 202, "status": "running",\n'
        '                              "cpu": 0.94, "mem": 32212254720, "maxmem": 34359738368,\n'
        '                              "disk": 85899345920, "maxdisk": 96636764160}}]\n'
        '    if __import__("os").environ.get("HADES_TEST_HOMELAB_deep_node_MONITOR") == "1":\n'
        '        resources.append({"name": "deep-inference-node SSH", "runtime_status": "NOT_OBSERVED",\n'
        '                          "currently_online": False, "inventory": None,\n'
        '                          "availability": {"name": "deep-inference-node SSH",\n'
        '                                           "status": __import__("os").environ.get("HADES_TEST_deep_node_MONITOR_STATUS", "up"),\n'
        '                                           "last_updated": "2026-09-27T00:00:00Z"},\n'
        '                          "availability_freshness": __import__("os").environ.get("HADES_TEST_deep_node_MONITOR_FRESHNESS", "FRESH"),\n'
        '                          "conflicts": []})\n'
        '    return {\n'
        '        "status": "OK",\n'
        '        "online_names": ["synthetic-core-node"],\n'
        '        "inventory_only_names": [],\n'
        '        "availability_summary": ([{"name": "Search latency check", "status": "down", "freshness": "FRESH"},\n'
        '                                  {"name": "Router ping", "status": "up", "freshness": "FRESH", "ping_ms": 84}]\n'
        '                                if __import__("os").environ.get("HADES_TEST_HOMELAB_BOTTLENECK") == "1" else []),\n'
        '        "conflicts": [],\n'
        '        "proxmox_guest_visibility": {"status": "PARTIAL", "scope": "SELECTED_GUESTS"},\n'
        '        "service_catalog": {"status": "OK", "coverage": "EMPTY", "services": []},\n'
        '        "source_observations": [{"source": "Synthetic Proxmox", "status": "READABLE", "retrieved_at": "synthetic-freshness-time"}],\n'
        '        "errors": [],\n'
        '        "resources": resources,\n'
        '    }\n'
        'def homelab_compute_capabilities():\n'
        '    return {"machines": []}\n'
        'def homelab_backup_status():\n'
        '    return {"status": "READABLE"}\n'
        'def format_homelab_backup_status(_report):\n'
        '    return "synthetic Proxmox backup report with restore limits"\n'
        'def homelab_recent_activity(_window_hours=24):\n'
        '    return {"status": "READABLE"}\n'
        'def format_homelab_recent_activity(_report):\n'
        '    return "synthetic recent homelab activity with bounded history"\n'
        'def homelab_inference_inventory():\n'
        '    return {"status": "READABLE", "endpoints": [{"id": "fast-lane", "source_identity": "inference:fast-lane", "node_identity": "netbox:device:42", "identity_status": "LINKED", "status": "READABLE", "models": [{"name": "model-a:8b"}], "loaded_status": "CURRENT", "loaded_models": [{"name": "model-a:8b"}]}]}\n'
        'def homelab_gpu_telemetry():\n'
        '    return {"status": "READABLE", "retrieved_at": "2026-10-04T12:00:00Z", "endpoints": [{"inference_id": "fast-lane", "status": "READABLE", "devices": [{"index": 0, "memory_free_mib": 8000, "memory_total_mib": 16000, "gpu_utilization_percent": 25}]}]}\n'
        'def format_inference_inventory_response(text, _inventory, summary, _gpu=None):\n'
        '    if "deep-inference-node" in text:\n'
        '        return "I found deep-inference-node in the hardware inventory. The recorded address is 192.0.2.69. It is listed as synthetic inference node. I don\'t have a current runtime check for it, so I can\'t say whether it\'s online."\n'
        '    if "20 gb model" in text.lower():\n'
        '        free = _gpu["endpoints"][0]["devices"][0]["memory_free_mib"]\n'
        '        return "Current point-in-time GPU readings: " + str(free) + " MiB free; a sample is not a fit guarantee."\n'
        '    name = summary["resources"][0]["inventory"]["name"]\n'
        '    return "model-a:8b is listed by " + name + ". Stable link verified; generation not tested."\n'
        ),
        encoding="utf-8",
    )
    capability_matrix = root / "capability-matrix.yaml"
    capability_matrix.write_text(
        "machines:\n"
        "  - name: deep-inference-node\n"
        "    address: 192.0.2.69\n"
        "    role: synthetic inference node\n"
        "  - name: specialized-inference-node\n"
        "    role: synthetic specialized inference node\n",
        encoding="utf-8",
    )
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
        "HADES_OWNER_SUBJECT_IDS": "synthetic-owner,synthetic-owner-clean",
        "HADES_TEST_RESULT_KEY_FILE": str(root / "result-query.key"),
    })
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
