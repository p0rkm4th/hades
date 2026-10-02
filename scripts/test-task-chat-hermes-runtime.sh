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
import run_agent
import sitecustomize as hades
import threading
assert hades._HADES_HOMELAB_INTENT.search("What models are available?")
assert hades._HADES_HOMELAB_INTENT.search("Where's qwen3.6:35b?")
assert hades._HADES_HOMELAB_INTENT.search("Which GPUs are free?")
assert hades._HADES_HOMELAB_INTENT.search("Where should I run another model?")
household_model_denial = hades._hades_direct_homelab_read(
    "What models are available?", scope="household",
)
assert "available only in an owner session" in household_model_denial
household_gpu_denial = hades._hades_direct_homelab_read(
    "Which GPUs are free?", scope="household",
)
assert "available only in an owner session" in household_gpu_denial
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
    assert "Live Proxmox currently reports: hades-core." in variant["final_response"], (prompt, variant)
    assert "memory update" not in variant["final_response"].casefold(), (prompt, variant)
    assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

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
hades._hades_phase2_backup_response = lambda *_args, **_kwargs: None
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
assert store.get("task-owner-approval01", owner)["status"] == TaskStatus.AWAITING_APPROVAL.value

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
        '    if __import__("os").environ.get("HADES_TEST_INFERENCE_ONLY") == "1":\n'
        '        raise AssertionError("inference-only query must not read broad homelab summary")\n'
        '    resources = [{"name": "hades-core", "runtime_status": "running",\n'
        '                  "currently_online": True,\n'
        '                  "runtime": {"name": "hades-core", "vmid": 1802, "status": "running",\n'
        '                              "cpu": 0.94, "mem": 32212254720, "maxmem": 34359738368,\n'
        '                              "disk": 85899345920, "maxdisk": 96636764160}}]\n'
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
        '        "availability_summary": ([{"name": "Search latency check", "status": "down", "freshness": "FRESH"},\n'
        '                                  {"name": "Router ping", "status": "up", "freshness": "FRESH", "ping_ms": 84}]\n'
        '                                if __import__("os").environ.get("HADES_TEST_HOMELAB_BOTTLENECK") == "1" else []),\n'
        '        "conflicts": [],\n'
        '        "errors": [],\n'
        '        "resources": resources,\n'
        '    }\n'
        'def homelab_compute_capabilities():\n'
        '    return {"machines": []}\n'
        'def homelab_inference_inventory():\n'
        '    return {"status": "READABLE", "endpoints": [{"source_identity": "inference:provider-a", "node_identity": "netbox:device:7", "status": "READABLE", "loaded_status": "CURRENT", "models": [{"name": "sample:small"}], "loaded_models": [{"name": "sample:small"}]}]}\n'
        'def resolve_inference_node_labels(_inventory):\n'
        '    return {"netbox:device:7": "Compute Node A"}\n'
        'def format_inference_inventory_response(question, _inventory, _summary):\n'
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
        "    role: synthetic inference node\n",
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
