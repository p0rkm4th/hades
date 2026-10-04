#!/usr/bin/env python3
"""Exercise service-health answers against authoritative monitor evidence."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import re
import sys
import tempfile
import time
import types
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source_path = Path(os.environ.get(
    'HADES_SITE_CUSTOMIZE_SOURCE', 'hermes/sitecustomize.py',
)).resolve()
default_source_path = (ROOT / 'hermes/sitecustomize.py').resolve()
source = source_path.read_text(encoding='utf-8')
tree = ast.parse(source)
wanted = {
    '_hades_service_health_target', '_hades_service_monitor_response',
    '_hades_household_safe_status_response',
    '_hades_homelab_availability_groups', '_hades_direct_homelab_read',
    '_hades_resolve_homelab_adapter_path',
    '_hades_direct_homelab_tool_result',
    '_hades_homelab_recent_activity_response',
    '_hades_homelab_workloads_on_host_response',
    '_hades_homelab_all_proxmox_guests_response',
    '_hades_homelab_workload_host_target',
    '_hades_homelab_core_vm_placement_response',
    '_hades_endpoint_intent_before_provision',
    '_hades_service_endpoint_response',
    '_hades_service_placement_intent',
    '_hades_agent_zero_runtime_placement_response',
    '_hades_managed_server_status_intent',
    '_hades_service_placement_response',
    '_hades_endpoint_continuation_response',
    '_hades_direct_owner_location',
    '_hades_direct_proxmox_backup_read',
    '_hades_homelab_name_key',
    '_hades_homelab_display_label',
    '_hades_homelab_named_machine_records',
    '_hades_homelab_target_from_question',
    '_hades_homelab_named_check_target',
    '_hades_homelab_followup_prompt',
    '_hades_homelab_service_coverage_intent',
    '_hades_homelab_service_coverage_response',
    '_hades_homelab_explicit_model_fit_intent',
    '_hades_homelab_named_node_capacity_target',
    '_hades_homelab_live_capacity_winner',
    '_hades_homelab_explicit_model_fit_response',
    '_hades_homelab_network_diagnostic_response',
    '_hades_homelab_source_identity_intent',
    '_hades_homelab_guest_visibility_intent',
    '_hades_redact_household_sensitive_history',
    '_hades_household_sensitive_context_followup',
    '_hades_homelab_conflict_intent',
    '_hades_homelab_conflict_response',
    '_hades_homelab_unlinked_identity_response',
    '_hades_broad_homelab_status_intent',
    '_hades_homelab_resource_ranking_intent',
    '_hades_homelab_resource_ranking_response',
    '_hades_homelab_gpu_execution_intent',
    '_hades_homelab_gpu_hardware_target_intent',
    '_hades_household_game_health_intent',
    '_hades_homelab_provenance_followup',
    '_hades_homelab_guest_visibility_provenance_intent',
    '_hades_homelab_guest_visibility_provenance_response',
    '_hades_positive_homelab_control_request',
}
functions = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in wanted
]
assert {node.name for node in functions} == wanted
debug_logs = []
info_logs = []
def record_warning(*args, **_kwargs):
    error = sys.exc_info()[1]
    debug_logs.append((*args, repr(error) if error else None))

namespace = {
    'json': __import__('json'),
    're': re,
    'os': os,
    'Path': Path,
    'datetime': datetime,
    '_hades_live_proxmox_vm_rows': lambda: [],
    '_hades_phase2_backup_freshness_response': lambda *_args, **_kwargs: None,
    '_HADES_EXPLICIT_PUBLIC_RESEARCH_INTENT': re.compile(r'(?!)'),
    'importlib': importlib,
    'sys': sys,
    'time': time,
    '_hades_logger': type('Log', (), {
        'warning': staticmethod(record_warning),
        'info': staticmethod(lambda *args, **_kwargs: info_logs.append(args)),
    })(),
    '_hades_phase2_backup_response': lambda *_args, **_kwargs: 'Configured HADES backup checks: current.',
    '_HADES_HOUSEHOLD_PRIVATE_HISTORY_MARKER': '[Private infrastructure conversation omitted for household safety.]',
}


class FakeHomelabRegistry:
    def __init__(self):
        self.calls = []

    def get_entry(self, name):
        return object() if name.startswith('mcp__homelab_readonly__') else None

    def dispatch(self, name, arguments):
        self.calls.append((name, arguments))
        adapter = (
            Path(os.environ['HADES_HERMES_WORKING_DIRECTORY'])
            / 'integrations' / 'homelab-readonly' / 'server.py'
        )
        spec = importlib.util.spec_from_file_location('synthetic_homelab_mcp', adapter)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tool = name.rsplit('__', 1)[-1]
        if tool == 'homelab_summary' and os.environ.get('HADES_TEST_PROXMOX_ACTIVITY') == '1':
            summary = {
                'status': 'PARTIAL', 'resources': [], 'sources': [],
                'source_counts': {}, 'availability_summary': [], 'conflicts': [],
                'online_names': [], 'inventory_names': [], 'errors': [],
            }
            return __import__('json').dumps({'result': __import__('json').dumps(summary)})
        if tool == 'homelab_recent_activity' and os.environ.get('HADES_TEST_PROXMOX_ACTIVITY') == '1':
            report = {
                'status': 'PARTIAL',
                'source_status': {'proxmox': 'PARTIAL', 'netbox': 'READABLE'},
                'retrieved_at': '2026-10-02T12:00:00+00:00',
                'window_hours': arguments.get('window_hours', 24),
                'endpoints': [{
                    'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS',
                    'events': [{
                        'guest_id': '12802', 'node': 'synthetic-pve',
                        'task_type': 'qmstart', 'status': 'OK',
                        'starttime': 1790942400, 'endtime': 1790946000,
                    }],
                }],
                'netbox': {
                    'status': 'READABLE', 'retrieved_at': '2026-10-02T12:00:01+00:00',
                    'objects': [{
                        'object_type': 'device', 'object_id': '17',
                        'name': 'synthetic-router', 'last_updated': '2026-10-02T11:50:00+00:00',
                    }],
                },
            }
            return __import__('json').dumps({'result': __import__('json').dumps(report)})
        if tool == 'homelab_recent_activity':
            assert arguments in ({'window_hours': 24}, {'window_hours': 168})
        else:
            assert arguments == {}
        call = getattr(module, tool, None)
        if not callable(call):
            return __import__('json').dumps({'error': 'synthetic tool is unavailable'})
        result = call(arguments.get('window_hours', 24)) if tool == 'homelab_recent_activity' else call()
        return __import__('json').dumps({'result': __import__('json').dumps(result)})


tools_module = types.ModuleType('tools')
tools_module.__path__ = []
registry_module = types.ModuleType('tools.registry')
registry_module.registry = FakeHomelabRegistry()
sys.modules['tools'] = tools_module
sys.modules['tools.registry'] = registry_module
exec(compile(ast.Module(body=functions, type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
namespace['_hades_agent_zero_available'] = lambda: True
run_conversation = next((
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == '_hades_run_conversation'
), None)
if run_conversation is not None:
    household_intent_assignment = next((
        node for node in run_conversation.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == '_household_homelab_boundary_intent'
            for target in node.targets
        )
    ), None)
else:
    household_intent_assignment = None
if household_intent_assignment is not None:
    household_boundary_expression = ast.unparse(household_intent_assignment.value)
    assert '_hades_broad_homelab_status_intent(user_message)' in household_boundary_expression
    assert '_hades_homelab_guest_visibility_intent(user_message)' in household_boundary_expression
    assert '_hades_household_sensitive_context_followup(user_message, _hades_history, _hades_intent_text)' in household_boundary_expression
    assert '_hades_household_game_health_intent(user_message, self._hades_session_scope)' in household_boundary_expression
    assert '_hades_service_health_target(user_message)' in household_boundary_expression
    assert 'self._hades_session_scope' in household_boundary_expression
    assert 'household' in household_boundary_expression
else:
    # Focused composed overlays omit upstream conversation internals. Their
    # household routing and redaction are exercised by the Hermes runtime test.
    assert os.environ.get('HADES_SITE_CUSTOMIZE_SOURCE')
intent_assignment = next(
    node for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == '_HADES_HOMELAB_INTENT' for target in node.targets)
)
exec(compile(ast.Module(body=[intent_assignment], type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
homelab_intent = namespace['_HADES_HOMELAB_INTENT']
status_intent = namespace['_hades_broad_homelab_status_intent']
guest_visibility_intent = namespace['_hades_homelab_guest_visibility_intent']
household_sensitive_followup = namespace['_hades_household_sensitive_context_followup']
redact_household_history = namespace['_hades_redact_household_sensitive_history']
game_health_intent = namespace['_hades_household_game_health_intent']
for prompt in (
    'Which Proxmox guests can you verify right now, and what are their current states?',
    'What VMs and containers are running?',
    'Show me the current guest visibility.',
):
    assert guest_visibility_intent(prompt), prompt
assert not guest_visibility_intent('What is Proxmox?')
leaked_household_history = [
    {'role': 'user', 'content': 'Which Proxmox guests can you verify?'} ,
    {'role': 'assistant', 'content': 'The approved node is synthetic-node; template name synthetic-template; http://198.51.100.1.'},
    {'role': 'user', 'content': 'Tell me a joke.'},
]
assert household_sensitive_followup('Can you remind me of the template?', leaked_household_history)
safe_household_history, did_redact = redact_household_history(leaked_household_history)
assert did_redact
assert 'synthetic-node' not in repr(safe_household_history)
assert 'synthetic-template' not in repr(safe_household_history)
assert '198.51.100.1' not in repr(safe_household_history)
assert '[Private infrastructure conversation omitted for household safety.]' in repr(safe_household_history)
assert leaked_household_history[0]['content'] == 'Which Proxmox guests can you verify?'
opaque_private_history, opaque_private_redacted = redact_household_history([
    {'role': 'user', 'content': 'What is the current state of Proxmox guests?'},
    {'role': 'assistant', 'content': 'Synthetic node Compute Node A is online.'},
    {'role': 'tool', 'content': '{"host":"Synthetic Node A","vmid":802}'},
])
assert opaque_private_redacted
assert 'Compute Node A' not in repr(opaque_private_history)
assert 'Synthetic Node A' not in repr(opaque_private_history)
assert 'vmid' not in repr(opaque_private_history)
assert not redact_household_history([
    {'role': 'assistant', 'content': 'All approved AI service checks responded; generation was not tested.'},
])[1]
assert not household_sensitive_followup(
    'Can you remind me what was checked?',
    [{'role': 'assistant', 'content': 'All approved AI service checks responded; generation was not tested.'}],
)
for prompt in (
    'Is everything okay?', 'What is down?', 'What is down or degraded right now, and what can you not verify?',
    'Anything dying?', "What's fucked?",
    'Which computer is having trouble?', "Why's shit slow?", 'What changed since yesterday?',
    'Are all the computers okay?', 'Is the homelab okay?', 'Are my computers okay?',
    'Is Minecraft working?', 'Is the game server working?',
    'Where is HADES running?', 'Where is Minecraft running?',
):
    assert homelab_intent.search(prompt), f'owner homelab health intent missed {prompt!r}'
for prompt in (
    'Is everything okay?', 'Is everything okay with the homelab?',
    'Is everything okay with my homelab?', 'Is everything okay with our homelab?',
    'Is everything okay with the homelab right now?', 'Is everything okay right now?',
    'Are all the computers okay?', 'Anything dying?', "Why's everything slow?",
    'Why does the network feel slow?', 'Why does Wi-Fi feel slow?',
    'Which live homelab observations cannot you confidently match to the same machine?',
    'Which source records are still unlinked?',
    'Which homelab services can you not verify right now?',
    'Which services can you not verify right now?',
    'Are any homelab sources contradicting each other right now?',
    'Do NetBox, Proxmox, and Uptime Kuma disagree about any server right now? Show conflicts only, and distinguish intended state from live runtime and probe state.',
    'What is down or degraded right now, and what can you not verify?',
):
    assert status_intent(prompt), f'broad homelab status intent missed {prompt!r}'
source_identity_intent = namespace['_hades_homelab_source_identity_intent']
conflict_intent = namespace['_hades_homelab_conflict_intent']
assert source_identity_intent('Which source records are still unlinked?')
assert conflict_intent('Are any homelab sources contradicting each other right now?')
assert conflict_intent('Do NetBox, Proxmox, and Uptime Kuma disagree about any server right now? Show conflicts only, and distinguish intended state from live runtime and probe state.')
assert namespace['_hades_homelab_service_coverage_intent'](
    'Which services can you not verify right now?'
)
conflict_response = namespace['_hades_homelab_conflict_response']({
    'status': 'PARTIAL',
    'retrieved_at': '2026-10-03T12:00:00+00:00',
    'sources': [{'source': 'Proxmox', 'status': 'OK'}, {'source': 'NetBox', 'status': 'UNAVAILABLE'}],
    'conflicts': [{
        'name': 'Synthetic Node A',
        'reasons': ['NetBox intended node differs from Proxmox runtime node'],
    }],
    'source_counts': {'identity_unlinked_resources': 2},
    'proxmox_guest_visibility': {'status': 'PARTIAL'},
})
assert 'Synthetic Node A' in conflict_response and 'differs from Proxmox runtime node' in conflict_response
assert 'coverage is incomplete' in conflict_response.casefold() and 'not a lab-wide agreement or all-clear' in conflict_response
assert '2 Proxmox or Uptime Kuma records' in conflict_response
no_conflict_response = namespace['_hades_homelab_conflict_response']({
    'status': 'PARTIAL', 'conflicts': [], 'sources': [],
    'proxmox_guest_visibility': {'status': 'PARTIAL'}, 'source_counts': {},
})
assert 'No conflicts were reported among the homelab records compared in this read' in no_conflict_response
assert 'not a lab-wide agreement or all-clear' in no_conflict_response
assert game_health_intent('Is the game server working?', 'household')
assert game_health_intent('Is Minecraft working?', 'household')
assert not game_health_intent('Is the game server working?', 'owner')
provenance_followup = namespace['_hades_homelab_provenance_followup']
assert provenance_followup('How do you know that?', 'Is everything okay with the homelab?')
assert not provenance_followup('How do you know that?', '')
guest_scope_question = (
    'How do you know what Proxmox guests you can see, and is that all guests or only a selection?'
)
guest_scope_intent = namespace['_hades_homelab_guest_visibility_provenance_intent']
guest_scope_response = namespace['_hades_homelab_guest_visibility_provenance_response']
assert guest_scope_intent(guest_scope_question)
assert not guest_scope_intent('Which guests are online?')
selected_scope = guest_scope_response({
    'proxmox_guest_visibility': {
        'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS',
        'endpoints': [{'status': 'DEGRADED', 'scope': 'SELECTED_GUESTS'}],
    },
    'sources': [{
        'source': 'Proxmox guest visibility (synthetic)', 'status': 'DEGRADED',
        'retrieved_at': '2026-10-03T23:44:14+00:00',
    }],
})
assert 'selected guests only' in selected_scope and 'effective-permission data' in selected_scope
assert '2026-10-03T23:44:14+00:00' in selected_scope
all_guest_scope = guest_scope_response({
    'proxmox_guest_visibility': {'status': 'COMPLETE', 'scope': 'ALL_GUESTS'},
    'sources': [],
})
assert 'all guests' in all_guest_scope and 'every configured Proxmox source' in all_guest_scope
mixed_guest_scope = guest_scope_response({
    'proxmox_guest_visibility': {'status': 'PARTIAL', 'scope': 'MIXED'},
    'sources': [],
})
assert 'mixed or incomplete' in mixed_guest_scope
unknown_guest_scope = guest_scope_response({
    'proxmox_guest_visibility': {'status': 'UNKNOWN', 'scope': 'UNKNOWN'},
    'sources': [],
})
assert 'could not verify effective Proxmox guest permissions' in unknown_guest_scope
target = namespace['_hades_service_health_target']
answer = namespace['_hades_service_monitor_response']
household_safe_status = namespace['_hades_household_safe_status_response']
assert 'I can\'t diagnose why everything is slow' in household_safe_status('Why is everything slow?')
assert 'I can\'t diagnose whole-home network speed' in household_safe_status('Why is Wi-Fi slow?')
assert 'I can\'t check all the home computers' in household_safe_status('Are all the computers okay?')
assert 'Proxmox' not in household_safe_status('Why is everything slow?')
assert '192.0.2.' not in household_safe_status('Why is everything slow?')
assert target('Why is the NetBox monitor down?') == (['netbox'], 'netbox')
assert target('How is NetBox reporting unavailable?') == (['netbox'], 'netbox')
assert target('Is the game server working?') == (['minecraft'], 'Minecraft')
assert target('Can you verify whether our game server is currently online?') == (
    ['minecraft'], 'Minecraft'
)
agent_zero_capability_question = (
    'What can you currently verify about Agent Zero availability and task execution?'
)
assert target(agent_zero_capability_question) == (['agent', 'zero'], 'agent zero')
assert target('Can you verify whether Agent Zero is currently available?') == (
    ['agent', 'zero'], 'agent zero'
)
groups = namespace['_hades_homelab_availability_groups']
workloads_on_host = namespace['_hades_homelab_workloads_on_host_response']
core_vm_placement = namespace['_hades_homelab_core_vm_placement_response']
direct_read = namespace['_hades_direct_homelab_read']
direct_proxmox_backup = namespace['_hades_direct_proxmox_backup_read']
endpoint_before_provision = namespace['_hades_endpoint_intent_before_provision']
endpoint_response = namespace['_hades_service_endpoint_response']
placement_response = namespace['_hades_service_placement_response']
placement_intent = namespace['_hades_service_placement_intent']
managed_server_status_intent = namespace['_hades_managed_server_status_intent']
endpoint_continuation = namespace['_hades_endpoint_continuation_response']
direct_owner_location = namespace['_hades_direct_owner_location']

# A generalized public build must not repeat the previous private deployment's
# machine, node, or address. An owner may supply an explicit private description.
previous_location = os.environ.pop('HADES_CORE_LOCATION_DESCRIPTION', None)
try:
    assert direct_owner_location('Where is HADES live?') == ''
finally:
    if previous_location is not None:
        os.environ['HADES_CORE_LOCATION_DESCRIPTION'] = previous_location
os.environ['HADES_CORE_LOCATION_DESCRIPTION'] = 'HADES Core is on the owner-configured primary host.'
try:
    assert direct_owner_location('Where is HADES live?') == 'HADES Core is on the owner-configured primary host.'
finally:
    if previous_location is None:
        os.environ.pop('HADES_CORE_LOCATION_DESCRIPTION', None)
    else:
        os.environ['HADES_CORE_LOCATION_DESCRIPTION'] = previous_location

assert endpoint_before_provision(
    'Can you spin up a Minecraft server and give me the IP and port for the firewall?'
) is False
dogfood_request = (
    'Can you spin up a Minecraft server for me and lemme know the server '
    'port/ip so I can add it to the firewall?'
)
assert endpoint_before_provision(dogfood_request) is False
assert endpoint_before_provision('Can you spin up a Minecraft server?') is False
assert endpoint_before_provision('What is the Minecraft server IP and port?') is True
assert endpoint_before_provision('What is the IP address of Test Host?') is False
if source_path == default_source_path:
    # These assertions cover source-only handler wording and instrumentation.
    # A deployment overlay composed from a newer source route retains its own
    # separately reviewed bounded provisioning preflight.
    assert 'first call the read-only homelab_summary' in source
    assert 'asks_to_provision' in source
    assert 'Owner service endpoint inventory read completed without model invocation' in source
    assert 'Owner endpoint-request follow-up closed without model invocation' in source
else:
    # The deployed handler's control guidance is intentionally not replaced by
    # the narrow composer. Require its owner-only, bounded path to remain in
    # the composed artifact while the focused route contract tests its MCP
    # reads independently.
    assert 'mcp_homelab_readonly_homelab_summary' in source
    assert 'provisioning_request = bool(' in source
    assert 'inspect_templates()' in source
    assert 'obtain an explicit confirmation immediately' in source

request = 'Can you give me the Minecraft server IP and port for the firewall?'
empty_catalog = endpoint_response(
    request, {'status': 'OK', 'coverage': 'EMPTY', 'services': []}, 'owner'
)
assert 'service inventory is empty' in empty_catalog
assert 'doesn\'t establish whether an unlisted server exists' in empty_catalog
assert 'couldn\'t find a matching service record' in endpoint_response(
    request, {'status': 'OK', 'coverage': 'COMPLETE', 'services': []}, 'owner'
)
assert 'service inventory is incomplete' in endpoint_response(
    request, {'status': 'PARTIAL', 'coverage': 'UNKNOWN', 'services': []}, 'owner'
)
partial_with_candidate = endpoint_response(request, {
    'status': 'OK', 'coverage': 'PARTIAL', 'services': [{
        'name': 'Minecraft Server', 'addresses': ['192.0.2.10'],
        'port_mappings': ['tcp/25565'],
    }],
}, 'owner')
assert 'coverage is incomplete or unknown' in partial_with_candidate
unknown_coverage = endpoint_response(request, {'status': 'OK', 'services': []}, 'owner')
assert 'coverage is incomplete or unknown' in unknown_coverage
assert 'couldn\'t verify a server address or port' in endpoint_response(
    request, {'status': 'UNAVAILABLE', 'coverage': 'UNKNOWN', 'services': [], 'limitation': 'NetBox timed out.'}, 'owner'
)
assert endpoint_response(request, {'status': 'OK', 'services': []}, 'household') is None
assert placement_intent('Where is the Minecraft server running?', 'owner')
assert placement_intent('Where is the Minecraft server running?', 'household')
assert not managed_server_status_intent('Where is the Minecraft server running?', 'owner')
assert not managed_server_status_intent('Where is the Minecraft server running?', 'household')
assert managed_server_status_intent('Show my managed server status', 'owner')
placement_catalog = {
    'status': 'OK', 'coverage': 'COMPLETE', 'services': [{
        'name': 'Agent Zero', 'parent_name': 'Compute Node A',
        'addresses': ['192.0.2.30'], 'port_mappings': ['tcp/8080'],
    }],
}
placement = placement_response('Where is Agent Zero?', placement_catalog, 'owner')
assert 'Agent Zero on Compute Node A' in placement and '192.0.2.30' in placement, placement
assert 'does not verify that the service is currently running or reachable' in placement
assert placement_response('Where is Agent Zero?', placement_catalog, 'household') is None
assert 'incomplete' in placement_response(
    'Where is Agent Zero?', {'status': 'OK', 'coverage': 'PARTIAL', 'services': placement_catalog['services']}, 'owner'
)
assert 'empty' in placement_response(
    'Where is Agent Zero?', {'status': 'OK', 'coverage': 'EMPTY', 'services': []}, 'owner'
)
empty_nextcloud_placement = placement_response(
    'Where is Nextcloud running right now?',
    {'status': 'OK', 'coverage': 'EMPTY', 'services': []}, 'owner'
)
assert 'service catalog is empty' in empty_nextcloud_placement, empty_nextcloud_placement
assert "can't verify where that service is currently running" in empty_nextcloud_placement, empty_nextcloud_placement
assert 'where it is intended to run' in empty_nextcloud_placement, empty_nextcloud_placement
previous_agent_zero_url = os.environ.get('AGENT_ZERO_URL')
os.environ['AGENT_ZERO_URL'] = 'http://127.0.0.1:7002/private-path'
try:
    local_agent_zero = placement_response(
        'Where is Agent Zero running?', {'status': 'OK', 'coverage': 'EMPTY', 'services': []}, 'owner'
    )
    assert 'loopback port 7002 on the HADES host' in local_agent_zero, local_agent_zero
    assert 'returned an HTTP response' in local_agent_zero and 'NetBox' in local_agent_zero, local_agent_zero
    assert 'private-path' not in local_agent_zero, local_agent_zero
    namespace['_hades_agent_zero_available'] = lambda: False
    unavailable_agent_zero = placement_response(
        'Where is Agent Zero running?', {'status': 'OK', 'coverage': 'EMPTY', 'services': []}, 'owner'
    )
    assert "could not reach the configured endpoint" in unavailable_agent_zero, unavailable_agent_zero
finally:
    if previous_agent_zero_url is None:
        os.environ.pop('AGENT_ZERO_URL', None)
    else:
        os.environ['AGENT_ZERO_URL'] = previous_agent_zero_url
    namespace['_hades_agent_zero_available'] = lambda: True
assert 'multiple matching service records' in endpoint_response(
    'Can you give me the Minecraft IP and port for the firewall?', {
    'status': 'OK', 'coverage': 'COMPLETE', 'services': [
        {'name': 'Minecraft Server'}, {'name': 'Minecraft RCON'},
    ],
}, 'owner')
assert 'doesn\'t give one clear address and port' in endpoint_response(request, {
    'status': 'OK', 'coverage': 'COMPLETE', 'services': [{
        'name': 'Minecraft Server', 'addresses': [], 'port_mappings': ['tcp/25565'],
    }],
}, 'owner')
recorded = endpoint_response(request, {
    'status': 'OK', 'coverage': 'COMPLETE', 'services': [{
        'name': 'Minecraft Server', 'parent_name': 'Test Host',
        'addresses': ['192.0.2.10'], 'port_mappings': ['tcp/25565'],
    }],
}, 'owner')
assert '`192.0.2.10`' in recorded and 'tcp/25565' in recorded, recorded
assert 'doesn\'t verify that the service is running' in recorded, recorded
assert 'haven\'t changed the firewall' in recorded, recorded
dogfood_history = [
    {'role': 'user', 'content': request},
    {'role': 'assistant', 'content': endpoint_response(
        request, {'status': 'OK', 'coverage': 'EMPTY', 'services': []}, 'owner'
    )},
    {'role': 'user', 'content': 'Perfect, continue'},
]
continued = endpoint_continuation('Perfect, continue', dogfood_history, 'owner')
assert 'There\'s no server setup to continue' in continued, continued
assert 'firewall is unchanged' in continued and 'nothing was created' in continued, continued
assert endpoint_continuation(
    'Perfect, continue', dogfood_history, 'household'
) is None

assert target('Is Minecraft healthy enough for tonight?') == (['minecraft'], 'minecraft')
assert target('Are all the computers okay?') is None
assert namespace['_hades_homelab_target_from_question']('whats Compute Node A doing rn') == 'compute node a'
assert namespace['_hades_homelab_target_from_question']('Is Compute Node B alive?') == 'compute node b'
assert namespace['_hades_homelab_target_from_question']("What's wrong with Compute Node A?") == 'compute node a'
assert namespace['_hades_homelab_target_from_question']('Is everything okay?') is None
assert namespace['_hades_homelab_workload_host_target'](
    'What is running on Runtime Node A right now?'
) == 'Runtime Node A'
assert namespace['_hades_homelab_workload_host_target'](
    'Which Runtime Node A guests can HADES currently see, and which are running or stopped?'
) == 'Runtime Node A'
assert namespace['_hades_homelab_workload_host_target'](
    'Which VMs or containers are currently running on Runtime Node A?'
) == 'Runtime Node A'
assert namespace['_hades_homelab_workload_host_target']('What is running?') is None
cluster_guest_question = 'Which Proxmox guests are running right now, and which are stopped?'
assert namespace['_hades_homelab_workload_host_target'](cluster_guest_question) == 'Proxmox'
cluster_guest_resources = [
    {
        'name': 'Synthetic VM Alpha', 'runtime_status': 'RUNNING',
        'runtime': {'type': 'qemu', 'vmid': 101, 'status': 'running'},
        'identity': {'canonical_id': 'proxmox:site-a:qemu:101',
                     'source_identities': {'proxmox': ['proxmox:site-a:qemu:101']}},
    },
    {
        'name': 'Synthetic CT Beta', 'runtime_status': 'STOPPED',
        'runtime': {'type': 'lxc', 'vmid': 202, 'status': 'stopped'},
        'identity': {'canonical_id': 'proxmox:site-b:lxc:202',
                     'source_identities': {'proxmox': ['proxmox:site-b:lxc:202']}},
    },
]
complete_cluster_scope = {
    'status': 'COMPLETE', 'scope': 'ALL_GUESTS',
    'endpoints': [
        {'source_identity': 'proxmox:site-a', 'status': 'HEALTHY', 'scope': 'ALL_GUESTS'},
        {'source_identity': 'proxmox:site-b', 'status': 'HEALTHY', 'scope': 'ALL_GUESTS'},
    ],
}
cluster_guest_response = namespace['_hades_homelab_workloads_on_host_response'](
    cluster_guest_question, cluster_guest_resources, 'OK', [], complete_cluster_scope,
)
assert 'Complete audit scope' in cluster_guest_response, cluster_guest_response
assert 'Running: Synthetic VM Alpha (VM 101).' in cluster_guest_response, cluster_guest_response
assert 'Stopped: Synthetic CT Beta (CT 202).' in cluster_guest_response, cluster_guest_response
assert 'not application or service health' in cluster_guest_response, cluster_guest_response
partial_cluster_scope = {
    **complete_cluster_scope, 'status': 'PARTIAL', 'scope': 'MIXED',
    'endpoints': [complete_cluster_scope['endpoints'][0],
                  {'source_identity': 'proxmox:site-b', 'status': 'DEGRADED', 'scope': 'ALL_GUESTS'}],
}
partial_cluster_response = namespace['_hades_homelab_workloads_on_host_response'](
    cluster_guest_question, cluster_guest_resources, 'PARTIAL', [], partial_cluster_scope,
)
assert 'Only guests visible' in partial_cluster_response, partial_cluster_response
assert 'incomplete or unknown' in partial_cluster_response, partial_cluster_response

host_workloads = workloads_on_host('What is running on Runtime Node A?', [
    {'name': 'Runtime Node A', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
     'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
    {'name': 'Dinner VM', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:qemu:101']}},
     'runtime': {'type': 'qemu', 'node': 'pve-a', 'vmid': 101, 'status': 'running'}},
    {'name': 'Unrelated CT', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-b:lxc:202']}},
     'runtime': {'type': 'lxc', 'node': 'pve-a', 'vmid': 202, 'status': 'running'}},
], 'PARTIAL')
assert 'Runtime Node A online' in host_workloads and 'Dinner VM (VM 101, running)' in host_workloads
assert 'Unrelated CT' not in host_workloads and "Other source state is partial or unknown" in host_workloads
right_now_host_workloads = workloads_on_host(
    'What is running on Runtime Node A right now? Be clear about guest visibility limits.', [
    {'name': 'Runtime Node A', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
     'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
    {'name': 'Dinner VM', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:qemu:101']}},
     'runtime': {'type': 'qemu', 'node': 'pve-a', 'vmid': 101, 'status': 'running'}},
], 'PARTIAL')
assert 'Dinner VM (VM 101, running)' in right_now_host_workloads, right_now_host_workloads
selected_guest_coverage = {
    'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS',
    'endpoints': [{
        'source_identity': 'proxmox:site-a', 'status': 'DEGRADED',
        'scope': 'SELECTED_GUESTS', 'scoped_guest_count': 1,
    }],
}
selected_host_workloads = workloads_on_host(
    'Which Runtime Node A guests can HADES currently see?', [
        {'name': 'Runtime Node A', 'runtime_status': 'online',
         'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
         'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
        {'name': 'Dinner VM', 'runtime_status': 'running',
         'identity': {'source_identities': {'proxmox': ['proxmox:site-a:qemu:101']}},
         'runtime': {'type': 'qemu', 'node': 'pve-a', 'vmid': 101, 'status': 'running'}},
    ], 'PARTIAL', [], selected_guest_coverage,
)
assert 'Guests visible to this Proxmox read: Dinner VM' in selected_host_workloads
assert 'only selected guests' in selected_host_workloads and 'may be incomplete' in selected_host_workloads
selected_no_guest_workloads = workloads_on_host(
    'What is running on Runtime Node A?', [
        {'name': 'Runtime Node A', 'runtime_status': 'online',
         'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
         'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
    ], 'PARTIAL', [], selected_guest_coverage,
)
assert "can't conclude that it has none" in selected_no_guest_workloads
complete_no_guest_workloads = workloads_on_host(
    'What is running on Runtime Node A?', [
        {'name': 'Runtime Node A', 'runtime_status': 'online',
         'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
         'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
    ], 'OK', [], {
        'status': 'COMPLETE', 'scope': 'ALL_GUESTS',
        'endpoints': [{'source_identity': 'proxmox:site-a', 'status': 'HEALTHY', 'scope': 'ALL_GUESTS'}],
    },
)
assert 'Proxmox reports no VM or container guests on this host' in complete_no_guest_workloads
unconfigured_sources = workloads_on_host('What is running on Runtime Node A?', [
    {'name': 'Runtime Node A', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
     'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
], 'PARTIAL', [
    {'source': 'Proxmox', 'status': 'HEALTHY'},
    {'source': 'NetBox', 'status': 'NOT_CONFIGURED'},
    {'source': 'Uptime Kuma', 'status': 'NOT_CONFIGURED'},
])
assert 'Not configured: NetBox, Uptime Kuma' in unconfigured_sources
assert 'unavailable' not in unconfigured_sources
unavailable_sources = workloads_on_host('What is running on Runtime Node A?', [
    {'name': 'Runtime Node A', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
     'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
], 'PARTIAL', [
    {'source': 'Proxmox', 'status': 'HEALTHY'},
    {'source': 'NetBox', 'status': 'UNAVAILABLE'},
])
assert 'Configured source(s) unavailable: NetBox' in unavailable_sources
degraded_sources = workloads_on_host('What is running on Runtime Node A?', [
    {'name': 'Runtime Node A', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
     'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
], 'PARTIAL', [
    {'source': 'Proxmox', 'status': 'DEGRADED'},
])
assert 'Configured source(s) degraded: Proxmox' in degraded_sources
assert 'unavailable: Proxmox' not in degraded_sources
core_vm_rows = [
    {'name': 'Synthetic Virtualization Host', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:synthetic-virtualization-host:node:synthetic-virtualization-host']}},
     'runtime': {'type': 'node', 'node': 'synthetic-virtualization-host', 'status': 'online'}},
    {'name': 'hades-core', 'runtime_status': 'stopped',
     'identity': {'source_identities': {'proxmox': ['proxmox:synthetic-virtualization-host:qemu:800']}},
     'runtime': {'type': 'qemu', 'node': 'synthetic-virtualization-host', 'vmid': 800, 'status': 'stopped'}},
    {'name': 'hades-core', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:synthetic-virtualization-host:qemu:2802']}},
     'runtime': {'type': 'qemu', 'node': 'synthetic-virtualization-host', 'vmid': 2802, 'status': 'running'}},
    {'name': 'hades-core', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-b:qemu:2802']}},
     'runtime': {'type': 'qemu', 'node': 'synthetic-virtualization-host', 'vmid': 2802, 'status': 'running'}},
]
core_vm_answer = core_vm_placement('Which machine is running HADES?', core_vm_rows)
assert '3 guests matching HADES Core' in core_vm_answer and 'VM 800) is stopped on Synthetic Virtualization Host' in core_vm_answer
assert 'VM 2802) is running on Synthetic Virtualization Host' in core_vm_answer and 'application health' in core_vm_answer
assert "host can't be uniquely linked through Proxmox source identity" in core_vm_answer
assert core_vm_placement('What is HADES?', core_vm_rows) is None
assert "can't verify HADES Core VM placement" in core_vm_placement('Where is HADES running?', [])
assert 'couldn\'t verify' in workloads_on_host('What is running on Unknown Host?', [])
unlinked_host_workloads = workloads_on_host('What is running on Runtime Node B?', [
    {'name': 'Runtime Node B', 'runtime_status': 'online',
     'runtime': {'type': 'node', 'node': 'pve-b', 'status': 'online'}},
    {'name': 'Potential Cross-Cluster Guest', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-a:qemu:303']}},
     'runtime': {'type': 'qemu', 'node': 'pve-b', 'vmid': 303, 'status': 'running'}},
])
assert "can't correlate guests" in unlinked_host_workloads and 'Potential Cross-Cluster Guest' not in unlinked_host_workloads

fresh_minecraft = [{
    'name': 'Minecraft Server',
    'runtime_status': 'NOT_OBSERVED',
    'currently_online': False,
    'availability': {'name': 'Minecraft Server', 'status': 'up', 'last_updated': datetime.now(timezone.utc).isoformat()},
    'availability_freshness': 'FRESH',
}]
up = answer('Is Minecraft healthy enough for tonight?', fresh_minecraft)
assert "Uptime Kuma's configured check for Minecraft Server is up." in up, up
assert 'does not verify an application login, usable session, or workload state' in up, up
assert 'guarantee it is ready for use' in up, up

unlinked_netbox_check = [{
    'name': 'service-netbox',
    'identity': {'canonical_id': None},
    'availability': {
        'name': 'service-netbox', 'status': 'down',
        'last_updated': datetime.now(timezone.utc).isoformat(),
    },
    'availability_freshness': 'FRESH',
}]
netbox_diagnosis = answer(
    'Why is service-netbox down?', unlinked_netbox_check,
    {'sources': [{'source': 'NetBox', 'status': 'HEALTHY'}]},
)
assert "Uptime Kuma's configured check for service-netbox is down." in netbox_diagnosis, netbox_diagnosis
assert 'no verified identity link' in netbox_diagnosis, netbox_diagnosis
assert 'NetBox inventory responded' in netbox_diagnosis, netbox_diagnosis
assert "can't confirm that this probe targets NetBox" in netbox_diagnosis, netbox_diagnosis

unmonitored = answer('Is Jellyfin healthy enough for tonight?', fresh_minecraft)
assert 'couldn\'t verify a current Uptime Kuma service monitor matching jellyfin' in unmonitored, unmonitored
assert 'Proxmox host or VM being online does not show' in unmonitored, unmonitored
assert "can't call it healthy" in unmonitored, unmonitored
unmonitored_current = answer('Is Grocy working right now?', [], {
    'sources': [{
        'source': 'Uptime Kuma', 'status': 'HEALTHY',
        'retrieved_at': '2026-10-03T18:00:00+00:00',
    }],
})
assert 'Uptime Kuma was checked at 2026-10-03T18:00:00+00:00' in unmonitored_current, unmonitored_current
assert "couldn't verify a current Uptime Kuma service monitor matching grocy" in unmonitored_current, unmonitored_current
unmonitored_outage = answer('Is Grocy working right now?', [], {
    'sources': [{
        'source': 'Uptime Kuma', 'status': 'UNAVAILABLE',
        'retrieved_at': '2026-10-03T18:01:00+00:00',
    }],
})
assert 'Uptime Kuma was checked at 2026-10-03T18:01:00+00:00' in unmonitored_outage, unmonitored_outage
assert 'Uptime Kuma source was unavailable' in unmonitored_outage, unmonitored_outage

stale = [dict(fresh_minecraft[0], availability_freshness='STALE')]
stale_answer = answer('Is Minecraft online?', stale)
assert 'observation is stale' in stale_answer and "can't verify current service health" in stale_answer, stale_answer

ambiguous = fresh_minecraft + [{
    'name': 'Minecraft RCON',
    'availability': {'name': 'Minecraft RCON', 'status': 'up'},
    'availability_freshness': 'FRESH',
}]
ambiguous_answer = answer('Is Minecraft up?', ambiguous)
assert 'more than one Uptime Kuma check' in ambiguous_answer, ambiguous_answer
assert answer('Are all the computers okay?', fresh_minecraft) is None

# Exercise the actual owner shortcut through its configured working directory.
# The temporary adapter makes this a synthetic end-to-end route check; a
# missed shortcut would fall through to the intentionally unavailable model in
# the authenticated UI harness.
with tempfile.TemporaryDirectory(prefix='hades-service-health-route-') as temp_root:
    adapter_dir = Path(temp_root) / 'integrations' / 'homelab-readonly'
    adapter_dir.mkdir(parents=True)
    (adapter_dir / 'server.py').write_text(
        'def homelab_summary():\n'
        '    import os\n'
        '    if os.environ.get("HADES_TEST_NO_GAME_MONITOR") == "1":\n'
        '        sources = []\n'
        '        if os.environ.get("HADES_TEST_KUMA_UNAVAILABLE") == "1":\n'
        '            sources = [{"source": "Uptime Kuma", "status": "UNAVAILABLE", "retrieved_at": "2026-10-03T12:00:00Z"}]\n'
        '        return {"resources": [], "sources": sources, "service_catalog": {"status": "OK", "coverage": "EMPTY", "services": []}}\n'
        '    resources = [{"name": "Minecraft Server", '
        '"runtime_status": "NOT_OBSERVED", "currently_online": False, '
        '"availability": {"name": "Minecraft Server", "status": "up", '
        '"last_updated": "2026-09-27T12:00:00Z"}, '
        '"availability_freshness": "FRESH"}]\n'
        '    if os.environ.get("HADES_TEST_UNKNOWN_GAME_MONITOR") == "1":\n'
        '        resources[0]["availability"]["status"] = "unknown"\n'
        '    if os.environ.get("HADES_TEST_STALE_GAME_MONITOR") == "1":\n'
        '        resources[0]["availability_freshness"] = "STALE"\n'
        '    if os.environ.get("HADES_TEST_INFERENCE_NODE") == "1":\n'
        '        resources.append({"name": "Compute Node A", "runtime_status": "NOT_OBSERVED", '
        '                         "inventory": {"name": "Compute Node A"}, '
        '                         "identity": {"canonical_id": "netbox:device:7"}})\n'
        '    if os.environ.get("HADES_TEST_INFERENCE_NODE_B") == "1":\n'
        '        resources.append({"name": "Compute Node B", "runtime_status": "NOT_OBSERVED", '
        '                         "inventory": {"name": "Compute Node B"}, '
        '                         "identity": {"canonical_id": "netbox:device:8"}})\n'
        '    sources = []\n'
        '    if os.environ.get("HADES_TEST_NETBOX_MONITOR_CONFLICT") == "1":\n'
        '        resources.append({"name": "service-netbox", "availability": {"name": "service-netbox", '
        '                          "status": "down", "last_updated": "2026-10-03T02:00:00Z"}, '
        '                         "availability_freshness": "FRESH"})\n'
        '        sources = [{"source": "NetBox", "status": "READABLE", '
        '                    "retrieved_at": "2026-10-03T02:00:01Z"}]\n'
        '    return {"resources": resources, "sources": sources, '
        '"proxmox_guest_visibility": {"status": "PARTIAL", "scope": "SELECTED_GUESTS", "endpoints": [{"status": "DEGRADED", "scope": "SELECTED_GUESTS"}]}, '
        '"service_catalog": {"status": "OK", "coverage": "COMPLETE", "services": [{'
        '"name": "Minecraft Server", "parent_name": "Test Host", '
        '"addresses": ["192.0.2.10"], "port_mappings": ["tcp/25565"]}]}}\n'
        'def homelab_inference_inventory():\n'
        '    import os\n'
        '    if os.environ.get("HADES_TEST_INFERENCE_ALIAS") == "1":\n'
        '        return {"status": "READABLE", "endpoints": [{"status": "READABLE", '
        '                "source_identity": "inference:compute-lane-a", '
        '                "node_identity": "netbox:device:7", "identity_status": "LINKED", '
        '                "models": [{"name": "sample:small"}], "loaded_models": [], '
        '                "loaded_status": "CURRENT"}]}\n'
        '    return {"status": "READABLE", "endpoints": [{"status": "READABLE", '
        '            "node_identity": "netbox:device:7", "models": [{"name": "sample:small"}], '
        '            "loaded_models": [{"name": "sample:small"}]}]}\n'
        'def resolve_inference_node_target(target, inventory, summary):\n'
        '    if target.casefold() == "compute lane a" and inventory.get("endpoints", [{}])[0].get("identity_status") == "LINKED":\n'
        '        return ("netbox:device:7", "Compute Node A")\n'
        '    return None\n'
        'def homelab_gpu_telemetry():\n'
        '    return {"status": "READABLE", "retrieved_at": "2026-10-04T00:00:00Z", '
        '            "endpoints": [{"inference_id": "compute-lane-a", "status": "READABLE", '
        '            "devices": [{"index": 0, "memory_free_mib": 6000, "memory_total_mib": 8192, '
        '            "gpu_utilization_percent": 35}]}]}\n'
        'def homelab_owner_snapshot():\n'
        '    return {"summary": homelab_summary(), "compute": {"machines": [\n'
        '        {"name": "Compute Node A", "role": "synthetic inference node"}\n'
        '    ]}}\n'
        'def format_gpu_hardware_target_response(text, inventory, summary, telemetry):\n'
        '    return "GPU_HARDWARE_TARGET:Compute Node A"\n'
        'def homelab_compute_capabilities():\n'
        '    return {"machines": [{"name": "Compute Node A", "role": "synthetic inference node"}]}\n'
        'def format_inference_inventory_response(user_text, inventory, summary, gpu_telemetry=None):\n'
        '    if "compute lane a" in user_text.casefold() and gpu_telemetry:\n'
        '        return "The inference endpoint linked to Compute Node A is responding. Live host GPU sample (checked 2026-10-04T00:00:00Z): GPU 0 has 6000 MiB free of 8192 MiB at 35% utilization."\n'
        '    if "compare current model residency" in user_text.casefold():\n'
        '        return "Compute Node A: provider reports loaded sample:small; Compute Node B: loaded state unknown; I can\'t tell which host has more capacity without live free-VRAM data."\n'
        '    if "host another model" in user_text.casefold() or "host a 20 gb model" in user_text.casefold():\n'
        '        return "I can\'t determine which GPU has room because current free-VRAM data is unavailable."\n'
        '    return "sample:small is listed at Compute Node A based on provider-reported inventory."\n',
        encoding='utf-8',
    )
    old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
    os.environ['HADES_HERMES_WORKING_DIRECTORY'] = temp_root
    try:
        guest_scope_answer = direct_read(
            guest_scope_question, 'synthetic-owner', 'owner'
        )
        assert 'selected guests only' in guest_scope_answer, guest_scope_answer
        assert 'effective-permission data' in guest_scope_answer, guest_scope_answer
        routed_up = direct_read('Is Minecraft healthy enough for tonight?', 'synthetic-owner', 'owner')
        assert "Uptime Kuma's configured check for Minecraft Server is up." in routed_up, routed_up
        owner_game_status = direct_read(
            'Is the game server working?', 'synthetic-owner', 'owner'
        )
        assert "Uptime Kuma's configured check for Minecraft Server is up." in owner_game_status, owner_game_status
        assert "does not verify an application login" in owner_game_status, owner_game_status
        os.environ['HADES_TEST_NETBOX_MONITOR_CONFLICT'] = '1'
        try:
            monitor_diagnosis = direct_read(
                'Why is the NetBox monitor down?', 'synthetic-owner', 'owner'
            )
        finally:
            os.environ.pop('HADES_TEST_NETBOX_MONITOR_CONFLICT', None)
        assert "Uptime Kuma's configured check for service-netbox is down." in monitor_diagnosis, monitor_diagnosis
        assert "That shows the probe failed, but not why." in monitor_diagnosis, monitor_diagnosis
        assert "NetBox inventory responded, but I can't confirm that this probe targets NetBox." in monitor_diagnosis, monitor_diagnosis
        household_monitor_diagnosis = direct_read(
            'Why is the NetBox monitor down?', 'synthetic-household', 'household'
        )
        assert "I can't check all the home computers from this account." in household_monitor_diagnosis, household_monitor_diagnosis
        assert 'NetBox' not in household_monitor_diagnosis and 'Kuma' not in household_monitor_diagnosis
        household_game_status = direct_read(
            'Is Minecraft working?', 'synthetic-household', 'household'
        )
        assert 'configured game-server check is responding' in household_game_status
        assert 'Test Host' not in household_game_status and '192.0.2.' not in household_game_status
        generic_household_game_status = direct_read(
            'Is the game server working?', 'synthetic-household', 'household'
        )
        assert 'configured game-server check is responding' in generic_household_game_status
        assert 'Test Host' not in generic_household_game_status and '192.0.2.' not in generic_household_game_status
        os.environ['HADES_TEST_NO_GAME_MONITOR'] = '1'
        try:
            missing_game_check = direct_read(
                'Is Minecraft working?', 'synthetic-household', 'household'
            )
            owner_missing_game_check = direct_read(
                'Is the game server working?', 'synthetic-owner', 'owner'
            )
        finally:
            os.environ.pop('HADES_TEST_NO_GAME_MONITOR', None)
        assert "I don't have a current check for the game server" in missing_game_check, missing_game_check
        assert 'Proxmox' not in missing_game_check and 'Test Host' not in missing_game_check, missing_game_check
        assert "couldn't verify a current Uptime Kuma service monitor matching Minecraft" in owner_missing_game_check, owner_missing_game_check
        assert "I can't call it healthy" in owner_missing_game_check, owner_missing_game_check
        os.environ['HADES_TEST_UNKNOWN_GAME_MONITOR'] = '1'
        try:
            inconclusive_game_check = direct_read(
                'Is Minecraft working?', 'synthetic-household', 'household'
            )
        finally:
            os.environ.pop('HADES_TEST_UNKNOWN_GAME_MONITOR', None)
        assert 'current game-server check is inconclusive' in inconclusive_game_check, inconclusive_game_check
        os.environ['HADES_TEST_STALE_GAME_MONITOR'] = '1'
        try:
            stale_game_check = direct_read(
                'Is Minecraft working?', 'synthetic-household', 'household'
            )
        finally:
            os.environ.pop('HADES_TEST_STALE_GAME_MONITOR', None)
        assert 'last game-server check is stale' in stale_game_check, stale_game_check
        os.environ['HADES_TEST_NO_GAME_MONITOR'] = '1'
        os.environ['HADES_TEST_KUMA_UNAVAILABLE'] = '1'
        try:
            unreadable_game_check = direct_read(
                'Is Minecraft working?', 'synthetic-household', 'household'
            )
        finally:
            os.environ.pop('HADES_TEST_NO_GAME_MONITOR', None)
            os.environ.pop('HADES_TEST_KUMA_UNAVAILABLE', None)
        assert "couldn't read a current game-server check" in unreadable_game_check, unreadable_game_check
        assert 'couldn\'t find a matching service record' in direct_read(
            'Where is Agent Zero?', 'synthetic-owner', 'owner'
        )
        assert direct_read('Where is Agent Zero?', 'synthetic-household', 'household') is None
        previous_agent_zero_url = os.environ.get('AGENT_ZERO_URL')
        os.environ['AGENT_ZERO_URL'] = 'http://127.0.0.1:7002'
        registry_module.registry.calls.clear()
        try:
            agent_zero_live = direct_read(
                'Where is Agent Zero running?', 'synthetic-owner', 'owner'
            )
            assert 'loopback port 7002 on the HADES host' in agent_zero_live, agent_zero_live
            assert 'delegation or task execution' in agent_zero_live, agent_zero_live
            assert len(registry_module.registry.calls) == 1 and registry_module.registry.calls[0][0].endswith('homelab_summary'), registry_module.registry.calls
            registry_module.registry.calls.clear()
            agent_zero_capability = direct_read(
                agent_zero_capability_question, 'synthetic-owner', 'owner'
            )
            assert 'configured Agent Zero endpoint responded' in agent_zero_capability, agent_zero_capability
            assert 'task execution is unverified' in agent_zero_capability, agent_zero_capability
            assert len(registry_module.registry.calls) == 1 and registry_module.registry.calls[0][0].endswith('homelab_summary'), registry_module.registry.calls
            registry_module.registry.calls.clear()
            household_agent_zero_capability = direct_read(
                agent_zero_capability_question, 'synthetic-household', 'household'
            )
            assert 'can\'t check all the home computers' in household_agent_zero_capability, household_agent_zero_capability
            assert '7002' not in household_agent_zero_capability and 'configured endpoint' not in household_agent_zero_capability
            assert not registry_module.registry.calls, registry_module.registry.calls
            namespace['_hades_agent_zero_available'] = lambda: False
            unavailable_agent_zero_capability = direct_read(
                agent_zero_capability_question, 'synthetic-owner', 'owner'
            )
            assert 'could not reach its configured Agent Zero endpoint' in unavailable_agent_zero_capability, unavailable_agent_zero_capability
            assert 'task execution is unverified' in unavailable_agent_zero_capability, unavailable_agent_zero_capability
            namespace['_hades_agent_zero_available'] = lambda: True
            registry_module.registry.calls.clear()
            household_agent_zero = direct_read(
                'Where is Agent Zero running?', 'synthetic-household', 'household'
            )
            assert household_agent_zero and '7002' not in household_agent_zero and 'loopback' not in household_agent_zero, household_agent_zero
            assert not registry_module.registry.calls, registry_module.registry.calls
        finally:
            if previous_agent_zero_url is None:
                os.environ.pop('AGENT_ZERO_URL', None)
            else:
                os.environ['AGENT_ZERO_URL'] = previous_agent_zero_url
        os.environ['HADES_TEST_INFERENCE_NODE'] = '1'
        try:
            followup_context = (
                "What's wrong with Compute Node A?\n"
                "Compute Node A's host runtime could not be verified.\n"
                "What about Compute Node A?\n"
                "Compute Node A has one provider-reported model.\n"
            )
            named_followup = direct_read(
                'What about Compute Node A?', 'synthetic-owner', 'owner',
                context_text=followup_context + 'What about Compute Node A?',
            )
            assert 'sample:small is listed at Compute Node A' in named_followup, named_followup
            os.environ['HADES_TEST_INFERENCE_ALIAS'] = '1'
            registry_module.registry.calls.clear()
            try:
                alias_activity = direct_read(
                    "What's Compute Lane A doing right now?", 'synthetic-owner', 'owner'
                )
            finally:
                os.environ.pop('HADES_TEST_INFERENCE_ALIAS', None)
            assert 'inference endpoint linked to Compute Node A is responding' in alias_activity, alias_activity
            assert 'Live host GPU sample' in alias_activity and '6000 MiB free' in alias_activity, alias_activity
            assert 'Compute Lane A is responding' not in alias_activity, alias_activity
            assert any(call[0].endswith('homelab_gpu_telemetry') for call in registry_module.registry.calls), registry_module.registry.calls
            assert namespace['_hades_homelab_gpu_hardware_target_intent'](
                'What server has the four P4000s?'
            )
            assert namespace['_hades_homelab_gpu_hardware_target_intent'](
                'Which server has two RTX 2080s?'
            )
            assert namespace['_hades_homelab_gpu_hardware_target_intent'](
                'How is the big GPU box doing right now?'
            )
            assert namespace['_hades_homelab_gpu_hardware_target_intent'](
                'hows the big gpu box'
            )
            registry_module.registry.calls.clear()
            os.environ['HADES_TEST_INFERENCE_ALIAS'] = '1'
            hardware_alias = direct_read(
                'What server has the four P4000s?', 'synthetic-owner', 'owner'
            )
            assert hardware_alias == 'GPU_HARDWARE_TARGET:Compute Node A', hardware_alias
            hardware_tools = [call[0].rsplit('__', 1)[-1] for call in registry_module.registry.calls]
            assert hardware_tools == [
                'homelab_inference_inventory', 'homelab_owner_snapshot', 'homelab_gpu_telemetry',
            ], hardware_tools
            registry_module.registry.calls.clear()
            big_hardware_alias = direct_read(
                'hows the big gpu box', 'synthetic-owner', 'owner'
            )
            assert big_hardware_alias == 'GPU_HARDWARE_TARGET:Compute Node A', big_hardware_alias
            big_hardware_tools = [call[0].rsplit('__', 1)[-1] for call in registry_module.registry.calls]
            assert big_hardware_tools == [
                'homelab_inference_inventory', 'homelab_owner_snapshot', 'homelab_gpu_telemetry',
            ], big_hardware_tools
            registry_module.registry.calls.clear()
            household_gpu_alias = direct_read(
                'How is the big GPU box doing right now?', 'synthetic-household', 'household'
            )
            assert household_gpu_alias == 'I can\'t provide internal host or GPU hardware details from this account.', household_gpu_alias
            assert not registry_module.registry.calls, registry_module.registry.calls
            os.environ.pop('HADES_TEST_INFERENCE_ALIAS', None)
            issue_question = direct_read(
                "What's wrong with Compute Node A?", 'synthetic-owner', 'owner'
            )
            assert 'sample:small is listed at Compute Node A' in issue_question, issue_question
            assert "can't say whether it's online" in issue_question, issue_question
            room_followup = direct_read(
                'Which one has more room?', 'synthetic-owner', 'owner',
                context_text=followup_context + 'Which one has more room?',
            )
            assert "can't determine which GPU has room" in room_followup, room_followup
            model_size_followup = direct_read(
                'What about a 20 GB one?', 'synthetic-owner', 'owner',
                context_text=followup_context + 'What about a 20 GB one?',
            )
            assert "can't confirm whether a 20 GB model fits" in model_size_followup, model_size_followup
            assert "model file's GB size is not its VRAM requirement" in model_size_followup, model_size_followup
            correction = direct_read(
                'Sorry, Compute Node A', 'synthetic-owner', 'owner',
                context_text=followup_context + 'Sorry, Compute Node A',
            )
            assert 'sample:small is listed at Compute Node A' in correction, correction
            os.environ['HADES_TEST_INFERENCE_NODE_B'] = '1'
            comparison_context = (
                "What's wrong with Compute Node A?\n"
                "What about Compute Node B?\n"
                "Which one has more room?"
            )
            comparison = direct_read(
                'Which one has more room?', 'synthetic-owner', 'owner',
                context_text=comparison_context,
            )
            assert 'Compute Node A: provider reports loaded sample:small' in comparison, comparison
            assert 'Compute Node B: loaded state unknown' in comparison, comparison
            assert "can't tell which host has more capacity" in comparison, comparison
            os.environ.pop('HADES_TEST_INFERENCE_NODE_B', None)
            assert namespace['_hades_homelab_followup_prompt'](
                'Which one has more room?', 'owner', ''
            ) == 'Where should I run another model?'
            original_dispatch = registry_module.registry.dispatch
            registry_module.registry.dispatch = lambda name, _arguments: {
                'resources': [
                    {'name': 'Compute Node A', 'inventory': {'name': 'Compute Node A'}},
                    {'name': 'Compute Node B', 'inventory': {'name': 'Compute Node B'}},
                ]
            }
            try:
                compare_context = (
                    "What's wrong with Compute Node A?\n"
                    "What about Compute Node B?\n"
                    "Which one has more room?"
                )
                comparison_prompt = namespace['_hades_homelab_followup_prompt'](
                    'Which one has more room?', 'owner', compare_context
                )
                assert comparison_prompt == (
                    'Compare current model residency and GPU capacity on Compute Node A and Compute Node B'
                ), comparison_prompt
                explicit_comparison = namespace['_hades_homelab_followup_prompt'](
                    'Which has more room for another model, Compute Node A or Compute Node B?',
                    'owner', '',
                )
                assert explicit_comparison == (
                    'Compare current model residency and GPU capacity on Compute Node A and Compute Node B'
                ), explicit_comparison
            finally:
                registry_module.registry.dispatch = original_dispatch
        finally:
            os.environ.pop('HADES_TEST_INFERENCE_NODE', None)
        assert "can't check all the home computers" in direct_read(
            'Is the homelab okay?', 'synthetic-household', 'household'
        )
        routed_endpoint = direct_read(
            request,
            'synthetic-owner', 'owner',
        )
        assert '`192.0.2.10`' in routed_endpoint and 'tcp/25565' in routed_endpoint, routed_endpoint
        routed_missing = direct_read('Is Jellyfin healthy enough for tonight?', 'synthetic-owner', 'owner')
        assert "couldn't verify a current Uptime Kuma service monitor matching jellyfin" in routed_missing, routed_missing
        assert direct_read('What is a network?', 'synthetic-owner', 'owner') is None
        assert direct_read('What is a server?', 'synthetic-owner', 'owner') is None
        assert direct_read('What is Proxmox?', 'synthetic-owner', 'owner') is None
        assert direct_read('What does Minecraft do?', 'synthetic-owner', 'owner') is None
        routed_network = direct_read('Why does the network feel slow?', 'synthetic-owner', 'owner')
        assert 'Packet-loss, throughput, DNS timing, and historical comparison data are unavailable' in routed_network, routed_network
        assert "can't identify a network bottleneck or trend from this evidence" in routed_network, routed_network
        assert 'The live homelab view is partial' not in routed_network, routed_network
        assert 'no verified cross-source identity link' not in routed_network, routed_network

        def write_broad_summary(monitors, **overrides):
            summary = {
                'status': 'OK',
                'online_names': ['HADES Core'],
                'inventory_only_names': [],
                'availability_summary': monitors,
                'resources': [{
                    'name': 'HADES Core', 'runtime_status': 'running',
                    'currently_online': True, 'runtime': {'vmid': 2802},
                    'availability': None, 'availability_observations': [],
                    'availability_freshness': 'UNKNOWN', 'conflicts': [],
                }],
                'conflicts': [], 'identity_warnings': [], 'errors': [],
                'service_catalog': {
                    'status': 'OK', 'coverage': 'EMPTY', 'services': [],
                    'records_returned': 0, 'source_total': 0,
                },
            }
            summary.update(overrides)
            (adapter_dir / 'server.py').write_text(
                'def homelab_summary():\n    return ' + repr(summary) + '\n'
                'def homelab_inference_inventory():\n'
                '    return {"status": "READABLE", "endpoints": [{"source_identity": "inference:test-fast", '
                '"status": "READABLE", "models": [{"name": "synthetic-model"}], '
                '"loaded_status": "CURRENT", "loaded_models": []}]}\n',
                encoding='utf-8',
            )

        write_broad_summary([], status='PARTIAL', sources=[
            {'source': 'Proxmox', 'status': 'OK'},
            {'source': 'NetBox', 'status': 'UNAVAILABLE'},
        ], conflicts=[{
            'name': 'Synthetic Node A',
            'reasons': ['NetBox intended node differs from Proxmox runtime node'],
        }], source_counts={'identity_unlinked_resources': 2},
            proxmox_guest_visibility={'status': 'PARTIAL'})
        registry_module.registry.calls.clear()
        conflict_answer = direct_read(
            'Are any homelab sources contradicting each other right now?',
            'synthetic-owner', 'owner',
        )
        assert 'Synthetic Node A' in conflict_answer and 'differs from Proxmox runtime node' in conflict_answer, conflict_answer
        assert 'not a lab-wide agreement or all-clear' in conflict_answer, conflict_answer
        assert len(registry_module.registry.calls) == 1 and registry_module.registry.calls[0][0].endswith('homelab_summary'), registry_module.registry.calls
        explicit_source_conflict = direct_read(
            'Do NetBox, Proxmox, and Uptime Kuma disagree about any server right now? Show conflicts only, and distinguish intended state from live runtime and probe state.',
            'synthetic-owner', 'owner',
        )
        assert 'The current homelab read found source conflicts:' in explicit_source_conflict, explicit_source_conflict
        assert 'live runtime and probe state' not in explicit_source_conflict.casefold(), explicit_source_conflict
        registry_module.registry.calls.clear()
        write_broad_summary([], status='PARTIAL', source_counts={
            'identity_unlinked_resources': 2,
        }, resources=[
            {
                'name': 'Synthetic Guest A',
                'identity': {
                    'status': 'UNLINKED', 'canonical_id': None,
                    'source_identities': {'proxmox': ['proxmox:synthetic-pve:qemu:802'], 'kuma': []},
                },
                'runtime': {'type': 'qemu', 'vmid': 802, 'node': 'synthetic-pve'},
            },
            {
                'name': 'Synthetic Host Monitor',
                'identity': {
                    'status': 'UNLINKED', 'canonical_id': None,
                    'source_identities': {'proxmox': [], 'kuma': ['kuma:monitor:17']},
                },
            },
        ])
        unlinked_answer = direct_read(
            'Which source records are still unlinked?', 'synthetic-owner', 'owner'
        )
        assert unlinked_answer and 'without a verified cross-source identity link' in unlinked_answer, unlinked_answer
        assert 'Synthetic Guest A (Proxmox QEMU guest VMID 802 on synthetic-pve)' in unlinked_answer, unlinked_answer
        assert 'Synthetic Host Monitor (Uptime Kuma monitor ID 17)' in unlinked_answer, unlinked_answer
        assert len(registry_module.registry.calls) == 1 and registry_module.registry.calls[0][0].endswith('homelab_summary'), registry_module.registry.calls
        registry_module.registry.calls.clear()
        assert "can't check all the home computers" in direct_read(
            'Are any homelab sources contradicting each other right now?',
            'synthetic-household', 'household',
        )
        assert "can't check all the home computers" in direct_read(
            'Do NetBox, Proxmox, and Uptime Kuma disagree about any server right now? Show conflicts only, and distinguish intended state from live runtime and probe state.',
            'synthetic-household', 'household',
        )
        assert not registry_module.registry.calls, registry_module.registry.calls

        write_broad_summary([])
        no_coverage = direct_read(
            'Are there any blockers in the homelab?', 'synthetic-owner', 'owner'
        )
        assert "No current Uptime Kuma availability observations were returned, so I can't confirm service health." in no_coverage, no_coverage
        assert 'No blocker was reported by the configured live sources.' not in no_coverage, no_coverage

        write_broad_summary([{
            'name': 'service-netbox', 'status': 'down', 'freshness': 'FRESH',
        }], status='PARTIAL', sources=[
            {'source': 'Uptime Kuma', 'status': 'OK'},
            {'source': 'Proxmox guest visibility (runtime_node_a)', 'status': 'PARTIAL'},
        ], service_catalog={
            'status': 'OK', 'coverage': 'EMPTY', 'services': [],
        }, proxmox_guest_visibility={'status': 'PARTIAL'})
        registry_module.registry.calls.clear()
        coverage_answer = direct_read(
            'Which services can you not verify right now?',
            'synthetic-owner', 'owner',
        )
        assert 'Fresh configured Uptime Kuma probes are failing for: service-netbox.' in coverage_answer, coverage_answer
        assert "NetBox's application-service catalog is reachable but currently empty" in coverage_answer, coverage_answer
        assert 'services on unreported guests remain unverified' in coverage_answer, coverage_answer
        assert coverage_answer.index("NetBox's application-service catalog") < coverage_answer.index('Fresh configured Uptime Kuma probes'), coverage_answer
        assert len(registry_module.registry.calls) == 1 and registry_module.registry.calls[0][0].endswith('homelab_summary'), registry_module.registry.calls

        write_broad_summary([{
            'name': 'HADES Core', 'status': 'up', 'freshness': 'FRESH',
        }])
        covered = direct_read(
            'Are there any blockers in the homelab?', 'synthetic-owner', 'owner'
        )
        assert 'No blocker was reported by the configured live sources.' in covered, (covered, debug_logs[-4:])
        assert 'A responding probe does not prove application login' in covered, covered
        assert 'Fresh configured Uptime Kuma probes responded for: HADES Core.' in covered, covered
        no_current_failures = direct_read('What is down?', 'synthetic-owner', 'owner')
        assert 'No fresh configured Uptime Kuma probe is currently reporting a failure.' in no_current_failures, no_current_failures
        assert "NetBox's application-service catalog is reachable but empty" in no_current_failures, no_current_failures
        assert 'intended placement for unlisted services remains unverified' in no_current_failures, no_current_failures
        assert "Uptime Kuma's configured probes failed:" not in no_current_failures, no_current_failures
        everything_ok = direct_read('Is everything okay?', 'synthetic-owner', 'owner')
        assert 'Live inference reads: Test Fast API responding (1 catalog models; 0 reported loaded)' in everything_ok, everything_ok
        assert 'Inference-worker health was not independently verified' not in everything_ok, everything_ok
        my_homelab_ok = direct_read('Is everything okay with my homelab?', 'synthetic-owner', 'owner')
        assert 'Live inference reads: Test Fast API responding (1 catalog models; 0 reported loaded)' in my_homelab_ok, my_homelab_ok
        assert 'do not prove generation or available GPU capacity' in my_homelab_ok, my_homelab_ok
        write_broad_summary([{
            'name': 'Search latency check', 'status': 'down', 'freshness': 'STALE',
        }])
        stale_down = direct_read('What is down?', 'synthetic-owner', 'owner')
        assert 'No fresh configured Uptime Kuma probe is currently reporting a failure.' in stale_down, stale_down
        assert 'Current Uptime Kuma probe status is stale or unknown for:' in stale_down, stale_down
        assert 'Search latency check (last reported down; stale)' in stale_down, stale_down
        write_broad_summary([{
            'name': 'HADES Core', 'status': 'up', 'freshness': 'FRESH',
        }])
        mcp_read_logs = [row for row in info_logs if row and str(row[0]).startswith('Homelab MCP read completed:')]
        assert mcp_read_logs, info_logs
        assert any(
            len(row) == 6
            and row[1] == 'homelab_summary'
            and row[2] in {'HEALTHY', 'READABLE', 'PARTIAL', 'UNAVAILABLE', 'SOURCE_UNAVAILABLE', 'NOT_CONFIGURED', 'CONFIGURATION_ERROR', 'UNKNOWN', 'OTHER'}
            and all(isinstance(value, (str, int, float)) for value in row[1:])
            for row in mcp_read_logs
        ), mcp_read_logs
        assert not any(
            any(isinstance(value, (dict, list)) for value in row)
            for row in mcp_read_logs
        ), mcp_read_logs
        for prompt in (
            'Is everything okay?', 'What is down?', 'Anything dying?', "What's fucked?",
            'Which computer is having trouble?', "Why's shit slow?", 'What changed?',
            'What changed since yesterday?', 'What changed in the homelab since yesterday?',
            'What changed in my homelab since yesterday?',
            'What changed in the homelab in the last 24 hours?',
            'What changed in my homelab since yesterday? Only report changes the live sources can establish, and say what you cannot compare.',
            'What changed on the infrastructure since last week?', 'What changed since last week?',
        ):
            registry_module.registry.calls.clear()
            answer_text = direct_read(prompt, 'synthetic-owner', 'owner')
            assert answer_text, f'direct owner homelab status route missed {prompt!r}'
            if prompt.startswith('What changed'):
                assert 'recent homelab changes' in answer_text.casefold(), (answer_text, debug_logs[-5:], registry_module.registry.calls[-5:])
                assert len(registry_module.registry.calls) == 1 and registry_module.registry.calls[0][0].endswith('homelab_recent_activity'), registry_module.registry.calls
        os.environ['HADES_TEST_PROXMOX_ACTIVITY'] = '1'
        try:
            recent_activity_answer = direct_read(
                'What changed in the homelab since last week?', 'synthetic-owner', 'owner'
            )
        finally:
            os.environ.pop('HADES_TEST_PROXMOX_ACTIVITY', None)
        assert 'qmstart for guest 12802 on synthetic-pve (ok, started at 2026-10-02 12:00 UTC; ended at 2026-10-02 13:00 UTC)' in recent_activity_answer, (recent_activity_answer, registry_module.registry.calls[-5:], debug_logs[-3:])
        assert 'last 168 hours' in recent_activity_answer, recent_activity_answer
        assert 'saved prior homelab snapshot' in recent_activity_answer, recent_activity_answer
        assert 'not a complete change log' in recent_activity_answer, recent_activity_answer
        assert 'NetBox device synthetic-router was last updated' in recent_activity_answer, recent_activity_answer
        assert 'Proxmox task coverage is partial' in recent_activity_answer, recent_activity_answer
        assert 'deletions are not included' in recent_activity_answer, recent_activity_answer
        assert (
            'Host operating-system, package/driver, and in-guest service events aren\'t included'
            in recent_activity_answer
        ), recent_activity_answer
        os.environ['HADES_TEST_PROXMOX_ACTIVITY'] = '1'
        try:
            recent_day_answer = direct_read(
                'What changed in the homelab in the last 24 hours?', 'synthetic-owner', 'owner'
            )
        finally:
            os.environ.pop('HADES_TEST_PROXMOX_ACTIVITY', None)
        assert 'last 24 hours' in recent_day_answer, recent_day_answer
        assert registry_module.registry.calls[-1][1] == {'window_hours': 24}, registry_module.registry.calls[-1]
        calls_before_household_change = len(registry_module.registry.calls)
        household_changes = direct_read(
            'What changed in the homelab since yesterday?', 'synthetic-household', 'household'
        )
        assert len(registry_module.registry.calls) == calls_before_household_change
        assert household_changes == "I can't verify private infrastructure changes from this account."
        assert 'Proxmox' not in household_changes and 'guest' not in household_changes
        household_overall = direct_read('What is down?', 'synthetic-household', 'household')
        assert "can't check all the home computers" in household_overall, household_overall
        assert 'Proxmox' not in household_overall and 'NetBox' not in household_overall, household_overall
        household_slow = direct_read('Why is everything slow?', 'synthetic-household', 'household')
        assert "can't diagnose why everything is slow" in household_slow, household_slow
        assert 'Proxmox' not in household_slow and 'Uptime Kuma' not in household_slow, household_slow
        assert direct_read('Is everything okay?', 'synthetic-household', 'household') == household_overall
        for prompt in ('Is the homelab okay?', 'Are my computers okay?', 'Are all the computers okay?', 'Is Synthetic Inference Node A alive?', "What's Synthetic Inference Node A doing?"):
            restricted = direct_read(prompt, 'synthetic-household', 'household')
            assert "can't check all the home computers" in restricted, restricted
            assert 'Synthetic Inference Node A' not in restricted and 'Proxmox' not in restricted, restricted
        for prompt in ('Where is HADES running?', 'Where is Minecraft running?'):
            restricted_location = direct_read(prompt, 'synthetic-household', 'household')
            assert "can't provide internal host or address details" in restricted_location, restricted_location
        write_broad_summary(
            [{'name': 'service-netbox', 'status': 'down', 'freshness': 'FRESH'}],
            sources=[{'source': 'NetBox', 'status': 'HEALTHY'}],
            resources=[{'name': 'service-netbox', 'identity': {'canonical_id': None},
                        'availability': {'name': 'service-netbox', 'status': 'down'},
                        'availability_freshness': 'FRESH'}],
        )
        disagreement = direct_read('What is down?', 'synthetic-owner', 'owner')
        assert 'The NetBox inventory API responded to this read' in disagreement, disagreement
        assert 'target has no verified identity link' in disagreement, disagreement
        assert 'Live inference reads: Test Fast API responding' in disagreement, disagreement
        named_netbox_diagnosis = direct_read(
            'Why is service-netbox down?', 'synthetic-owner', 'owner'
        )
        assert 'NetBox inventory responded' in named_netbox_diagnosis, named_netbox_diagnosis
        assert 'monitor has no verified identity link' in named_netbox_diagnosis, named_netbox_diagnosis
        assert "can't confirm that this probe targets NetBox" in named_netbox_diagnosis, named_netbox_diagnosis
        calls_before_private_monitor = len(registry_module.registry.calls)
        private_monitor_diagnosis = direct_read(
            'Why is service-netbox down?', 'synthetic-household', 'household'
        )
        assert len(registry_module.registry.calls) == calls_before_private_monitor
        assert "can't check all the home computers" in private_monitor_diagnosis, private_monitor_diagnosis
        assert 'NetBox' not in private_monitor_diagnosis and 'service-netbox' not in private_monitor_diagnosis
        write_broad_summary(
            [], status='PARTIAL',
            sources=[
                {'source': 'Proxmox', 'status': 'HEALTHY'},
                {'source': 'NetBox', 'status': 'UNAVAILABLE'},
                {'source': 'Uptime Kuma', 'status': 'HEALTHY'},
                {'source': 'Optional Source', 'status': 'NOT_CONFIGURED'},
            ],
            errors=['NetBox unavailable'],
        )
        source_outage = direct_read('Is everything okay?', 'synthetic-owner', 'owner')
        assert 'The live homelab view is partial.' in source_outage, source_outage
        assert "No current Uptime Kuma availability observations were returned, so I can't confirm service health." in source_outage, source_outage
        assert 'Current source reads unavailable or degraded: NetBox.' in source_outage, source_outage
        assert 'Proxmox' in source_outage and 'Uptime Kuma' in source_outage, source_outage
        assert 'unreported nodes remain unknown' in source_outage, source_outage
        assert 'Optional Source' not in source_outage, source_outage
        right_now_status = direct_read(
            'Is everything okay with the homelab right now?', 'synthetic-owner', 'owner'
        )
        assert 'The live homelab view is partial.' in right_now_status, right_now_status
        assert 'Live inference reads: Test Fast API responding' in right_now_status, right_now_status
        compound_status = direct_read(
            'What is down or degraded right now, and what can you not verify?',
            'synthetic-owner', 'owner',
        )
        assert 'The live homelab view is partial.' in compound_status, compound_status
        assert 'Current source reads unavailable or degraded: NetBox.' in compound_status, compound_status
        assert 'unreported nodes remain unknown' in compound_status, compound_status
        calls_before_compound_household = len(registry_module.registry.calls)
        compound_household = direct_read(
            'What is down or degraded right now, and what can you not verify?',
            'synthetic-household', 'household',
        )
        assert "can't check all the home computers" in compound_household
        assert 'NetBox' not in compound_household and 'Proxmox' not in compound_household
        assert len(registry_module.registry.calls) == calls_before_compound_household
        write_broad_summary(
            [],
            inventory_only_names=['GPU Node'],
            source_counts={'identity_unlinked_resources': 3},
            resources=[
                {'name': 'Lab Host', 'runtime_status': 'online', 'currently_online': True,
                 'runtime': {'status': 'online', 'mem': 8, 'maxmem': 16, 'disk': 20, 'maxdisk': 40}},
                {'name': 'App Guest', 'runtime_status': 'running', 'currently_online': True,
                 'runtime': {'name': 'ignored', 'vmid': 2803, 'node': 'Lab Host', 'status': 'running',
                             'mem': 4, 'maxmem': 8, 'disk': 10, 'maxdisk': 20}},
            ],
        )
        formatted = direct_read('Give me a detailed homelab status', 'synthetic-owner', 'owner')
        assert 'Lab Host host' in formatted and 'App Guest VM 2803 on Lab Host' in formatted, formatted
        assert 'None VM None' not in formatted, formatted
        assert 'no linked Proxmox runtime record is available' in formatted and 'does not mean they are offline' in formatted, formatted
        assert '3 Proxmox or Uptime Kuma resources have no verified cross-source identity link' in formatted, formatted
        assert 'Proxmox-reported disk fields' in formatted and 'not guest filesystem utilization' in formatted, formatted
        (adapter_dir / 'server.py').write_text(
            'def homelab_inference_inventory():\n'
            '    return {"status": "READABLE", "endpoints": []}\n'
            'def homelab_summary():\n'
            '    return {"resources": [{"identity": {"canonical_id": "netbox:device:75"}, '
            '"inventory": {"name": "Compute Node A"}}]}\n'
            'def homelab_compute_capabilities():\n'
            '    return {"status": "STALE", "freshness": "STALE", "observed_at": "2026-09-01", '
            '"machines": [{"name": "Compute Node A", "role": "synthetic inference node"}]}\n'
            'def resolve_inference_node_labels(_inventory):\n'
            '    return {"netbox:device:75": "Compute Node A"}\n'
            'def format_inference_inventory_response(text, inventory, summary, gpu_telemetry=None):\n'
            '    if "where should" in text.casefold():\n'
            '        return "PLACEMENT:" + str(summary.get("capability_machines", [{}])[0].get("role"))\n'
            '    return "NODE_ACTIVITY:" + summary["resources"][0]["inventory"]["name"]\n',
            encoding='utf-8',
        )
        node_activity = direct_read(
            "What's Compute Node A doing right now?", 'synthetic-owner', 'owner'
        )
        assert node_activity.startswith('NODE_ACTIVITY:Compute Node A Observed hardware inventory lists Compute Node A.'), node_activity
        assert 'Last recorded role: synthetic inference node.' in node_activity
        assert 'treat its role and specifications as historical' in node_activity
        assert 'hardware inventory is stale; last observed 2026-09-01' in node_activity
        assert "Host CPU/GPU load and free VRAM are not connected." in node_activity
        running_activity = direct_read(
            'What is Compute Node A running?', 'synthetic-owner', 'owner'
        )
        assert running_activity.startswith('NODE_ACTIVITY:Compute Node A'), running_activity
        assert "can't check all the home computers" in direct_read(
            "What's Compute Node A doing right now?", 'synthetic-household', 'household'
        )
        placement_route = direct_read(
            'Where should I run another model?', 'synthetic-owner', 'owner'
        )
        assert placement_route == 'PLACEMENT:synthetic inference node', placement_route
        assert 'owner session' in direct_read(
            'Where should I run another model?', 'synthetic-household', 'household'
        )
        host_workload_route = direct_read(
            "What's running on Compute Node A right now? Be clear about guest visibility limits.",
            'synthetic-owner', 'owner'
        )
        assert 'couldn\'t verify Compute Node A as a current Proxmox host' in host_workload_route
        runtime_node_summary = {
            'status': 'PARTIAL',
            'proxmox_guest_visibility': {
                'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS',
                'endpoints': [{'source_identity': 'proxmox:site-a',
                               'status': 'HEALTHY', 'scope': 'SELECTED_GUESTS'}],
            },
            'resources': [
                {'name': 'Runtime Node A', 'runtime_status': 'online',
                 'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
                 'inventory': {'name': 'Runtime Node A'},
                 'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
                {'name': 'Runtime Services CT', 'runtime_status': 'running',
                 'identity': {'source_identities': {'proxmox': ['proxmox:site-a:lxc:803']}},
                 'runtime': {'type': 'lxc', 'node': 'pve-a', 'vmid': 803, 'status': 'running'}},
            ],
            'sources': [{'source': 'Proxmox', 'status': 'HEALTHY'}],
            'service_catalog': {'status': 'OK', 'services': []},
        }
        (adapter_dir / 'server.py').write_text(
            'def homelab_summary():\n    return ' + repr(runtime_node_summary) + '\n',
            encoding='utf-8',
        )
        runtime_node_workloads = direct_read(
            'Which Runtime Node A guests can HADES currently see, and what states are they in?',
            'synthetic-owner', 'owner'
        )
        assert 'Proxmox currently reports Runtime Node A online' in runtime_node_workloads, runtime_node_workloads
        assert 'Runtime Services CT (CT 803, running)' in runtime_node_workloads, runtime_node_workloads
        assert 'only selected guests' in runtime_node_workloads and 'may be incomplete' in runtime_node_workloads, runtime_node_workloads
        assert "doesn't enumerate application services" in runtime_node_workloads, runtime_node_workloads
        runtime_node_household = direct_read(
            'What is running on Runtime Node A right now?', 'synthetic-household', 'household'
        )
        assert "can't check all the home computers" in runtime_node_household.casefold(), runtime_node_household
        assert 'Runtime Node A' not in runtime_node_household and 'Proxmox' not in runtime_node_household, runtime_node_household
        private_host_summary = {
            'status': 'OK',
            'resources': [
                {'name': 'Private Runtime Host', 'runtime_status': 'online',
                 'identity': {'source_identities': {'proxmox': ['proxmox:site-a:node:pve-a']}},
                 'runtime': {'type': 'node', 'node': 'pve-a', 'status': 'online'}},
                {'name': 'Private Admin VM', 'runtime_status': 'running',
                 'identity': {'source_identities': {'proxmox': ['proxmox:site-a:qemu:101']}},
                 'runtime': {'type': 'qemu', 'node': 'pve-a', 'vmid': 101, 'status': 'running'}},
            ],
            'service_catalog': {'status': 'OK', 'services': []},
        }
        (adapter_dir / 'server.py').write_text(
            'def homelab_summary():\n    return ' + repr(private_host_summary) + '\n',
            encoding='utf-8',
        )
        household_host_query = direct_read(
            'What is running on Private Runtime Host right now?', 'synthetic-household', 'household'
        )
        assert household_host_query is None or not any(
            private_detail in household_host_query
            for private_detail in ('Private Runtime Host', 'Private Admin VM', 'pve-a', 'VM 101')
        ), household_host_query
        (adapter_dir / 'server.py').write_text(
            'def homelab_summary():\n'
            '    return {"status": "OK", "resources": ' + repr(core_vm_rows) + ', '
            '"sources": [{"source": "Proxmox", "status": "HEALTHY"}], '
            '"service_catalog": {"status": "OK", "services": []}}\n',
            encoding='utf-8',
        )
        core_placement_route = direct_read(
            'Which machine is running HADES?', 'synthetic-owner', 'owner'
        )
        assert 'VM 2802) is running on Synthetic Virtualization Host' in core_placement_route, core_placement_route
        household_placement = direct_read(
            'Which machine is running HADES?', 'synthetic-household', 'household'
        )
        assert "can't check all the home computers" in household_placement, household_placement
        assert 'Synthetic Virtualization Host' not in household_placement and 'VM 2802' not in household_placement, household_placement
    finally:
        if old_workdir is None:
            os.environ.pop('HADES_HERMES_WORKING_DIRECTORY', None)
        else:
            os.environ['HADES_HERMES_WORKING_DIRECTORY'] = old_workdir
print('PASS service-level status requires a matching Uptime Kuma monitor')
print('PASS stale, absent, and ambiguous service checks do not inherit host liveness')
print('PASS named Minecraft/Jellyfin health prompts route through the synthetic read-only homelab shortcut')

monitor_groups = groups([
    {'name': 'Minecraft Server', 'status': 'up', 'freshness': 'FRESH'},
    {'name': 'Search', 'status': 'down', 'freshness': 'FRESH'},
    {'name': 'Jellyfin', 'status': 'down', 'freshness': 'STALE'},
    {'name': 'LLDAP', 'status': 'up', 'freshness': 'UNKNOWN'},
    {'name': 'Malformed', 'status': 'unavailable', 'freshness': 'FRESH'},
])
assert monitor_groups['up'] == ['Minecraft Server'], monitor_groups
assert monitor_groups['down'] == ['Search'], monitor_groups
assert {item['name'] for item in monitor_groups['unknown']} == {'Jellyfin', 'LLDAP', 'Malformed'}, monitor_groups
print('PASS broad homelab summaries distinguish current probe failures from stale/unknown checks')

backup_root = Path(tempfile.mkdtemp(prefix='hades-proxmox-backup-route-'))
old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
old_spec_from_file = importlib.util.spec_from_file_location
old_module_from_spec = importlib.util.module_from_spec
old_homelab_tool_result = namespace['_hades_direct_homelab_tool_result']
backup_tool_calls = []
os.environ['HADES_HERMES_WORKING_DIRECTORY'] = str(backup_root)
importlib.util.spec_from_file_location = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    AssertionError('backup formatter must come from the active homelab MCP result')
)
importlib.util.module_from_spec = lambda _spec: (_ for _ in ()).throw(
    AssertionError('backup formatter must not import a cwd adapter')
)
namespace['_hades_direct_homelab_tool_result'] = lambda name: (
    backup_tool_calls.append(name)
    or {'status': 'PARTIAL', 'formatted_summary': 'Proxmox status: selected-scope partial.'}
)
try:
    backup_answer = direct_proxmox_backup(
        'Are my backups okay?', 'synthetic-owner', 'owner', 'session-key'
    )
    assert 'Proxmox status: selected-scope partial.' in backup_answer, backup_answer
    assert backup_tool_calls == ['homelab_backup_status'], backup_tool_calls
    assert 'Configured HADES backup checks: current.' in backup_answer, backup_answer
    infrastructure_backup_answer = direct_proxmox_backup(
        'Are my infrastructure backups okay right now, and what coverage cannot you verify?',
        'synthetic-owner', 'owner', 'session-key',
    )
    assert 'Proxmox status: selected-scope partial.' in infrastructure_backup_answer, infrastructure_backup_answer
    assert 'HADES BACKUP CHECKS' not in infrastructure_backup_answer, infrastructure_backup_answer
    assert 'securely tie that Backup Check request to this chat' not in infrastructure_backup_answer, infrastructure_backup_answer
    guest_scoped_backup_answer = direct_proxmox_backup(
        'Are my backups current? Report the latest per-guest task evidence and what you cannot verify.',
        'synthetic-owner', 'owner', 'session-key',
    )
    assert 'Proxmox status: selected-scope partial.' in guest_scoped_backup_answer, guest_scoped_backup_answer
    assert 'HADES BACKUP CHECKS' not in guest_scoped_backup_answer, guest_scoped_backup_answer
    assert 'securely tie that Backup Check request to this chat' not in guest_scoped_backup_answer, guest_scoped_backup_answer
    assert direct_proxmox_backup(
        'Are my backups okay?', 'synthetic-household', 'household', 'session-key'
    ) is None
    assert direct_proxmox_backup(
        'Run the backup now', 'synthetic-owner', 'owner', 'session-key'
    ) is None
finally:
    namespace['_hades_direct_homelab_tool_result'] = old_homelab_tool_result
    importlib.util.spec_from_file_location = old_spec_from_file
    importlib.util.module_from_spec = old_module_from_spec
    if old_workdir is None:
        os.environ.pop('HADES_HERMES_WORKING_DIRECTORY', None)
    else:
        os.environ['HADES_HERMES_WORKING_DIRECTORY'] = old_workdir
    import shutil
    shutil.rmtree(backup_root, ignore_errors=True)
print('PASS owner backup questions compose bounded Proxmox evidence with HADES coverage; household and write requests remain gated')

# A source exception must be a terminal unknown for recognized operational
# requests. Returning None here would let the model answer from stale chat or
# remembered inventory after the live read failed.
with tempfile.TemporaryDirectory(prefix='hades-failed-homelab-read-') as temp_root:
    adapter_dir = Path(temp_root) / 'integrations' / 'homelab-readonly'
    adapter_dir.mkdir(parents=True)
    (adapter_dir / 'server.py').write_text(
        'def homelab_summary():\n'
        '    raise RuntimeError("synthetic source unavailable")\n'
        'def homelab_inference_inventory():\n'
        '    raise RuntimeError("synthetic source unavailable")\n',
        encoding='utf-8',
    )
    old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
    os.environ['HADES_HERMES_WORKING_DIRECTORY'] = temp_root
    try:
        owner_unknown = direct_read(
            "What's Synthetic Inference Node A doing right now?", 'synthetic-owner', 'owner'
        )
        assert 'couldn\'t verify the current homelab sources' in owner_unknown, owner_unknown
        provenance_unknown = direct_read(
            'When was that checked?', 'synthetic-owner', 'owner',
            context_text='What is Synthetic Inference Node A doing right now?',
        )
        assert provenance_unknown.startswith(
            "I couldn't verify the current homelab sources"
        ), provenance_unknown
        household_unknown = direct_read(
            'Is Minecraft working?', 'synthetic-household', 'household'
        )
        assert "can't confirm whether the game server is working" in household_unknown
        assert 'synthetic source unavailable' not in household_unknown
    finally:
        if old_workdir is None:
            os.environ.pop('HADES_HERMES_WORKING_DIRECTORY', None)
        else:
            os.environ['HADES_HERMES_WORKING_DIRECTORY'] = old_workdir
print('PASS failed source reads remain explicit unknowns and cannot fall back to remembered live status')
