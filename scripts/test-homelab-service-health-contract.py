#!/usr/bin/env python3
"""Exercise service-health answers against authoritative monitor evidence."""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


source = Path('hermes/sitecustomize.py').read_text(encoding='utf-8')
tree = ast.parse(source)
wanted = {
    '_hades_service_health_target', '_hades_service_monitor_response',
    '_hades_homelab_availability_groups', '_hades_direct_homelab_read',
    '_hades_homelab_workloads_on_host_response',
    '_hades_endpoint_intent_before_provision',
    '_hades_service_endpoint_response',
    '_hades_service_placement_response',
    '_hades_endpoint_continuation_response',
    '_hades_direct_owner_location',
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
}
exec(compile(ast.Module(body=functions, type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
target = namespace['_hades_service_health_target']
answer = namespace['_hades_service_monitor_response']
groups = namespace['_hades_homelab_availability_groups']
workloads_on_host = namespace['_hades_homelab_workloads_on_host_response']
direct_read = namespace['_hades_direct_homelab_read']
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
        assert "Uptime Kuma's configured check for Minecraft Server is up." in household_game_status
        assert 'Test Host' not in household_game_status and '192.0.2.' not in household_game_status
        assert 'couldn\'t find a matching service record' in direct_read(
            'Where is Agent Zero?', 'synthetic-owner', 'owner'
        )
        assert direct_read('Where is Agent Zero?', 'synthetic-household', 'household') is None
        assert direct_read('Is the homelab okay?', 'synthetic-household', 'household') is None
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

        def write_broad_summary(monitors):
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
            (adapter_dir / 'server.py').write_text(
                'def homelab_summary():\n    return ' + repr(summary) + '\n',
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
        (adapter_dir / 'server.py').write_text(
            'def homelab_inference_inventory():\n'
            '    return {"status": "READABLE", "endpoints": []}\n'
            'def homelab_summary():\n'
            '    return {"resources": [{"identity": {"canonical_id": "netbox:device:75"}, '
            '"inventory": {"name": "Compute Node A"}}]}\n'
            'def homelab_compute_capabilities():\n'
            '    return {"machines": [{"name": "Compute Node A", "role": "synthetic inference node"}]}\n'
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
        assert "Host CPU/GPU load and free VRAM are not connected." in node_activity
        running_activity = direct_read(
            'What is Compute Node A running?', 'synthetic-owner', 'owner'
        )
        assert running_activity.startswith('NODE_ACTIVITY:Compute Node A'), running_activity
        assert 'owner session' in direct_read(
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
