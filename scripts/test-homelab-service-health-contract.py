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
import types
from datetime import datetime, timezone
from pathlib import Path


source = Path('hermes/sitecustomize.py').read_text(encoding='utf-8')
tree = ast.parse(source)
wanted = {
    '_hades_service_health_target', '_hades_service_monitor_response',
    '_hades_homelab_availability_groups', '_hades_direct_homelab_read',
    '_hades_homelab_workloads_on_host_response',
    '_hades_homelab_core_vm_placement_response',
    '_hades_endpoint_intent_before_provision',
    '_hades_service_endpoint_response',
    '_hades_service_placement_response',
    '_hades_endpoint_continuation_response',
    '_hades_direct_owner_location',
    '_hades_direct_proxmox_backup_read',
    '_hades_homelab_name_key',
    '_hades_homelab_target_from_question',
}
functions = [
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in wanted
]
assert {node.name for node in functions} == wanted
namespace = {
    're': re,
    'os': os,
    'Path': Path,
    '_hades_live_proxmox_vm_rows': lambda: [],
    '_hades_phase2_backup_freshness_response': lambda *_args, **_kwargs: None,
    '_HADES_EXPLICIT_PUBLIC_RESEARCH_INTENT': re.compile(r'(?!)'),
    'importlib': importlib,
    'sys': sys,
    '_hades_logger': type('Log', (), {'warning': staticmethod(lambda *_args, **_kwargs: None)})(),
    '_hades_phase2_backup_response': lambda *_args, **_kwargs: 'Configured HADES backup checks: current.',
}
exec(compile(ast.Module(body=functions, type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
intent_assignment = next(
    node for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == '_HADES_HOMELAB_INTENT' for target in node.targets)
)
exec(compile(ast.Module(body=[intent_assignment], type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
homelab_intent = namespace['_HADES_HOMELAB_INTENT']
for prompt in (
    'Is everything okay?', 'What is down?', 'Anything dying?', "What's fucked?",
    'Which computer is having trouble?', "Why's shit slow?", 'What changed since yesterday?',
    'Are all the computers okay?', 'Is the homelab okay?', 'Are my computers okay?',
    'Is Minecraft working?',
):
    assert homelab_intent.search(prompt), f'owner homelab health intent missed {prompt!r}'
target = namespace['_hades_service_health_target']
answer = namespace['_hades_service_monitor_response']
groups = namespace['_hades_homelab_availability_groups']
workloads_on_host = namespace['_hades_homelab_workloads_on_host_response']
core_vm_placement = namespace['_hades_homelab_core_vm_placement_response']
direct_read = namespace['_hades_direct_homelab_read']
direct_proxmox_backup = namespace['_hades_direct_proxmox_backup_read']
endpoint_before_provision = namespace['_hades_endpoint_intent_before_provision']
endpoint_response = namespace['_hades_service_endpoint_response']
placement_response = namespace['_hades_service_placement_response']
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
assert 'first call the read-only homelab_summary' in source
assert 'asks_to_provision' in source
assert 'Owner service endpoint inventory read completed without model invocation' in source
assert 'Owner endpoint-request follow-up closed without model invocation' in source

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
assert namespace['_hades_homelab_target_from_question']('Is everything okay?') is None

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
assert 'Runtime Node A online' in host_workloads and 'Dinner VM (qemu, running)' in host_workloads
assert 'Unrelated CT' not in host_workloads and "Other source state is partial or unknown" in host_workloads
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
    {'name': 'Erebus', 'runtime_status': 'online',
     'identity': {'source_identities': {'proxmox': ['proxmox:erebus:node:erebus']}},
     'runtime': {'type': 'node', 'node': 'erebus', 'status': 'online'}},
    {'name': 'hades-core', 'runtime_status': 'stopped',
     'identity': {'source_identities': {'proxmox': ['proxmox:erebus:qemu:800']}},
     'runtime': {'type': 'qemu', 'node': 'erebus', 'vmid': 800, 'status': 'stopped'}},
    {'name': 'hades-core', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:erebus:qemu:802']}},
     'runtime': {'type': 'qemu', 'node': 'erebus', 'vmid': 802, 'status': 'running'}},
    {'name': 'hades-core', 'runtime_status': 'running',
     'identity': {'source_identities': {'proxmox': ['proxmox:site-b:qemu:802']}},
     'runtime': {'type': 'qemu', 'node': 'erebus', 'vmid': 802, 'status': 'running'}},
]
core_vm_answer = core_vm_placement('Which machine is running HADES?', core_vm_rows)
assert '3 guests matching HADES Core' in core_vm_answer and 'VM 800) is stopped on Erebus' in core_vm_answer
assert 'VM 802) is running on Erebus' in core_vm_answer and 'application health' in core_vm_answer
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
        '    import os\n'
        '    if os.environ.get("HADES_TEST_NO_GAME_MONITOR") == "1":\n'
        '        return {"resources": [], "service_catalog": {"status": "OK", "coverage": "EMPTY", "services": []}}\n'
        '    return {"resources": [{"name": "Minecraft Server", '
        '"runtime_status": "NOT_OBSERVED", "currently_online": False, '
        '"availability": {"name": "Minecraft Server", "status": "up", '
        '"last_updated": "2026-09-27T12:00:00Z"}, '
        '"availability_freshness": "FRESH"}], '
        '"service_catalog": {"status": "OK", "coverage": "COMPLETE", "services": [{'
        '"name": "Minecraft Server", "parent_name": "Test Host", '
        '"addresses": ["192.0.2.10"], "port_mappings": ["tcp/25565"]}]}}\n',
        encoding='utf-8',
    )
    old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
    os.environ['HADES_HERMES_WORKING_DIRECTORY'] = temp_root
    try:
        routed_up = direct_read('Is Minecraft healthy enough for tonight?', 'synthetic-owner', 'owner')
        assert "Uptime Kuma's configured check for Minecraft Server is up." in routed_up, routed_up
        household_game_status = direct_read(
            'Is Minecraft working?', 'synthetic-household', 'household'
        )
        assert 'configured game-server check is responding' in household_game_status
        assert 'Test Host' not in household_game_status and '192.0.2.' not in household_game_status
        os.environ['HADES_TEST_NO_GAME_MONITOR'] = '1'
        try:
            missing_game_check = direct_read(
                'Is Minecraft working?', 'synthetic-household', 'household'
            )
        finally:
            os.environ.pop('HADES_TEST_NO_GAME_MONITOR', None)
        assert "can't confirm whether the game server is working from the current check" in missing_game_check, missing_game_check
        assert 'Proxmox' not in missing_game_check and 'Test Host' not in missing_game_check, missing_game_check
        assert 'couldn\'t find a matching service record' in direct_read(
            'Where is Agent Zero?', 'synthetic-owner', 'owner'
        )
        assert direct_read('Where is Agent Zero?', 'synthetic-household', 'household') is None
        assert "can't verify private infrastructure or computer status" in direct_read(
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
        assert 'Packet-loss, throughput, and historical comparison data are unavailable' in routed_network, routed_network
        assert 'cannot identify a network bottleneck or trend from this evidence' in routed_network, routed_network

        def write_broad_summary(monitors, **overrides):
            summary = {
                'status': 'OK',
                'online_names': ['HADES Core'],
                'inventory_only_names': [],
                'availability_summary': monitors,
                'resources': [{
                    'name': 'HADES Core', 'runtime_status': 'running',
                    'currently_online': True, 'runtime': {'vmid': 802},
                    'availability': None, 'availability_observations': [],
                    'availability_freshness': 'UNKNOWN', 'conflicts': [],
                }],
                'conflicts': [], 'identity_warnings': [], 'errors': [],
                'service_catalog': {'status': 'OK', 'services': []},
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

        write_broad_summary([])
        no_coverage = direct_read(
            'Are there any blockers in the homelab?', 'synthetic-owner', 'owner'
        )
        assert "No service availability observations are available, so I can't confirm service health." in no_coverage, no_coverage
        assert 'No blocker was reported by the configured live sources.' not in no_coverage, no_coverage

        write_broad_summary([{
            'name': 'HADES Core', 'status': 'up', 'freshness': 'FRESH',
        }])
        covered = direct_read(
            'Are there any blockers in the homelab?', 'synthetic-owner', 'owner'
        )
        assert 'No blocker was reported by the configured live sources.' in covered, covered
        assert 'A responding probe does not prove application login' in covered, covered
        everything_ok = direct_read('Is everything okay?', 'synthetic-owner', 'owner')
        assert 'Live inference reads: Test Fast API responding (1 catalog models; 0 reported loaded)' in everything_ok, everything_ok
        assert 'Inference-worker health was not independently verified' not in everything_ok, everything_ok
        for prompt in (
            'Is everything okay?', 'What is down?', 'Anything dying?', "What's fucked?",
            'Which computer is having trouble?', "Why's shit slow?", 'What changed since yesterday?',
        ):
            answer_text = direct_read(prompt, 'synthetic-owner', 'owner')
            assert answer_text, f'direct owner homelab status route missed {prompt!r}'
            if prompt == 'What changed since yesterday?':
                assert 'no historical homelab snapshot or change-event source is configured' in answer_text
        household_overall = direct_read('What is down?', 'synthetic-household', 'household')
        assert "can't verify private infrastructure or computer status" in household_overall, household_overall
        assert 'Proxmox' not in household_overall and 'NetBox' not in household_overall, household_overall
        assert direct_read('Is everything okay?', 'synthetic-household', 'household') == household_overall
        for prompt in ('Is the homelab okay?', 'Are my computers okay?', 'Is Tartarus alive?', "What's Tartarus doing?"):
            restricted = direct_read(prompt, 'synthetic-household', 'household')
            assert "can't verify private infrastructure or computer status" in restricted, restricted
            assert 'Tartarus' not in restricted and 'Proxmox' not in restricted, restricted
        write_broad_summary(
            [{'name': 'service-netbox', 'status': 'down', 'freshness': 'FRESH'}],
            sources=[{'source': 'NetBox', 'status': 'HEALTHY'}],
            resources=[{'name': 'service-netbox', 'identity': {'canonical_id': None},
                        'availability': {'name': 'service-netbox', 'status': 'down'}}],
        )
        disagreement = direct_read('What is down?', 'synthetic-owner', 'owner')
        assert 'The NetBox inventory API responded to this read' in disagreement, disagreement
        assert 'target has no verified identity link' in disagreement, disagreement
        assert 'Live inference reads: Test Fast API responding' in disagreement, disagreement
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
        assert 'Current source reads unavailable or degraded: NetBox.' in source_outage, source_outage
        assert 'Proxmox' in source_outage and 'Uptime Kuma' in source_outage, source_outage
        assert 'unreported nodes remain unknown' in source_outage, source_outage
        assert 'Optional Source' not in source_outage, source_outage
        write_broad_summary(
            [],
            inventory_only_names=['GPU Node'],
            source_counts={'identity_unlinked_resources': 3},
            resources=[
                {'name': 'Lab Host', 'runtime_status': 'online', 'currently_online': True,
                 'runtime': {'status': 'online', 'mem': 8, 'maxmem': 16, 'disk': 20, 'maxdisk': 40}},
                {'name': 'App Guest', 'runtime_status': 'running', 'currently_online': True,
                 'runtime': {'name': 'ignored', 'vmid': 803, 'node': 'Lab Host', 'status': 'running',
                             'mem': 4, 'maxmem': 8, 'disk': 10, 'maxdisk': 20}},
            ],
        )
        formatted = direct_read('Give me a detailed homelab status', 'synthetic-owner', 'owner')
        assert 'Lab Host host' in formatted and 'App Guest VM 803 on Lab Host' in formatted, formatted
        assert 'None VM None' not in formatted, formatted
        assert 'no linked Proxmox runtime record is available' in formatted and 'does not mean they are offline' in formatted, formatted
        assert '3 source observations have no verified cross-source identity link' in formatted, formatted
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
            'def format_inference_inventory_response(text, inventory, summary):\n'
            '    if "where should" in text.casefold():\n'
            '        return "PLACEMENT:" + str(summary.get("capability_machines", [{}])[0].get("role"))\n'
            '    return "NODE_ACTIVITY:" + summary["resources"][0]["inventory"]["name"]\n',
            encoding='utf-8',
        )
        node_activity = direct_read(
            "What's Compute Node A doing right now?", 'synthetic-owner', 'owner'
        )
        assert node_activity.startswith('NODE_ACTIVITY:Compute Node A Observed hardware inventory lists Compute Node A.'), node_activity
        assert 'hardware inventory is stale; last observed 2026-09-01' in node_activity
        assert "Host CPU/GPU load and free VRAM are not connected." in node_activity
        running_activity = direct_read(
            'What is Compute Node A running?', 'synthetic-owner', 'owner'
        )
        assert running_activity.startswith('NODE_ACTIVITY:Compute Node A'), running_activity
        assert "can't verify private infrastructure or computer status" in direct_read(
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
            "What's running on Compute Node A?", 'synthetic-owner', 'owner'
        )
        assert 'couldn\'t verify Compute Node A as a current Proxmox host' in host_workload_route
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
            'What is running on Private Runtime Host?', 'synthetic-household', 'household'
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
        assert 'VM 802) is running on Erebus' in core_placement_route, core_placement_route
        household_placement = direct_read(
            'Which machine is running HADES?', 'synthetic-household', 'household'
        )
        assert 'private infrastructure or computer status' in household_placement, household_placement
        assert 'Erebus' not in household_placement and 'VM 802' not in household_placement, household_placement
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
backup_adapter = backup_root / 'integrations' / 'homelab-readonly' / 'server.py'
backup_adapter.parent.mkdir(parents=True)
backup_adapter.touch()
old_workdir = os.environ.get('HADES_HERMES_WORKING_DIRECTORY')
old_spec_from_file = importlib.util.spec_from_file_location
old_module_from_spec = importlib.util.module_from_spec
class FakeLoader:
    def exec_module(self, module):
        module.homelab_backup_status = lambda: {'status': 'READABLE'}
        module.format_homelab_backup_status = lambda report: 'Proxmox status: ' + report['status']
class FakeSpec:
    loader = FakeLoader()
os.environ['HADES_HERMES_WORKING_DIRECTORY'] = str(backup_root)
importlib.util.spec_from_file_location = lambda *_args, **_kwargs: FakeSpec()
importlib.util.module_from_spec = lambda _spec: types.SimpleNamespace()
try:
    backup_answer = direct_proxmox_backup(
        'Are my backups okay?', 'synthetic-owner', 'owner', 'session-key'
    )
    assert 'Proxmox status: READABLE' in backup_answer, backup_answer
    assert 'Configured HADES backup checks: current.' in backup_answer, backup_answer
    assert direct_proxmox_backup(
        'Are my backups okay?', 'synthetic-household', 'household', 'session-key'
    ) is None
    assert direct_proxmox_backup(
        'Run the backup now', 'synthetic-owner', 'owner', 'session-key'
    ) is None
finally:
    importlib.util.spec_from_file_location = old_spec_from_file
    importlib.util.module_from_spec = old_module_from_spec
    if old_workdir is None:
        os.environ.pop('HADES_HERMES_WORKING_DIRECTORY', None)
    else:
        os.environ['HADES_HERMES_WORKING_DIRECTORY'] = old_workdir
    import shutil
    shutil.rmtree(backup_root, ignore_errors=True)
print('PASS owner backup questions compose bounded Proxmox evidence with HADES coverage; household and write requests remain gated')
