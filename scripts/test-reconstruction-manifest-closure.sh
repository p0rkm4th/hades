#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
import subprocess
from pathlib import Path

manifest = json.loads(Path('config/reconstruction-manifest.json').read_text(encoding='utf-8'))
versions = {}
for line in Path('config/versions.env').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        versions[key] = value

sources = {
    'LLDAP': ['deploy/lldap.compose.yaml'],
    'Open WebUI': ['deploy/templates/open-webui.compose.yaml', 'webui/Dockerfile', 'webui/channel_response_compat.py'],
    'Hindsight': ['deploy/templates/hindsight.compose.yaml'],
    'Grocy': ['deploy/grocy.compose.yaml', 'integrations/grocy-recipe-authoring'],
    'Actual Budget / Finance MCP': ['integrations/actual-finance-readonly'],
    'Hermes 0.14 baseline': ['deploy/templates/hermes.service.in', 'scripts/install-hermes-artifact.sh'],
    'Agent Zero': ['deploy/agent-zero.compose.yaml', 'integrations/agent-zero-mcp'],
    'SearXNG': ['deploy/templates/searxng.compose.yaml', 'searxng/settings.yml'],
    'HADES policy/assets/adapters': ['hermes/sitecustomize.py', 'webui/hades-theme.css', 'webui/hades-theme.js'],
}
components = {item['component']: item for item in manifest['components']}
if set(components) != set(sources):
    raise SystemExit('FAIL manifest/source closure component set differs')

tracked = set(subprocess.check_output(['git', 'ls-files'], text=True).splitlines())
for component, paths in sources.items():
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise SystemExit(f'FAIL {component} source is missing: {raw}')
        if path.is_file() and raw not in tracked:
            raise SystemExit(f'FAIL {component} source is not tracked: {raw}')
        if path.is_dir() and not any(item == raw or item.startswith(raw.rstrip('/') + '/') for item in tracked):
            raise SystemExit(f'FAIL {component} source directory is not tracked: {raw}')

for component, key in {
    'LLDAP': 'HADES_LLDAP_IMAGE',
    'Hindsight': 'HADES_HINDSIGHT_IMAGE',
    'Grocy': 'HADES_GROCY_IMAGE',
    'Agent Zero': 'HADES_AGENT_ZERO_IMAGE',
    'SearXNG': 'HADES_SEARXNG_IMAGE_RECORD',
}.items():
    if '@sha256:' not in versions.get(key, ''):
        raise SystemExit(f'FAIL {component} does not have an immutable manifest pin')

if '@sha256:' not in versions.get('HADES_OPEN_WEBUI_BASE_IMAGE', ''):
    raise SystemExit('FAIL Open WebUI immutable base is missing')
if '@sha256:' not in versions.get('HADES_HERMES_SOURCE_SHA256', '') and len(versions.get('HADES_HERMES_SOURCE_SHA256', '')) != 64:
    raise SystemExit('FAIL Hermes source checksum is missing')
dockerfile = Path('webui/Dockerfile').read_text(encoding='utf-8')
if 'HADES_OPEN_WEB_UI_BASE_IMAGE' in dockerfile or 'ghcr.io/open-webui/open-webui@sha256:' not in dockerfile:
    raise SystemExit('FAIL Open WebUI Dockerfile does not retain immutable upstream provenance')
if 'channel_response_compat.py' not in dockerfile:
    raise SystemExit('FAIL Open WebUI compatibility layer is absent from the build')

if [item['startup_order'] for item in sorted(components.values(), key=lambda x: x['startup_order'])] != [1, 2, 3, 4, 4, 5, 6, 7, 8]:
    raise SystemExit('FAIL manifest startup order is not a complete 1-8 sequence')
print('PASS every reconstruction component has tracked source and deployment closure')
print('PASS immutable image/source pins and Open WebUI compatibility provenance are present')
print('PASS reconstruction startup order is complete and explicit')
PY
