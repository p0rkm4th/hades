#!/usr/bin/env bash
set -eu

# Static audit for authority amplification in publishable configuration.
python - <<'PY'
from pathlib import Path

compose = '\n'.join(p.read_text() for p in Path('deploy').glob('*.compose.yaml'))
overlay = Path('hermes/sitecustomize.py').read_text()
finance_client = Path('integrations/actual-finance-readonly/actual_client.js').read_text()
agent_zero = Path('integrations/agent-zero-mcp/server.py').read_text()

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
for forbidden, label in (
    ('privileged: true', 'privileged container'),
    ('network_mode: host', 'host network'),
    ('/var/run/docker.sock', 'Docker socket mount'),
    ('/:/host', 'broad host mount'),
):
    if forbidden in compose:
        raise SystemExit(f'forbidden {label} exposed by tracked compose')
agent_compose = Path('deploy/agent-zero.compose.yaml').read_text()
for fragment, label in (
    ('read_only: true', 'Agent Zero read-only root filesystem'),
    ('- ALL', 'Agent Zero capability drop'),
    ('no-new-privileges:true', 'Agent Zero no-new-privileges'),
):
    if fragment not in agent_compose:
        raise SystemExit(f'missing {label}')
if 'mcp-actual-finance-readonly' in overlay:
    raise SystemExit('finance toolset is reachable from the production overlay')
if 'HADES_OWNER_SUBJECT_ID' not in overlay or 'return ""' not in overlay:
    raise SystemExit('owner scope does not fail closed')
if 'shell' in overlay.lower() and 'unrestricted' in overlay.lower():
    raise SystemExit('overlay mentions unrestricted shell authority')
for forbidden in ('createTransaction', 'updateTransaction', 'deleteTransaction', 'runCommand'):
    if forbidden in finance_client:
        raise SystemExit(f'finance bridge exposes mutation or command API: {forbidden}')
for required_text in ('read-only', 'OUTCOME UNKNOWN', 'MAX_TASK_CHARS', 'MAX_RESPONSE_CHARS'):
    if required_text not in agent_zero:
        raise SystemExit(f'Agent Zero bound is missing: {required_text}')
print('PASS static security boundary audit')
PY
