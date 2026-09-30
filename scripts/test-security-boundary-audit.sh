#!/usr/bin/env bash
set -eu

# Static audit for authority amplification in publishable configuration.
python - <<'PY'
from pathlib import Path
import re

compose_paths = sorted(Path('deploy').rglob('*.compose.yaml'))
if not compose_paths:
    raise SystemExit('no tracked Compose records found')
compose = '\n'.join(p.read_text() for p in compose_paths)
overlay = Path('hermes/sitecustomize.py').read_text()
finance_client = Path('integrations/actual-finance-readonly/actual_client.js').read_text()
agent_zero = Path('integrations/agent-zero-mcp/server.py').read_text()
homelab = Path('integrations/homelab-readonly/server.py').read_text()

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
for path in compose_paths:
    text = path.read_text()
    for forbidden, label in (
        ('privileged: true', 'privileged container'),
        ('/var/run/docker.sock', 'Docker socket mount'),
        ('/:/host', 'broad host mount'),
    ):
        if forbidden in text:
            raise SystemExit(f'forbidden {label} exposed by tracked compose: {path}')
    if 'network_mode: host' in text:
        nginx_template = Path('deploy/templates/agent-zero-operator.nginx.conf.in').read_text()
        if path != Path('deploy/templates/agent-zero-operator-proxy.compose.yaml'):
            raise SystemExit(f'forbidden host network exposed by tracked compose: {path}')
        for fragment in ('user: "101:101"', 'cap_drop:', '- ALL', 'read_only: true'):
            if fragment not in text:
                raise SystemExit(f'optional gateway missing host-network restriction: {fragment}')
        if 'ports:' in text or 'listen 127.0.0.1:@WEBUI_FRONT_PORT@' not in nginx_template or 'listen 127.0.0.1:@OPERATOR_FRONT_PORT@' not in nginx_template:
            raise SystemExit('optional gateway does not constrain host-network listeners to loopback')
agent_compose = Path('deploy/agent-zero.compose.yaml').read_text()
if 'read-only container root' in agent_compose:
    raise SystemExit('Agent Zero comment contradicts the writable upstream image contract')
for fragment, label in (
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
for required_text in (
    'homelab_compute_capabilities',
    'path.is_symlink()',
    'read_only',
    'does not imply current availability',
    'HADES_DISCOVERY_ALLOWED_NETWORKS',
):
    if required_text not in homelab:
        raise SystemExit(f'homelab read-only boundary is missing: {required_text}')
for forbidden in ('subprocess', 'os.system', 'docker.sock'):
    if forbidden in homelab:
        raise SystemExit(f'homelab adapter contains forbidden authority primitive: {forbidden}')
for required_text in (
    'hades-user-',
    'HADES_OWNER_SUBJECT_ID',
    'return ""',
):
    if required_text not in overlay:
        raise SystemExit(f'identity/capability boundary is missing: {required_text}')
if not re.search(
    r'privileged_markers\s*=\s*\(\s*"agent_zero"\s*,\s*"agent-zero"\s*,\s*"finance"\s*,\s*"homelab"',
    overlay,
):
    raise SystemExit('identity/capability boundary is missing: privileged marker tuple')
print('PASS static security boundary audit')
PY
