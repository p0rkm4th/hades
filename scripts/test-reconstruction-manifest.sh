#!/usr/bin/env bash
set -eu

# Validate the public reconstruction contract without reading private operator
# records, credentials, or persistent volumes.
python - <<'PY'
from pathlib import Path

source = Path('docs/component-manifest.md').read_text()
required = (
    'LLDAP', 'Open WebUI', 'Hindsight', 'Grocy', 'Hermes 0.14 baseline',
    'Actual Budget / Finance MCP', 'Agent Zero', 'SearXNG', 'HADES policy/assets/adapters',
)
start = source.index('## Reconstruction manifest')
end = source.index('## Boundary rule', start)
table = source[start:end]
for component in required:
    rows = [line for line in table.splitlines() if line.startswith('| ' + component + ' |')]
    if len(rows) != 1:
        raise SystemExit(f'manifest must contain exactly one row for {component}')
    cells = [cell.strip() for cell in rows[0].strip('|').split('|')]
    if len(cells) != 8 or any(not cell for cell in cells):
        raise SystemExit(f'manifest row is incomplete for {component}')
    if not any(marker in cells[1].lower() for marker in ('pinned', 'repository')):
        raise SystemExit(f'rebuild source is not explicit for {component}')
orders = []
for line in table.splitlines():
    if line.startswith('| ') and line.count('|') == 9 and line[1:3].isdigit():
        orders.append(line)
if not all(f'| {number} |' in table for number in range(1, 8)):
    raise SystemExit('startup order is incomplete')
for phrase in ('Pinned/rebuild source', 'Persistent state', 'Required private inputs',
               'Network dependency', 'Startup order', 'Health check', 'Restore check'):
    if phrase not in table:
        raise SystemExit(f'manifest column missing: {phrase}')
print('PASS reconstruction manifest contract')
PY
