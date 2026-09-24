#!/usr/bin/env bash
set -eu

# Validate the public reconstruction contract without reading private operator
# records, credentials, or persistent volumes.
python - <<'PY'
import json
from pathlib import Path

machine = json.loads(Path('config/reconstruction-manifest.json').read_text())
if machine.get('manifest_version') != 1:
    raise SystemExit('machine manifest version is not 1')
machine_components = {item['component']: item for item in machine['components']}
versions = {}
for line in Path('config/versions.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        versions[key] = value
for component, key in {
    'LLDAP': 'HADES_LLDAP_IMAGE',
    'Hindsight': 'HADES_HINDSIGHT_IMAGE',
    'Grocy': 'HADES_GROCY_IMAGE',
    'Agent Zero': 'HADES_AGENT_ZERO_IMAGE',
}.items():
    if key not in versions or machine_components[component]['pinned_version'] != f'config/versions.env:{key}':
        raise SystemExit(f'machine manifest pin reference drifted for {component}')
if machine_components['Open WebUI']['pinned_version'] != f"{versions['HADES_OPEN_WEBUI_VERSION']} tracked Dockerfile plus immutable base":
    raise SystemExit('machine manifest Open WebUI version drifted')
if machine_components['Hermes 0.14 baseline']['pinned_version'] != versions['HADES_HERMES_VERSION']:
    raise SystemExit('machine manifest Hermes version drifted')
if machine_components['Actual Budget / Finance MCP']['pinned_version'] != f"{versions['HADES_ACTUAL_VERSION']} server/client pair":
    raise SystemExit('machine manifest Actual version drifted')
if len(machine_components) != 9 or any(
    not all(item.get(field) is not None for field in (
        'pinned_version', 'persistent_state', 'required_secret_inputs',
        'network_dependency', 'startup_order', 'health_check', 'restore_check'))
    for item in machine_components.values()
):
    raise SystemExit('machine manifest has missing component fields')

allowed_provenance = {
    'SOURCE CONTROLLED', 'GENERATED FROM SOURCE-CONTROLLED TEMPLATE',
    'EXPLICIT OPERATOR INPUT', 'GENERATED SECRET WITH DOCUMENTED LIFECYCLE',
    'RESTORED CANONICAL STATE', 'UPSTREAM APPLICATION DEFAULT',
}
provenance = machine.get('provenance', [])
if len(provenance) != 6 or any(
    not all(item.get(field) for field in ('artifact', 'classification', 'source', 'lifecycle'))
    or item['classification'] not in allowed_provenance
    for item in provenance
):
    raise SystemExit('machine manifest provenance classification is incomplete')
if any('already there' in item['classification'].lower() for item in provenance):
    raise SystemExit('machine manifest contains implicit artifact provenance')

source = Path('docs/component-manifest.md').read_text()
required = (
    'LLDAP', 'Open WebUI', 'Hindsight', 'Grocy', 'Hermes 0.14 baseline',
    'Actual Budget / Finance MCP', 'Agent Zero', 'SearXNG', 'HADES policy/assets/adapters',
)
start = source.index('## Reconstruction manifest')
end = source.index('## Boundary rule', start)
table = source[start:end]
for component in required:
    if component not in machine_components:
        raise SystemExit(f'machine manifest omits {component}')
    rows = [line for line in table.splitlines() if line.startswith('| ' + component + ' |')]
    if len(rows) != 1:
        raise SystemExit(f'manifest must contain exactly one row for {component}')
    cells = [cell.strip() for cell in rows[0].strip('|').split('|')]
    if len(cells) != 8 or any(not cell for cell in cells):
        raise SystemExit(f'manifest row is incomplete for {component}')
    if not any(marker in cells[1].lower() for marker in ('pinned', 'repository')):
        raise SystemExit(f'rebuild source is not explicit for {component}')
expected_order = {
    'LLDAP': '1',
    'Open WebUI': '2',
    'Hindsight': '3',
    'Grocy': '4',
    'Actual Budget / Finance MCP': '4',
    'Hermes 0.14 baseline': '5',
    'Agent Zero': '6',
    'SearXNG': '7',
}
for component, expected in expected_order.items():
    row = next(line for line in table.splitlines() if line.startswith('| ' + component + ' |'))
    cells = [cell.strip() for cell in row.strip('|').split('|')]
    if cells[5] != expected:
        raise SystemExit(f'startup order for {component} is {cells[5]!r}, expected {expected!r}')
    if machine_components[component]['startup_order'] != int(expected):
        raise SystemExit(f'machine manifest startup order for {component} is incorrect')
for phrase in ('Pinned/rebuild source', 'Persistent state', 'Required private inputs',
               'Network dependency', 'Startup order', 'Health check', 'Restore check'):
    if phrase not in table:
        raise SystemExit(f'manifest column missing: {phrase}')
print('PASS reconstruction manifest contract')
PY
