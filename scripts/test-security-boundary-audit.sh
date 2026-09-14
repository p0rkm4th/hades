#!/usr/bin/env bash
set -eu

# Static audit for authority amplification in publishable configuration.
python - <<'PY'
from pathlib import Path

compose = '\n'.join(p.read_text() for p in Path('deploy').glob('*.compose.yaml'))
overlay = Path('hermes/sitecustomize.py').read_text()

required = {
    '127.0.0.1:7002:80': 'Agent Zero loopback binding',
    '127.0.0.1:7003:80': 'Grocy loopback binding',
    '127.0.0.1:17170:17170': 'LLDAP loopback binding',
    'hades-agent-zero-data:/a0/usr': 'isolated Agent Zero volume',
    'hades-grocy-data:/config': 'isolated Grocy volume',
    'hades-lldap-data:/data': 'isolated LLDAP volume',
}
for fragment, label in required.items():
    if fragment not in compose:
        raise SystemExit(f'missing {label}')
if 'mcp-actual-finance-readonly' in overlay:
    raise SystemExit('finance toolset is reachable from the production overlay')
if 'HADES_OWNER_SUBJECT_ID' not in overlay or 'return ""' not in overlay:
    raise SystemExit('owner scope does not fail closed')
if 'shell' in overlay.lower() and 'unrestricted' in overlay.lower():
    raise SystemExit('overlay mentions unrestricted shell authority')
print('PASS static security boundary audit')
PY
