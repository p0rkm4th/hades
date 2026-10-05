#!/usr/bin/env python3
"""Exercise service-health answers against authoritative monitor evidence."""
from __future__ import annotations

import ast
import importlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import yaml


source = Path('hermes/sitecustomize.py').read_text(encoding='utf-8')
repository_root = Path.cwd().resolve()
tree = ast.parse(source)
view_source = repository_root / 'integrations' / 'homelab_views.py'
view_tree = ast.parse(view_source.read_text(encoding='utf-8'))
view_functions = {
    node.name: node for node in view_tree.body if isinstance(node, ast.FunctionDef)
}
assert set(view_functions) == {
    '_hades_homelab_availability_groups',
    '_hades_homelab_health_summary_response',
    '_hades_homelab_service_coverage_response',
    '_hades_homelab_provenance_response',
    '_hades_homelab_conflict_response',
}
assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in view_tree.body)
assert all(
    isinstance(node, ast.FunctionDef)
    or isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    and isinstance(node.value.value, str)
    for node in view_tree.body
), 'homelab view module must have no import or top-level runtime work'
inference_reader = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == '_hades_direct_homelab_inference_read'
)
freshness_assignment = next(
    node for node in ast.walk(inference_reader)
    if isinstance(node, ast.Assign)
    and any(
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name) and target.value.id == 'summary'
        and isinstance(target.slice, ast.Constant) and target.slice.value == 'capability_freshness'
        for target in node.targets
    )
)
assert ast.dump(freshness_assignment.value) == ast.dump(ast.parse(
    "hardware.get('freshness', 'UNKNOWN')", mode='eval'
).body), 'source read status must not be used as data freshness'
wanted = {
    '_hades_capability_matrix_path', '_hades_configured_homelab_records',
    '_hades_configured_homelab_aliases',
    '_hades_configured_homelab_alias_match', '_hades_is_homelab_intent',
    '_hades_service_health_target', '_hades_service_monitor_response',
    '_hades_load_homelab_views',
    '_hades_homelab_availability_groups',
    '_hades_broad_homelab_status_intent',
    '_hades_homelab_health_summary_response',
    '_hades_homelab_service_coverage_intent',
    '_hades_homelab_service_coverage_response',
    '_hades_homelab_provenance_followup', '_hades_homelab_provenance_response',
    '_hades_homelab_conflict_intent', '_hades_homelab_conflict_response',
    '_hades_homelab_guest_visibility_intent',
    '_hades_homelab_guest_visibility_response',
    '_hades_homelab_service_placement_intent',
    '_hades_homelab_service_placement_response',
    '_hades_homelab_resource_ranking_intent',
    '_hades_homelab_resource_ranking_response',
    '_hades_homelab_node_metrics_ranking_response',
    '_hades_homelab_proxmox_node_load_response',
    '_hades_homelab_proxmox_node_load_target',
    '_hades_homelab_guest_inventory_intent',
    '_hades_homelab_guest_inventory_response',
    '_hades_homelab_guest_index_host_target',
    '_hades_homelab_guest_index_workloads_on_host_response',
    '_hades_resolve_homelab_adapter_path',
    '_hades_homelab_core_guest_name_keys',
    '_hades_homelab_core_vm_placement_intent',
    '_hades_homelab_core_vm_placement_index_response',
    '_hades_homelab_core_vm_placement_response',
    '_hades_agent_zero_runtime_placement_response',
    '_hades_direct_homelab_agent_zero_placement_read',
    '_hades_homelab_gpu_execution_intent',
    '_hades_homelab_gpu_execution_response',
    '_hades_direct_homelab_gpu_execution_read',
    '_hades_direct_homelab_read',
    '_hades_endpoint_intent_before_provision',
    '_hades_service_endpoint_response',
    '_hades_endpoint_continuation_response',
    '_hades_direct_owner_location',
    '_hades_household_homelab_boundary_response',
}
functions = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in wanted
]
assert {node.name for node in functions} == wanted
namespace = {
    're': re,
    'os': os,
    'sys': sys,
    'importlib': importlib,
    'Path': Path,
    '_hades_agent_zero_available': lambda: True,
    '_hades_logger': type('Logger', (), {'warning': lambda *_args, **_kwargs: None})(),
    '_hades_live_proxmox_vm_rows': lambda: [],
    '_HADES_EXPLICIT_PUBLIC_RESEARCH_INTENT': re.compile(r'(?!)'),
    '_HADES_LIVE_WEB_INTENT': re.compile(r'\b(?:search|web)\b', re.I),
    '_HADES_HOMELAB_INTENT': re.compile(
        r'\b(?:homelab|server|node|computer|network|minecraft|hades)\b', re.I
    ),
}
namespace['__file__'] = str(repository_root / 'hermes' / 'sitecustomize.py')
exec(compile(ast.Module(body=functions, type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
target = namespace['_hades_service_health_target']
answer = namespace['_hades_service_monitor_response']
groups = namespace['_hades_homelab_availability_groups']
broad_status_intent = namespace['_hades_broad_homelab_status_intent']
health_summary_response = namespace['_hades_homelab_health_summary_response']
coverage_intent = namespace['_hades_homelab_service_coverage_intent']
coverage_response = namespace['_hades_homelab_service_coverage_response']
provenance_followup = namespace['_hades_homelab_provenance_followup']
provenance_response = namespace['_hades_homelab_provenance_response']
conflict_intent = namespace['_hades_homelab_conflict_intent']
conflict_response = namespace['_hades_homelab_conflict_response']

# Run the same-name wrappers from an unrelated CWD while pinning the selected
# integration root. These byte-for-byte goldens capture former hook behavior.
golden_availability = [
    {'name': 'Fresh up', 'status': 'up', 'freshness': 'FRESH'},
    {'name': 'Stale down', 'status': 'down', 'freshness': 'STALE'},
    {'name': 'Fresh down', 'status': 'down', 'freshness': 'FRESH'},
]
golden_health = {
    'status': 'PARTIAL', 'online_names': ['Synthetic Guest'],
    'availability_summary': [
        {'name': 'Old up', 'status': 'up', 'freshness': 'STALE'},
        {'name': 'Fresh down', 'status': 'down', 'freshness': 'FRESH'},
    ],
    'source_observations': [
        {'source': 'Synthetic Proxmox', 'status': 'AVAILABLE'},
        {'source': 'Synthetic NetBox', 'status': 'UNAVAILABLE'},
    ],
    'service_catalog': {'status': 'OK', 'coverage': 'PARTIAL', 'services': [{'name': 'X'}]},
    'proxmox_guest_visibility': {'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS'},
    'conflicts': [{'name': 'Synthetic Resource', 'reasons': ['NetBox intended differs from Proxmox runtime']}],
}
golden_coverage = {
    'status': 'PARTIAL', 'retrieved_at': '2026-10-04T12:00:00Z',
    'availability_summary': [
        {'name': 'Fresh up', 'status': 'up', 'freshness': 'FRESH'},
        {'name': 'Old down', 'status': 'down', 'freshness': 'STALE'},
    ],
    'service_catalog': {'status': 'OK', 'coverage': 'UNKNOWN', 'services': []},
    'proxmox_guest_visibility': {'status': 'UNKNOWN', 'scope': 'UNKNOWN'},
}
golden_provenance = {'source_observations': [
    {'source': 'Synthetic Proxmox', 'status': 'AVAILABLE', 'retrieved_at': '2026-10-04T12:00:00Z'},
    {'source': 'Synthetic Kuma', 'status': 'UNAVAILABLE'},
]}
golden_conflict = {'conflicts': [
    {'name': 'Synthetic Guest', 'reasons': [
        'Display label is shared by multiple records; they remain separate by stable source identity',
    ]},
    {'name': 'Synthetic Host', 'reasons': [
        'NetBox intended node differs from Proxmox runtime node',
    ]},
]}
old_cwd = Path.cwd()
original_integrations_root = os.environ.get('HADES_INTEGRATIONS_ROOT')
os.environ['HADES_INTEGRATIONS_ROOT'] = str(repository_root)
with tempfile.TemporaryDirectory(prefix='homelab-view-cwd-decoy-') as unrelated_cwd:
    os.chdir(unrelated_cwd)
    try:
        assert groups(golden_availability) == {
            'up': ['Fresh up'], 'down': ['Fresh down'],
            'unknown': [{'name': 'Stale down', 'last_status': 'down', 'freshness': 'STALE'}],
        }
        assert health_summary_response(golden_health) == (
            'Some configured homelab evidence needs attention. Failing configured checks: Fresh down. '
            '1 configured check(s) are stale or unknown. Proxmox reports 1 guest(s) running; this is '
            'power/runtime state, not application health. Sources disagree about Synthetic Resource. '
            'Proxmox guest visibility is selected_guests; unreported guest state remains unknown. '
            'Could not verify Synthetic NetBox in this read. Application-service placement coverage is '
            'missing, empty, or incomplete. Some unmonitored services remain unknown for application '
            'health. Backup contents and restoreability were not checked in this summary.'
        )
        assert coverage_response(golden_coverage) == (
            "The service catalog responded, but its total coverage is unknown, so I can't confirm that "
            'unlisted services are absent. Guest visibility is partial or unknown, so services on '
            'unreported guests remain unverified. Current probe state is unknown or stale for: Old down. '
            '1 configured probes responded, but that does not confirm application login or workload '
            'readiness. The source read completed at 2026-10-04T12:00:00Z.'
        )
        assert provenance_response(golden_provenance) == (
            'I refreshed the configured homelab sources for this answer. Synthetic Proxmox: available; '
            'read at 2026-10-04T12:00:00Z; Synthetic Kuma: unavailable; read time unavailable. These '
            'are source-read times, not proof that older observations remain live. NetBox describes '
            'intended inventory, Proxmox reports runtime state, and configured probes report availability; '
            'those sources are not interchangeable.'
        )
        assert conflict_response(golden_conflict) == (
            'The current sources report these inventory/runtime disagreements: Synthetic Host: NetBox '
            'intended node differs from Proxmox runtime node. I kept those records separate instead of '
            'choosing one source as universal truth. Shared display labels remain separate by stable '
            'source identity: Synthetic Guest: Display label is shared by multiple records; they remain '
            'separate by stable source identity.'
        )
    finally:
        os.chdir(old_cwd)
        if original_integrations_root is None:
            os.environ.pop('HADES_INTEGRATIONS_ROOT', None)
        else:
            os.environ['HADES_INTEGRATIONS_ROOT'] = original_integrations_root
guest_visibility_intent = namespace['_hades_homelab_guest_visibility_intent']
guest_visibility_response = namespace['_hades_homelab_guest_visibility_response']
placement_intent = namespace['_hades_homelab_service_placement_intent']
placement_response = namespace['_hades_homelab_service_placement_response']
ranking_intent = namespace['_hades_homelab_resource_ranking_intent']
ranking_response = namespace['_hades_homelab_resource_ranking_response']
guest_inventory_intent = namespace['_hades_homelab_guest_inventory_intent']
guest_inventory_response = namespace['_hades_homelab_guest_inventory_response']
workload_host_target = namespace['_hades_homelab_guest_index_host_target']
workloads_on_host_response = namespace['_hades_homelab_guest_index_workloads_on_host_response']
resolve_homelab_adapter_path = namespace['_hades_resolve_homelab_adapter_path']
core_placement_intent = namespace['_hades_homelab_core_vm_placement_intent']
core_placement_response = namespace['_hades_homelab_core_vm_placement_response']
os.environ['HADES_CORE_PROXMOX_GUEST_NAMES'] = 'synthetic-core-node'
agent_zero_placement = namespace['_hades_agent_zero_runtime_placement_response']
direct_agent_zero_placement = namespace['_hades_direct_homelab_agent_zero_placement_read']
gpu_execution_intent = namespace['_hades_homelab_gpu_execution_intent']
gpu_execution_response = namespace['_hades_homelab_gpu_execution_response']
direct_gpu_execution = namespace['_hades_direct_homelab_gpu_execution_read']
direct_read = namespace['_hades_direct_homelab_read']
endpoint_before_provision = namespace['_hades_endpoint_intent_before_provision']
endpoint_response = namespace['_hades_service_endpoint_response']
endpoint_continuation = namespace['_hades_endpoint_continuation_response']
direct_owner_location = namespace['_hades_direct_owner_location']
household_boundary = namespace['_hades_household_homelab_boundary_response']

with tempfile.TemporaryDirectory(prefix='hades-active-adapter-path-') as temp_root:
    root = Path(temp_root)
    selected = root / 'generated' / 'integrations' / 'homelab-readonly' / 'server.py'
    selected.parent.mkdir(parents=True)
    selected.write_text('# selected synthetic adapter\n', encoding='utf-8')
    decoy_root = root / 'working-copy'
    decoy = decoy_root / 'integrations' / 'homelab-readonly' / 'server.py'
    decoy.parent.mkdir(parents=True)
    decoy.write_text('# decoy synthetic adapter\n', encoding='utf-8')
    profile = root / 'profile' / 'profiles' / 'hades' / 'config.yaml'
    profile.parent.mkdir(parents=True)
    profile.write_text(json.dumps({'mcp_servers': {'homelab-readonly': {
        'args': [str(selected)],
    }}}), encoding='utf-8')
    old_root = os.environ.get('HADES_INTEGRATIONS_ROOT')
    old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
    os.environ['HADES_INTEGRATIONS_ROOT'] = str(root)
    os.environ['HADES_HERMES_WORKING_DIRECTORY'] = str(decoy_root)
    try:
        assert resolve_homelab_adapter_path() == selected
    finally:
        if old_root is None:
            os.environ.pop('HADES_INTEGRATIONS_ROOT', None)
        else:
            os.environ['HADES_INTEGRATIONS_ROOT'] = old_root
        if old_workdir is None:
            os.environ.pop('HADES_HERMES_WORKING_DIRECTORY', None)
        else:
            os.environ['HADES_HERMES_WORKING_DIRECTORY'] = old_workdir

assert coverage_intent('Which services can you not verify?')
assert coverage_intent('What homelab applications remain unknown?')
assert not coverage_intent('Is Minecraft working?')
assert broad_status_intent("What's down?")
assert namespace['_hades_is_homelab_intent']("What's down?")
assert broad_status_intent('Is everything okay with the homelab?')
assert broad_status_intent('How is the lab doing?')
assert namespace['_hades_is_homelab_intent']('Is everything okay with the homelab?')
assert not broad_status_intent('What changed since yesterday?')
healthy_checks_partial_coverage = health_summary_response({
    'status': 'OK',
    'online_names': ['Synthetic Guest A', 'Synthetic Guest B'],
    'availability_summary': [
        {'name': 'Synthetic Web Probe', 'status': 'up', 'freshness': 'FRESH'},
        {'name': 'Synthetic Old Probe', 'status': 'up', 'freshness': 'STALE'},
    ],
    'source_observations': [
        {'source': 'Synthetic Proxmox', 'status': 'AVAILABLE', 'retrieved_at': 'now'},
        {'source': 'Synthetic NetBox', 'status': 'AVAILABLE', 'retrieved_at': 'now'},
    ],
    'service_catalog': {'status': 'OK', 'coverage': 'EMPTY', 'services': []},
    'proxmox_guest_visibility': {'status': 'COMPLETE', 'scope': 'ALL_GUESTS'},
    'conflicts': [],
})
assert 'No failure is reported by fresh configured availability checks' in healthy_checks_partial_coverage
assert '2 guest(s) running' in healthy_checks_partial_coverage
assert 'power/runtime state, not application health' in healthy_checks_partial_coverage
assert 'Application-service placement coverage is missing, empty, or incomplete' in healthy_checks_partial_coverage
assert 'unmonitored services remain unknown for application health' in healthy_checks_partial_coverage
assert 'Backup contents and restoreability were not checked' in healthy_checks_partial_coverage
duplicate_label_summary = health_summary_response({
    'status': 'OK', 'online_names': ['Synthetic Guest'],
    'availability_summary': [{'name': 'Synthetic Probe', 'status': 'up', 'freshness': 'FRESH'}],
    'source_observations': [{'source': 'Synthetic Proxmox', 'status': 'AVAILABLE'}],
    'service_catalog': {'status': 'OK', 'coverage': 'COMPLETE'},
    'proxmox_guest_visibility': {'status': 'COMPLETE', 'scope': 'ALL_GUESTS'},
    'conflicts': [
        {'name': 'Synthetic Guest (VM 800)', 'reasons': ['Display label is shared by multiple records; they remain separate by stable source identity']},
        {'name': 'Synthetic Guest (VM 802)', 'reasons': ['Display label is shared by multiple records; they remain separate by stable source identity']},
    ],
})
assert 'Sources disagree about' not in duplicate_label_summary, duplicate_label_summary
assert 'Some records share display labels' in duplicate_label_summary, duplicate_label_summary
assert 'Some configured homelab evidence needs attention' not in duplicate_label_summary, duplicate_label_summary
partial_guest_scope = health_summary_response({
    'status': 'OK', 'online_names': ['Synthetic Guest A'],
    'availability_summary': [{'name': 'Synthetic Probe', 'status': 'up', 'freshness': 'FRESH'}],
    'source_observations': [{'source': 'Synthetic Proxmox', 'status': 'AVAILABLE'}],
    'service_catalog': {'status': 'OK', 'coverage': 'COMPLETE'},
    'proxmox_guest_visibility': {'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS'},
    'conflicts': [],
})
assert "can't confirm that the whole homelab is okay" in partial_guest_scope
assert 'Proxmox guest visibility is selected_guests' in partial_guest_scope
assert 'unreported guest state remains unknown' in partial_guest_scope
failed_source_health = health_summary_response({
    'status': 'PARTIAL', 'online_names': [],
    'availability_summary': [{'name': 'Synthetic App Check', 'status': 'down', 'freshness': 'FRESH'}],
    'source_observations': [{'source': 'Synthetic NetBox', 'status': 'UNAVAILABLE'}],
    'service_catalog': {'status': 'UNAVAILABLE', 'coverage': 'UNKNOWN'},
    'conflicts': [],
})
assert 'Some configured homelab evidence needs attention' in failed_source_health
assert 'Failing configured checks: Synthetic App Check' in failed_source_health
assert 'Could not verify Synthetic NetBox' in failed_source_health
assert guest_inventory_intent('What VMs are running?')
assert guest_inventory_intent('List all Proxmox containers')
assert not guest_inventory_intent('Are all VMs visible?')
assert not guest_inventory_intent('Is VM 202 running?')
assert workload_host_target("What's running on Synthetic Hypervisor right now?") == 'Synthetic Hypervisor'
assert workload_host_target('Which guests are on Synthetic Hypervisor?') == 'Synthetic Hypervisor'
assert workload_host_target("What's running on Proxmox?") == 'Proxmox'
host_inventory = {'proxmox_guest_inventory': {'status': 'COMPLETE', 'endpoints': [{
    'source_id': 'synthetic', 'status': 'COMPLETE',
    'visibility_status': 'COMPLETE', 'visibility_scope': 'ALL_GUESTS',
    'node_inventory_status': 'OBSERVED', 'truncated': False,
    'retrieved_at': 'synthetic-host-read',
    'nodes': [{'source_identity': 'proxmox:synthetic:node:hypervisor-a',
               'node': 'hypervisor-a', 'name': 'Synthetic Hypervisor', 'status': 'ONLINE'}],
    'guests': [
        {'source_identity': 'proxmox:synthetic:qemu:102',
         'node_identity': 'proxmox:synthetic:node:hypervisor-a', 'guest_type': 'qemu',
         'guest_id': '102', 'name': 'Synthetic VM', 'status': 'RUNNING'},
        {'source_identity': 'proxmox:synthetic:lxc:203',
         'node_identity': 'proxmox:synthetic:node:other', 'guest_type': 'lxc',
         'guest_id': '203', 'name': 'Other CT', 'status': 'STOPPED'},
    ],
}]}}
host_answer = workloads_on_host_response("What's running on Synthetic Hypervisor?", host_inventory, 'owner')
assert 'Synthetic Hypervisor as ONLINE' in host_answer, host_answer
assert 'Synthetic VM VM 102 (RUNNING)' in host_answer, host_answer
assert 'Other CT' not in host_answer, host_answer
assert 'do not establish application health' in host_answer, host_answer
assert workloads_on_host_response("What's running on Synthetic Hypervisor?", host_inventory, 'household') is not None
assert 'Complete effective VM.Audit scope' in workloads_on_host_response(
    "What's running on Proxmox?", host_inventory, 'owner'
)
host_inventory['proxmox_guest_inventory']['endpoints'][0]['guests'] = []
host_inventory['proxmox_guest_inventory']['endpoints'][0]['visibility_scope'] = 'SELECTED_GUESTS'
partial_host_answer = workloads_on_host_response("What's running on Synthetic Hypervisor?", host_inventory, 'owner')
assert 'does not establish that the node is empty' in partial_host_answer, partial_host_answer
assert core_placement_intent('Where is HADES Core running?')
assert core_placement_intent('Which host is running HADES?')
assert not core_placement_intent('How is HADES doing?')
assert gpu_execution_intent('Is the NVIDIA driver responding?')
assert gpu_execution_intent('Are the GPUs executing processes?')
assert gpu_execution_intent('Are the GPUs working?')
assert not gpu_execution_intent('Which GPUs are installed?')
gpu_execution_answer = gpu_execution_response({
    'status': 'READABLE', 'retrieved_at': 'synthetic-provider-read',
    'endpoints': [{
        'source_identity': 'inference:fast-lane', 'status': 'READABLE',
        'loaded_status': 'CURRENT', 'loaded_models': [{'name': 'synthetic-model'}],
    }],
}, {
    'status': 'PARTIAL', 'retrieved_at': 'synthetic-gpu-read',
    'endpoints': [
        {'inference_id': 'fast-lane', 'status': 'READABLE', 'devices': [{
            'index': 0, 'name': 'Synthetic GPU', 'gpu_utilization_percent': 92,
            'memory_free_mib': 2048, 'memory_total_mib': 16384,
        }]},
        {'inference_id': 'deep-lane', 'status': 'UNAVAILABLE'},
    ],
})
assert 'NVIDIA query responded' in gpu_execution_answer, gpu_execution_answer
assert '92% utilization' in gpu_execution_answer and '2048 MiB free' in gpu_execution_answer, gpu_execution_answer
assert 'Telemetry was unavailable for: deep-lane' in gpu_execution_answer, gpu_execution_answer
assert 'not proof that a requested workload completed' in gpu_execution_answer, gpu_execution_answer
assert 'provider reports resident model(s): synthetic-model' in gpu_execution_answer, gpu_execution_answer
assert 'no generation request was made' in gpu_execution_answer, gpu_execution_answer
assert 'driver health, GPU execution' in gpu_execution_answer, gpu_execution_answer
unknown_gpu_answer = gpu_execution_response(
    {'status': 'NOT_CONFIGURED', 'endpoints': []},
    {'status': 'NOT_CONFIGURED', 'endpoints': []},
)
assert 'driver health and actual GPU execution are unknown' in unknown_gpu_answer, unknown_gpu_answer
old_agent_zero_url = os.environ.get('AGENT_ZERO_URL')
os.environ['AGENT_ZERO_URL'] = 'http://127.0.0.1:7002/api/private-check'
try:
    gpu_registry_calls = []
    namespace['_hades_direct_homelab_tool_result'] = lambda name: (
        gpu_registry_calls.append(name)
        or ({'status': 'READABLE', 'endpoints': []} if name == 'homelab_inference_inventory'
            else {'status': 'NOT_CONFIGURED', 'endpoints': []})
    )
    direct_gpu_answer = direct_gpu_execution(
        'Is the NVIDIA driver responding?', 'synthetic-owner', 'owner'
    )
    assert 'driver health and actual GPU execution are unknown' in direct_gpu_answer, direct_gpu_answer
    assert gpu_registry_calls == ['homelab_gpu_telemetry', 'homelab_inference_inventory'], gpu_registry_calls
    gpu_registry_calls.clear()
    assert direct_gpu_execution(
        'Is the NVIDIA driver responding?', 'synthetic-household', 'household'
    ) is None
    assert not gpu_registry_calls, gpu_registry_calls
    agent_zero_answer = agent_zero_placement(
        'Where is Agent Zero running?',
        {'status': 'OK', 'coverage': 'EMPTY'}, 'owner',
    )
    assert 'loopback port 7002 on the HADES host' in agent_zero_answer, agent_zero_answer
    assert 'endpoint returned an HTTP response' in agent_zero_answer, agent_zero_answer
    assert 'catalog is reachable but empty' in agent_zero_answer, agent_zero_answer
    assert 'not Agent Zero delegation or task execution' in agent_zero_answer, agent_zero_answer
    assert '/api/private-check' not in agent_zero_answer, agent_zero_answer
    assert agent_zero_placement(
        'Where is Agent Zero running?', {'status': 'OK', 'coverage': 'EMPTY'}, 'household'
    ) is None
    agent_zero_registry_calls = []
    namespace['_hades_direct_homelab_tool_result'] = lambda name: (
        agent_zero_registry_calls.append(name)
        or {'service_catalog': {'status': 'OK', 'coverage': 'EMPTY'}}
    )
    direct_agent_zero_answer = direct_agent_zero_placement(
        'Where is Agent Zero running?', 'synthetic-owner', 'owner'
    )
    assert 'loopback port 7002 on the HADES host' in direct_agent_zero_answer, direct_agent_zero_answer
    assert agent_zero_registry_calls == ['homelab_summary'], agent_zero_registry_calls
    agent_zero_registry_calls.clear()
    assert direct_agent_zero_placement(
        'Where is Agent Zero running?', 'synthetic-household', 'household'
    ) is None
    assert not agent_zero_registry_calls, agent_zero_registry_calls
    os.environ.pop('AGENT_ZERO_URL', None)
    unconfigured_agent_zero = agent_zero_placement(
        'Where is Agent Zero running?', {'status': 'OK', 'coverage': 'EMPTY'}, 'owner'
    )
    assert 'no explicit Agent Zero endpoint configured' in unconfigured_agent_zero, unconfigured_agent_zero
    assert "catalog is reachable but empty" in unconfigured_agent_zero, unconfigured_agent_zero
    intended_agent_zero = agent_zero_placement(
        'Where is Agent Zero running?',
        {'status': 'OK', 'coverage': 'COMPLETE', 'services': [
            {'name': 'Agent Zero', 'parent_name': 'Synthetic Host'},
        ]}, 'owner',
    )
    assert 'NetBox lists Agent Zero on Synthetic Host as intended placement' in intended_agent_zero, intended_agent_zero
    ambiguous_agent_zero = agent_zero_placement(
        'Where is Agent Zero running?',
        {'status': 'OK', 'coverage': 'COMPLETE', 'services': [
            {'name': 'Agent Zero', 'parent_name': 'Synthetic Host A'},
            {'name': 'Agent Zero', 'parent_name': 'Synthetic Host B'},
        ]}, 'owner',
    )
    assert 'placement is ambiguous' in ambiguous_agent_zero, ambiguous_agent_zero
    os.environ['AGENT_ZERO_URL'] = 'not a url'
    invalid_agent_zero = agent_zero_placement(
        'Where is Agent Zero running?', {'status': 'UNKNOWN'}, 'owner'
    )
    assert 'configured Agent Zero endpoint is invalid' in invalid_agent_zero, invalid_agent_zero
finally:
    if old_agent_zero_url is None:
        os.environ.pop('AGENT_ZERO_URL', None)
    else:
        os.environ['AGENT_ZERO_URL'] = old_agent_zero_url
complete_guest_state = guest_inventory_response({
    'proxmox_guest_inventory': {
        'status': 'COMPLETE', 'endpoints': [{
            'source_id': 'synthetic', 'status': 'COMPLETE',
            'visibility_status': 'COMPLETE', 'visibility_scope': 'ALL_GUESTS',
            'retrieved_at': 'synthetic-guest-read', 'truncated': False,
            'guests': [
                {'source_identity': 'proxmox:synthetic:qemu:102', 'guest_type': 'qemu',
                 'guest_id': '102', 'name': 'Synthetic VM', 'node': 'Synthetic Node', 'status': 'RUNNING'},
                {'source_identity': 'proxmox:synthetic:lxc:203', 'guest_type': 'lxc',
                 'guest_id': '203', 'name': 'Synthetic CT', 'node': 'Synthetic Node', 'status': 'STOPPED'},
            ],
        }],
    },
})
assert 'Complete effective VM.Audit scope' in complete_guest_state, complete_guest_state
assert 'Synthetic VM (VM 102) on Synthetic Node' in complete_guest_state, complete_guest_state
assert 'Synthetic CT (CT 203) on Synthetic Node' in complete_guest_state, complete_guest_state
assert 'not application or service health' in complete_guest_state, complete_guest_state
core_placement = core_placement_response({
    'proxmox_guest_inventory': {
        'status': 'COMPLETE', 'endpoints': [{
            'status': 'COMPLETE', 'visibility_scope': 'ALL_GUESTS',
            'retrieved_at': 'synthetic-core-read', 'truncated': False,
            'guests': [{
            'name': 'synthetic-core-node', 'guest_type': 'qemu', 'guest_id': '202',
                'node': 'Synthetic Hypervisor', 'status': 'RUNNING',
            }],
        }],
    },
})
assert 'synthetic-core-node (VM 202) is running on Synthetic Hypervisor' in core_placement, core_placement
assert 'does not verify HADES application health' in core_placement, core_placement
partial_core_placement = core_placement_response({
    'proxmox_guest_inventory': {
        'status': 'PARTIAL', 'endpoints': [{
            'status': 'PARTIAL', 'visibility_scope': 'SELECTED_GUESTS',
            'guests': [{'name': 'synthetic-core-node', 'guest_type': 'qemu', 'guest_id': '202',
                        'node': 'Synthetic Hypervisor', 'status': 'RUNNING'}],
        }],
    },
})
assert 'other matching guests may be unreported' in partial_core_placement, partial_core_placement
assert 'no guest with a HADES Core name' in core_placement_response({
    'proxmox_guest_inventory': {'status': 'COMPLETE', 'endpoints': [{
        'status': 'COMPLETE', 'visibility_scope': 'ALL_GUESTS', 'guests': [],
    }]},
}), "a complete inventory without HADES Core must not invent placement"
partial_guest_state = guest_inventory_response({
    'proxmox_guest_inventory': {'status': 'PARTIAL', 'endpoints': [{
        'source_id': 'synthetic', 'status': 'PARTIAL', 'visibility_scope': 'SELECTED_GUESTS',
        'guests': [], 'truncated': False,
    }]},
})
assert 'does not establish an empty cluster' in partial_guest_state, partial_guest_state
coverage = coverage_response({
    'service_catalog': {'status': 'OK', 'coverage': 'EMPTY', 'services': []},
    'proxmox_guest_visibility': {'status': 'PARTIAL'},
    'availability_summary': [
        {'name': 'synthetic-web-probe', 'status': 'up', 'freshness': 'FRESH'},
        {'name': 'synthetic-stale-probe', 'status': 'up', 'freshness': 'STALE'},
    ],
    'retrieved_at': '2026-10-04T12:00:00Z',
})
assert 'catalog is reachable but empty' in coverage, coverage
assert 'services on unreported guests remain unverified' in coverage, coverage
assert 'configured probes responded' in coverage, coverage
assert 'does not confirm application login or workload readiness' in coverage, coverage
assert 'synthetic-stale-probe' in coverage, coverage
assert '2026-10-04T12:00:00Z' in coverage, coverage
coverage_without_explicit_empty_marker = coverage_response({
    'service_catalog': {'status': 'OK', 'services': [], 'truncated': False},
    'availability_summary': [
        {'name': 'synthetic-host-probe', 'status': 'up', 'freshness': 'FRESH'},
    ],
})
assert 'total coverage is unknown' in coverage_without_explicit_empty_marker, coverage_without_explicit_empty_marker
assert 'catalog is reachable but empty' not in coverage_without_explicit_empty_marker, coverage_without_explicit_empty_marker
assert 'configured probes responded' in coverage_without_explicit_empty_marker, coverage_without_explicit_empty_marker
partial_catalog_coverage = coverage_response({
    'service_catalog': {'status': 'OK', 'coverage': 'PARTIAL', 'services': [{'name': 'Synthetic'}], 'truncated': True},
})
assert 'partial or truncated' in partial_catalog_coverage, partial_catalog_coverage
assert 'returned 1 service record, but the read is partial or truncated' in partial_catalog_coverage, partial_catalog_coverage
assert 'catalog is reachable but empty' not in partial_catalog_coverage, partial_catalog_coverage
truncated_complete_catalog = coverage_response({
    'service_catalog': {'status': 'OK', 'coverage': 'COMPLETE', 'services': [{'name': 'Synthetic'}], 'truncated': True},
})
assert 'partial or truncated' in truncated_complete_catalog, truncated_complete_catalog
empty_with_rows = coverage_response({
    'service_catalog': {'status': 'OK', 'coverage': 'EMPTY', 'services': [{'name': 'Synthetic'}], 'truncated': False},
})
assert 'metadata conflicts' in empty_with_rows and 'reachable but empty' not in empty_with_rows, empty_with_rows
complete_without_rows = coverage_response({
    'service_catalog': {'status': 'OK', 'coverage': 'COMPLETE', 'services': [], 'truncated': False},
})
assert 'conflicts with its coverage state' in complete_without_rows, complete_without_rows
unavailable_stale_rows = coverage_response({
    'service_catalog': {'status': 'UNAVAILABLE', 'coverage': 'COMPLETE', 'services': [{'name': 'Stale Service'}], 'truncated': False},
})
assert 'not currently available' in unavailable_stale_rows and 'lists 1 application service' not in unavailable_stale_rows, unavailable_stale_rows
provenance_history = [
    {'role': 'user', 'content': "What's down?"},
    {'role': 'assistant', 'content': 'No fresh configured failures.'},
    {'role': 'user', 'content': 'How do you know that?'},
]
assert provenance_followup('How do you know that?', provenance_history)
assert not provenance_followup('How do you know that?', [])
provenance = provenance_response({'source_observations': [
    {'source': 'Synthetic Proxmox', 'status': 'READABLE', 'retrieved_at': '2026-10-04T12:00:00Z'},
    {'source': 'Synthetic NetBox', 'status': 'UNAVAILABLE'},
]})
assert 'Synthetic Proxmox: readable; read at 2026-10-04T12:00:00Z' in provenance, provenance
assert 'Synthetic NetBox: unavailable; read time unavailable' in provenance, provenance
assert 'not proof that older observations remain live' in provenance, provenance
assert conflict_intent('Do any sources disagree?')
assert namespace['_hades_is_homelab_intent']('Do any sources disagree?')
assert namespace['_hades_is_homelab_intent']('Which services can you not verify?')
conflict = conflict_response({'conflicts': [{
    'name': 'Synthetic Node',
    'reasons': ['NetBox intended node differs from Proxmox runtime node'],
}]})
assert 'Synthetic Node: NetBox intended node differs from Proxmox runtime node' in conflict, conflict
assert 'kept those records separate' in conflict, conflict
assert 'does not prove inventory coverage is complete' in conflict_response({'conflicts': []})
unavailable_conflict = conflict_response({
    'status': 'PARTIAL',
    'conflicts': [],
    'source_observations': [{'source': 'Synthetic NetBox', 'status': 'UNAVAILABLE'}],
})
assert "can't confirm whether the sources disagree" in unavailable_conflict, unavailable_conflict
assert 'Synthetic NetBox' in unavailable_conflict and 'does not establish that the sources agree' in unavailable_conflict, unavailable_conflict
known_conflict_partial_read = conflict_response({
    'status': 'PARTIAL',
    'conflicts': [{'name': 'Synthetic Node', 'reasons': ['intended and observed state differs']}],
    'source_observations': [{'source': 'Synthetic Kuma', 'status': 'UNAVAILABLE'}],
    'proxmox_guest_visibility': {'status': 'PARTIAL'},
})
assert 'Synthetic Node: intended and observed state differs' in known_conflict_partial_read, known_conflict_partial_read
assert 'Synthetic Kuma' in known_conflict_partial_read and 'guest visibility is partial or unknown' in known_conflict_partial_read, known_conflict_partial_read
assert 'does not mean the sources agree' in known_conflict_partial_read, known_conflict_partial_read
assert 'couldn\'t determine whether' in conflict_response(None)
assert 'conflict records were unavailable or malformed' in conflict_response({'conflicts': None})
label_collision_only = conflict_response({'conflicts': [{
    'name': 'Synthetic Guest (node qemu 100)',
    'reasons': ['Display label is shared by multiple records; they remain separate by stable source identity'],
}]})
assert 'no cross-source inventory disagreement' in label_collision_only, label_collision_only
assert 'Shared display labels remain separate by stable source identity' in label_collision_only, label_collision_only
assert 'inventory/runtime disagreements' not in label_collision_only, label_collision_only
mixed_conflicts = conflict_response({'conflicts': [
    {'name': 'Synthetic Guest', 'reasons': [
        'Display label is shared by multiple records; they remain separate by stable source identity',
    ]},
    {'name': 'Synthetic Host', 'reasons': [
        'NetBox intended node differs from Proxmox runtime node',
    ]},
]})
assert 'inventory/runtime disagreements: Synthetic Host' in mixed_conflicts, mixed_conflicts
assert 'Shared display labels remain separate by stable source identity: Synthetic Guest' in mixed_conflicts, mixed_conflicts
assert guest_visibility_intent('Are all VMs visible?')
assert namespace['_hades_is_homelab_intent']('Are all VMs visible?')
complete_visibility = guest_visibility_response({
    'proxmox_guest_visibility': {'status': 'COMPLETE', 'scope': 'ALL_GUESTS'},
    'source_observations': [{
        'source': 'Proxmox guest visibility:synthetic', 'status': 'COMPLETE',
        'retrieved_at': '2026-10-04T12:00:00Z',
    }],
})
assert 'all guests in scope' in complete_visibility, complete_visibility
assert 'effective-permission data' in complete_visibility, complete_visibility
assert '2026-10-04T12:00:00Z' in complete_visibility, complete_visibility
partial_visibility = guest_visibility_response({
    'proxmox_guest_visibility': {'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS'}
})
assert 'selected guests only' in partial_visibility, partial_visibility
assert placement_intent('Where is Agent Zero running?')
assert namespace['_hades_is_homelab_intent']('Where is Agent Zero running?')
intended_placement = placement_response('Where is Minecraft Server running?', {
    'service_catalog': {'status': 'OK', 'coverage': 'COMPLETE', 'services': [{
        'name': 'Minecraft Server', 'parent_name': 'Synthetic Host',
    }], 'truncated': False},
})
assert 'NetBox lists Minecraft Server on Synthetic Host' in intended_placement, intended_placement
assert 'does not establish whether the service is currently running or healthy' in intended_placement
unknown_placement = placement_response('Where is Agent Zero running?', {
    'service_catalog': {'status': 'OK', 'coverage': 'EMPTY', 'services': []},
})
assert 'catalog is reachable but empty' in unknown_placement, unknown_placement
assert 'remembered location' in unknown_placement, unknown_placement
placement_empty_with_rows = placement_response('Where is Minecraft running?', {
    'service_catalog': {'status': 'OK', 'coverage': 'EMPTY', 'services': [{'name': 'Minecraft'}], 'truncated': False},
})
assert 'contradictory completeness metadata' in placement_empty_with_rows, placement_empty_with_rows
placement_complete_without_rows = placement_response('Where is Minecraft running?', {
    'service_catalog': {'status': 'OK', 'coverage': 'COMPLETE', 'services': [], 'truncated': False},
})
assert 'contradictory completeness metadata' in placement_complete_without_rows, placement_complete_without_rows
partial_placement = placement_response('Where is Minecraft running?', {
    'service_catalog': {'status': 'OK', 'coverage': 'PARTIAL', 'services': [{'name': 'Synthetic'}], 'truncated': True},
})
assert 'partial or doesn\'t confirm complete coverage' in partial_placement, partial_placement
assert 'remembered location' in partial_placement, partial_placement
unknown_coverage_placement = placement_response('Where is Minecraft running?', {
    'service_catalog': {'status': 'OK', 'services': [], 'truncated': False},
})
assert 'doesn\'t confirm complete coverage' in unknown_coverage_placement, unknown_coverage_placement
assert 'catalog is reachable but empty' not in unknown_coverage_placement, unknown_coverage_placement
assert ranking_intent("What's the most loaded server?")
assert ranking_intent('What is using the most resources?')
assert namespace['_hades_is_homelab_intent']("What's the most loaded server?")
ranking = ranking_response({
    'resources': [
        {'name': 'Synthetic CPU Host', 'currently_online': True,
         'runtime': {'status': 'running', 'cpu': 0.9, 'mem': 8 * 1024**3, 'maxmem': 16 * 1024**3}},
        {'name': 'Synthetic Memory Host', 'currently_online': True,
         'runtime': {'status': 'running', 'cpu': 0.5, 'mem': 15 * 1024**3, 'maxmem': 20 * 1024**3}},
        {'name': 'Synthetic Status Only Host', 'runtime_status': 'online'},
        {'name': 'Synthetic Conflicting Host', 'currently_online': False,
         'runtime_status': 'running',
         'runtime': {'status': 'running', 'cpu': 0.99, 'mem': 19 * 1024**3, 'maxmem': 20 * 1024**3}},
        {'name': 'Synthetic Conflicting Stopped Host', 'currently_online': True,
         'runtime_status': 'stopped',
         'runtime': {'status': 'stopped', 'cpu': 0.98, 'mem': 18 * 1024**3, 'maxmem': 20 * 1024**3}},
        {'name': 'Synthetic Offline', 'currently_online': False,
         'runtime': {'status': 'stopped', 'cpu': 0.99, 'mem': 19 * 1024**3, 'maxmem': 20 * 1024**3}},
    ],
    'source_observations': [{'source': 'Proxmox synthetic', 'retrieved_at': 'synthetic-read-time'}],
})
assert 'Synthetic CPU Host at 90.0%' in ranking, ranking
assert 'Synthetic Memory Host at 15.0 / 20.0 GiB (75.0%)' in ranking, ranking
assert 'Synthetic Offline' not in ranking
assert 'Synthetic Conflicting Host at 99.0%' not in ranking
assert 'Synthetic Conflicting Stopped Host at 98.0%' not in ranking
assert 'host and guest readings are separate' in ranking
assert 'This compares 3 currently online Proxmox runtime record(s)' in ranking, ranking
assert 'conflicting current-status fields was excluded' in ranking, ranking
assert 'Proxmox source read completed at synthetic-read-time' in ranking
status_without_metrics = ranking_response({
    'resources': [{'name': 'Synthetic Online Without Metrics', 'currently_online': True}]
})
assert 'records are online, but they contain no comparable CPU or memory readings' in status_without_metrics
unknown_runtime_status = ranking_response({
    'resources': [{'name': 'Synthetic Unknown Status', 'runtime_status': 'UNKNOWN'}]
})
assert 'no rows with an explicit online/running status' in unknown_runtime_status
assert 'this does not establish that no machines are online' in unknown_runtime_status
synthetic_node_metrics = {
    'status': 'READABLE', 'endpoints': [{
        'status': 'AVAILABLE', 'truncated': False, 'nodes': [
            {'name': 'Synthetic Node A', 'status': 'ONLINE', 'cpu_fraction': 0.25,
             'memory_used_bytes': 8 * 1024**3, 'memory_total_bytes': 16 * 1024**3,
             'observed_at': 'synthetic-node-time-a'},
            {'name': 'Synthetic Node B', 'node': 'synthetic-node-b',
             'status': 'ONLINE', 'cpu_fraction': 0.75,
             'memory_used_bytes': 6 * 1024**3, 'memory_total_bytes': 12 * 1024**3,
             'observed_at': 'synthetic-node-time-b'},
            {'name': 'Synthetic Offline Node', 'status': 'OFFLINE', 'cpu_fraction': 0.99,
             'memory_used_bytes': 19 * 1024**3, 'memory_total_bytes': 20 * 1024**3},
        ],
    }],
}
node_metric_ranking = ranking_response({
    'resources': [], 'proxmox_node_metrics': synthetic_node_metrics,
})
assert 'Synthetic Node B at 75.0%' in node_metric_ranking, node_metric_ranking
assert 'Synthetic Offline Node' not in node_metric_ranking
assert 'synthetic-node-time-b' in node_metric_ranking
assert 'host/node sample(s) only' in node_metric_ranking
assert 'Guest readings are separate' in node_metric_ranking
unknown_node_metrics = ranking_response({
    'resources': [], 'proxmox_node_metrics': {'status': 'UNKNOWN', 'endpoints': []},
})
assert 'status and load are unknown; I can\'t rank host load' in unknown_node_metrics
assert 'because' not in unknown_node_metrics
missing_timestamp_metrics = ranking_response({
    'resources': [], 'proxmox_node_metrics': {'status': 'UNKNOWN', 'endpoints': [{
        'status': 'UNKNOWN', 'error_code': 'MISSING_SOURCE_TIMESTAMP', 'nodes': [],
    }]},
})
assert 'because a source read timestamp is missing' in missing_timestamp_metrics
node_load_response = namespace['_hades_homelab_proxmox_node_load_response']
node_load_target = namespace['_hades_homelab_proxmox_node_load_target']
assert node_load_target('How loaded is Synthetic Compute Alpha right now?') == 'Synthetic Compute Alpha'
assert node_load_target('How much CPU is on Synthetic Node B?') == 'Synthetic Node B'
assert node_load_target('What is Synthetic Node B load like?') == 'Synthetic Node B'
assert node_load_target('What models are available?') is None
specific_node_load = node_load_response(
    {'proxmox_node_metrics': synthetic_node_metrics}, 'synthetic-node-b'
)
assert 'synthetic-node-b online' in specific_node_load, specific_node_load
assert 'Host CPU reading is 75.0%' in specific_node_load, specific_node_load
assert 'Host memory is 6.0 / 12.0 GiB' in specific_node_load, specific_node_load
assert 'sampled at synthetic-node-time-b' in specific_node_load, specific_node_load
assert 'guest readings may overlap' in specific_node_load, specific_node_load
assert node_load_response(
    {'proxmox_node_metrics': synthetic_node_metrics}, 'Synthetic Offline Node'
).endswith('current host load is unverified.')
linked_host = {
    'proxmox_node_metrics': {'status': 'READABLE', 'endpoints': [{
        'status': 'AVAILABLE', 'nodes': [{
            'name': 'synthetic-compute-alpha (NetBox 2)', 'node': 'pve-node-1', 'status': 'ONLINE',
            'cpu_fraction': 0.1, 'observed_at': 'linked-host-time',
        }],
    }]},
}
assert 'Proxmox reports Synthetic Compute Alpha online' in node_load_response(linked_host, 'Synthetic Compute Alpha')
unmatched_host = node_load_response(linked_host, 'Unlisted Node')
assert 'no current Proxmox node sample uniquely matched that machine' in unmatched_host
linked_host['proxmox_node_metrics']['endpoints'][0]['nodes'].append({
    'name': 'synthetic-compute-alpha (NetBox 3)', 'node': 'pve-node-2', 'status': 'ONLINE',
    'cpu_fraction': 0.2, 'observed_at': 'second-linked-host-time',
})
assert 'multiple Proxmox node records match' in node_load_response(linked_host, 'Synthetic Compute Alpha')
direct_read_fn = next(
    node for node in functions
    if isinstance(node, ast.FunctionDef) and node.name == '_hades_direct_homelab_read'
)
assert any(
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == '_hades_homelab_proxmox_node_load_response'
    for node in ast.walk(direct_read_fn)
), 'direct named host load intent must reach the explicit Proxmox node-load response'

household_health = household_boundary('Are all the computers okay? Is Minecraft working?')
assert household_health == (
    "I can't verify the computers' live status from this account, so I can't say whether everything is okay. "
    "I can't confirm that Minecraft is online from an approved live status check."
), household_health
household_topology = household_boundary(
    'Which computer is having trouble, and where does HADES run?'
)
assert "can't verify the computers' live status" in household_topology, household_topology
assert "can't share internal host or network details" in household_topology, household_topology
assert all(
    secret not in household_topology
    for secret in ('Proxmox', 'NetBox', '192.168.', 'mcp__')
)
household_minecraft = household_boundary('Is the Minecraft server online?')
assert household_minecraft == (
    "I can't confirm that Minecraft is online from an approved live status check."
), household_minecraft
assert household_boundary('What does Minecraft do?') is None
assert household_boundary('Can you help me pick a Minecraft skin?') is None
run_conversation = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == '_hades_run_conversation'
)
boundary_call = next(
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == '_hades_household_homelab_boundary_response'
)
assert boundary_call
boundary_guard = next(
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.If)
    and any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == '_hades_household_homelab_boundary_response'
        for child in ast.walk(node)
    )
)
assert ast.unparse(boundary_guard.test) == (
    "getattr(self, '_hades_session_scope', '') == 'household'"
)
early_memory_call = next(
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == '_hades_direct_memory_response'
)
server_status_assignment = next(
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.Assign)
    and any(
        isinstance(target, ast.Name) and target.id == '_server_status_turn'
        for target in node.targets
    )
)
assert early_memory_call.lineno < boundary_call.lineno < server_status_assignment.lineno
assert any(
    isinstance(node, ast.Return)
    and isinstance(node.value, ast.Dict)
    and any(
        isinstance(key, ast.Constant)
        and key.value == 'api_calls'
        and isinstance(value, ast.Constant)
        and value.value == 0
        for key, value in zip(node.value.keys, node.value.values)
    )
    for node in ast.walk(boundary_guard)
)

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
assert endpoint_before_provision('What is the IP address of management-node?') is False
assert 'first call the read-only homelab_summary' in source
assert 'asks_to_provision' in source
assert 'Owner service endpoint inventory read completed without model invocation' in source
assert 'Owner endpoint-request follow-up closed without model invocation' in source

request = 'Can you give me the Minecraft server IP and port for the firewall?'
assert 'couldn\'t find a matching service record' in endpoint_response(
    request, {'status': 'OK', 'services': []}, 'owner'
)
assert 'service inventory is incomplete' in endpoint_response(
    request, {'status': 'PARTIAL', 'services': []}, 'owner'
)
assert 'couldn\'t verify a server address or port' in endpoint_response(
    request, {'status': 'UNAVAILABLE', 'services': [], 'limitation': 'NetBox timed out.'}, 'owner'
)
assert endpoint_response(request, {'status': 'OK', 'services': []}, 'household') is None
assert 'multiple matching service records' in endpoint_response(
    'Can you give me the Minecraft IP and port for the firewall?', {
    'status': 'OK', 'services': [
        {'name': 'Minecraft Server'}, {'name': 'Minecraft RCON'},
    ],
}, 'owner')
assert 'doesn\'t give one clear address and port' in endpoint_response(request, {
    'status': 'OK', 'services': [{
        'name': 'Minecraft Server', 'addresses': [], 'port_mappings': ['tcp/25565'],
    }],
}, 'owner')
recorded = endpoint_response(request, {
    'status': 'OK', 'services': [{
        'name': 'Minecraft Server', 'parent_name': 'management-node',
        'addresses': ['192.0.2.10'], 'port_mappings': ['tcp/25565'],
    }],
}, 'owner')
assert '`192.0.2.10`' in recorded and 'tcp/25565' in recorded, recorded
assert 'doesn\'t verify that the service is running' in recorded, recorded
assert 'haven\'t changed the firewall' in recorded, recorded
dogfood_history = [
    {'role': 'user', 'content': request},
    {'role': 'assistant', 'content': endpoint_response(
        request, {'status': 'OK', 'services': []}, 'owner'
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

unmonitored = answer('Is Jellyfin healthy enough for tonight?', fresh_minecraft)
assert 'couldn\'t verify a current Uptime Kuma service monitor matching jellyfin' in unmonitored, unmonitored
assert 'Proxmox host or VM being online does not show' in unmonitored, unmonitored
assert "can't call it healthy" in unmonitored, unmonitored

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
        '    return {"resources": [{"name": "Minecraft Server", '
        '"runtime_status": "NOT_OBSERVED", "currently_online": False, '
        '"availability": {"name": "Minecraft Server", "status": "up", '
        '"last_updated": "2026-09-27T12:00:00Z"}, '
        '"availability_freshness": "FRESH"}], '
        '"service_catalog": {"status": "OK", "coverage": "COMPLETE", "truncated": False, "services": [{'
        '"name": "Minecraft Server", "parent_name": "Test Host", '
        '"addresses": ["192.0.2.10"], "port_mappings": ["tcp/25565"]}]}}\n',
        encoding='utf-8',
    )
    matrix_path = Path(temp_root) / 'hades-infra' / 'inventory' / 'capability-matrix.yaml'
    matrix_path.parent.mkdir(parents=True)
    matrix_path.write_text(
        'machines:\n'
        '  - name: compute-alpha\n'
        '    aliases: ["alpha node"]\n',
        encoding='utf-8',
    )
    old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
    old_matrix = os.environ.get('HADES_CAPABILITY_MATRIX_FILE')
    old_hermes_home = os.environ.get('HERMES_HOME')
    os.environ['HADES_HERMES_WORKING_DIRECTORY'] = temp_root
    os.environ.pop('HADES_CAPABILITY_MATRIX_FILE', None)
    os.environ['HERMES_HOME'] = str(Path(temp_root) / 'hermes-home')
    def synthetic_registry_read(tool_name, _args=None):
        if tool_name != 'homelab_summary':
            return {'status': 'UNKNOWN', 'machines': []}
        adapter_path = adapter_dir / 'server.py'
        spec = importlib.util.spec_from_file_location('synthetic_service_registry', adapter_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        summary = module.homelab_summary()
        summary.setdefault('resources', []).append({
            'name': 'Synthetic Host', 'currently_online': True,
            'runtime': {
                'status': 'running', 'cpu': 0.9,
                'mem': 8 * 1024**3, 'maxmem': 16 * 1024**3,
            },
        })
        summary['source_observations'] = [
            {'source': 'Synthetic Proxmox', 'status': 'READABLE', 'retrieved_at': 'synthetic-freshness-time'},
            {'source': 'Proxmox synthetic', 'status': 'READABLE', 'retrieved_at': 'synthetic-proxmox-time'},
        ]
        summary['conflicts'] = [{
            'name': 'Synthetic Node',
            'reasons': ['NetBox intended node differs from Proxmox runtime node'],
        }]
        summary['proxmox_guest_visibility'] = {
            'status': 'PARTIAL', 'scope': 'SELECTED_GUESTS',
        }
        summary['proxmox_guest_inventory'] = {'status': 'COMPLETE', 'endpoints': [{
            'source_id': 'synthetic', 'status': 'COMPLETE',
            'visibility_status': 'COMPLETE', 'visibility_scope': 'ALL_GUESTS',
            'node_inventory_status': 'OBSERVED', 'truncated': False,
            'retrieved_at': 'synthetic-host-read',
            'nodes': [{'source_identity': 'proxmox:synthetic:node:synthetic-hypervisor',
                       'node': 'synthetic-hypervisor', 'name': 'Synthetic Hypervisor', 'status': 'ONLINE'}],
            'guests': [{'source_identity': 'proxmox:synthetic:qemu:902',
                        'node_identity': 'proxmox:synthetic:node:synthetic-hypervisor',
                        'guest_type': 'qemu', 'guest_id': '902', 'name': 'Guested App',
                        'status': 'RUNNING'}],
        }]}
        return summary

    namespace['_hades_direct_homelab_tool_result'] = synthetic_registry_read
    try:
        owner_coverage = direct_read(
            'Which services can you not verify?', 'synthetic-owner', 'owner'
        )
        assert 'service catalog' in owner_coverage, owner_coverage
        assert 'service catalog lists 1 application service' in owner_coverage, owner_coverage
        assert 'No configured service-check observations' in owner_coverage, owner_coverage
        assert direct_read(
            'Which services can you not verify?', 'synthetic-household', 'household'
        ) is None
        assert 'only in an owner session' in direct_read(
            'What VMs are running?', 'synthetic-household', 'household'
        )
        owner_down = direct_read("What's down?", 'synthetic-owner', 'owner')
        assert 'No fresh configured probe is reporting a failure' in owner_down, owner_down
        assert 'unmonitored services remain unknown' in owner_down, owner_down
        owner_overall = direct_read(
            'Is everything okay with the homelab?', 'synthetic-owner', 'owner'
        )
        assert 'Some configured homelab evidence needs attention' in owner_overall, owner_overall
        assert 'Sources disagree about Synthetic Node' in owner_overall, owner_overall
        assert 'Backup contents and restoreability were not checked' in owner_overall, owner_overall
        assert 'Live Proxmox currently reports:' not in owner_overall, owner_overall

        view_module = namespace['_hades_load_homelab_views']()
        owner_view_names = (
            '_hades_homelab_health_summary_response',
            '_hades_homelab_service_coverage_response',
            '_hades_homelab_provenance_response',
            '_hades_homelab_conflict_response',
        )
        original_owner_views = {name: getattr(view_module, name) for name in owner_view_names}
        owner_view_calls = []
        for name, original in original_owner_views.items():
            def track_owner_view(summary, _name=name, _original=original):
                owner_view_calls.append(_name)
                return _original(summary)
            setattr(view_module, name, track_owner_view)
        household_overall = direct_read(
            'Is everything okay with the homelab?', 'synthetic-household', 'household'
        )
        assert household_overall == household_boundary(
            'Is everything okay with the homelab?'
        ), household_overall
        assert direct_read("What's down?", 'synthetic-household', 'household') == household_boundary(
            "What's down?"
        )
        assert direct_read(
            'Which services can you not verify?', 'synthetic-household', 'household'
        ) is None
        assert direct_read(
            'How do you know that?', 'synthetic-household', 'household',
            conversation_history=provenance_history,
        ) is None
        assert direct_read(
            'Do any sources disagree?', 'synthetic-household', 'household'
        ) is None
        assert owner_view_calls == [], f'household route invoked owner renderers: {owner_view_calls}'
        for name, original in original_owner_views.items():
            setattr(view_module, name, original)
        owner_provenance = direct_read(
            'How do you know that?', 'synthetic-owner', 'owner',
            conversation_history=provenance_history,
        )
        assert 'Synthetic Proxmox: readable; read at synthetic-freshness-time' in owner_provenance, owner_provenance
        owner_conflicts = direct_read(
            'Do any sources disagree?', 'synthetic-owner', 'owner'
        )
        assert 'Synthetic Node: NetBox intended node differs from Proxmox runtime node' in owner_conflicts, owner_conflicts
        assert direct_read(
            'Do any sources disagree?', 'synthetic-household', 'household'
        ) is None
        owner_scope = direct_read('Are all VMs visible?', 'synthetic-owner', 'owner')
        assert 'selected guests only' in owner_scope, owner_scope
        household_scope = direct_read(
            'Are all VMs visible?', 'synthetic-household', 'household'
        )
        assert 'internal guest inventory or permission details' in household_scope, household_scope
        host_workloads = direct_read(
            "What's running on Synthetic Hypervisor?", 'synthetic-owner', 'owner'
        )
        assert 'Guested App VM 902 (RUNNING)' in host_workloads, host_workloads
        assert direct_read(
            "What's running on Synthetic Hypervisor?", 'synthetic-household', 'household'
        ).startswith('Detailed host and guest placement is available only in an owner session.'), 'household host details leaked'
        owner_placement = direct_read(
            'Where is Minecraft Server running?', 'synthetic-owner', 'owner'
        )
        assert 'NetBox lists Minecraft Server on Test Host' in owner_placement, owner_placement
        household_placement = direct_read(
            'Where is Minecraft Server running?', 'synthetic-household', 'household'
        )
        assert 'only in an owner session' in household_placement, household_placement
        owner_rank = direct_read(
            "What's the most loaded server?", 'synthetic-owner', 'owner'
        )
        assert 'Synthetic Host at 90.0%' in owner_rank and 'Proxmox source read' in owner_rank, owner_rank
        household_rank = direct_read(
            "What's the most loaded server?", 'synthetic-household', 'household'
        )
        assert 'only in an owner session' in household_rank, household_rank
        assert namespace['_hades_configured_homelab_alias_match'](
            'is alpha node healthy?'
        ) == 'compute-alpha'
        assert namespace['_hades_is_homelab_intent'](
            'is compute-alpha healthy?'
        )
        household_named_host = household_boundary('Is compute-alpha okay?')
        assert household_named_host and 'compute-alpha' not in household_named_host
        assert 'can\'t verify current infrastructure status' in household_named_host
        matrix_path.chmod(0o666)
        assert namespace['_hades_configured_homelab_alias_match'](
            'is compute-alpha healthy?'
        ) is None
        matrix_path.chmod(0o600)
        routed_up = direct_read('Is Minecraft healthy enough for tonight?', 'synthetic-owner', 'owner')
        assert "Uptime Kuma's configured check for Minecraft Server is up." in routed_up, routed_up
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
        assert 'Packet-loss, throughput, and historical comparison data are unavailable' in routed_network, routed_network
        assert 'cannot identify a network bottleneck or trend from this evidence' in routed_network, routed_network
    finally:
        if old_matrix is None:
            os.environ.pop('HADES_CAPABILITY_MATRIX_FILE', None)
        else:
            os.environ['HADES_CAPABILITY_MATRIX_FILE'] = old_matrix
        if old_hermes_home is None:
            os.environ.pop('HERMES_HOME', None)
        else:
            os.environ['HERMES_HOME'] = old_hermes_home
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

agent_method = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_run_conversation"
)
agent_zero_route_lines = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_agent_zero_placement_read"
]
gpu_execution_route_lines = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_gpu_execution_read"
]
generic_route_lines = [
    node.lineno for node in ast.walk(agent_method)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_read"
]
assert (
    agent_zero_route_lines and gpu_execution_route_lines and generic_route_lines
    and min(agent_zero_route_lines) < max(generic_route_lines)
    and min(gpu_execution_route_lines) < max(generic_route_lines)
)
print('PASS owner Agent Zero placement uses the bounded endpoint route before generic model/tool handling')
print('PASS owner GPU execution questions distinguish fixed-command driver telemetry from provider residency')
