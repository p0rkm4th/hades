#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
import re
import subprocess
import tempfile
from pathlib import Path

manifest = json.loads(Path('config/reconstruction-manifest.json').read_text(encoding='utf-8'))
versions = {}
for line in Path('config/versions.env').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        versions[key] = value

sources = {
    'LLDAP': ['deploy/lldap.compose.yaml'],
    'Open WebUI': ['deploy/templates/open-webui.compose.yaml', 'webui/Dockerfile', 'webui/channel_response_compat.py', 'webui/task_notification_compat.py', 'webui/finance-upload.js', 'webui/receipt-upload.js'],
    'Hindsight': ['deploy/templates/hindsight.compose.yaml'],
    'Grocy': ['deploy/grocy.compose.yaml', 'integrations/grocy-mcp', 'integrations/grocy-recipe-authoring', 'scripts/install-grocy-mcp.sh', 'scripts/check-grocy-mcp-runtime.py'],
    'Actual Budget / Finance MCP': ['integrations/actual-finance-readonly'],
    'Hermes': ['deploy/templates/hermes.service.in', 'hermes/config.yaml.example', 'scripts/install-hermes-artifact.sh'],
    'Agent Zero': ['deploy/agent-zero.compose.yaml', 'integrations/agent-zero-mcp'],
    'SearXNG': ['deploy/templates/searxng.compose.yaml', 'searxng/settings.yml'],
    'HADES policy/assets/adapters': ['hermes/sitecustomize.py', 'integrations/homelab_views.py', 'integrations/grocy-mcp/launch.py', 'integrations/grocy-mcp/requirements.lock', 'integrations/grocy-recipe-authoring/server.py', 'integrations/agent-zero-mcp/server.py', 'webui/hades-theme.css', 'webui/hades-theme.js', 'webui/finance-upload.js', 'webui/receipt-upload.js', 'integrations/homelab-readonly', 'integrations/public-research/server.py', 'integrations/public-research/research.py', 'integrations/browser-access/proxy.py', 'integrations/browser-access/research_reader.py', 'integrations/browser-access/read-only-network.js'],
}
components = {item['component']: item for item in manifest['components']}
if set(components) != set(sources):
    raise SystemExit('FAIL manifest/source closure component set differs')

open_webui = components['Open WebUI']
if open_webui.get('required_assets') != [
    'webui/hades-theme.css', 'webui/hades-theme.js',
    'webui/finance-upload.js', 'webui/receipt-upload.js',
]:
    raise SystemExit('FAIL Open WebUI runtime assets are incomplete or out of sync')
layer = components['HADES policy/assets/adapters']
expected_layer_files = [
    'overlay/sitecustomize.py',
    'overlay/homelab_views.py',
    'adapters/grocy-mcp-launch.py',
    'adapters/grocy-recipe-authoring.py',
    'adapters/agent-zero-mcp.py',
    'assets/hades-theme.css',
    'assets/hades-theme.js',
    'assets/finance-upload.js',
    'assets/receipt-upload.js',
]
if layer.get('installed_layer_files') != expected_layer_files:
    raise SystemExit('FAIL installed HADES layer file list is incomplete or out of order')
expected_digest_sources = [
    'hermes/sitecustomize.py',
    'integrations/homelab_views.py',
    'integrations/grocy-mcp/launch.py',
    'integrations/grocy-mcp/requirements.lock',
    'integrations/grocy-recipe-authoring/server.py',
    'integrations/agent-zero-mcp/server.py',
    'webui/hades-theme.css',
    'webui/hades-theme.js',
    'webui/finance-upload.js',
    'webui/receipt-upload.js',
]
if layer.get('layer_digest_sources') != expected_digest_sources:
    raise SystemExit('FAIL HADES layer digest source list is incomplete or out of order')
installer = Path('scripts/install-hades.sh').read_text(encoding='utf-8')
doctor = Path('scripts/hades-doctor.sh').read_text(encoding='utf-8')
validator = Path('scripts/validate-install.sh').read_text(encoding='utf-8')
expected_source_digest_tail = (
    '"$repo_dir/integrations/homelab_views.py" '
    '"$repo_dir/integrations/grocy-mcp/launch.py" '
    '"$repo_dir/integrations/grocy-mcp/requirements.lock" '
    '"$repo_dir/integrations/grocy-recipe-authoring/server.py" '
    '"$repo_dir/integrations/agent-zero-mcp/server.py" '
    '"$repo_dir/webui/hades-theme.css" "$repo_dir/webui/hades-theme.js" '
    '"$repo_dir/webui/finance-upload.js" "$repo_dir/webui/receipt-upload.js"'
)
expected_overlay_digest_calls = (
    'hades_layer_digest "$config_root/overlay/sitecustomize.py" ',
    'hades_layer_digest "$expected_sitecustomize" ',
    'hades_layer_digest "$config_root/overlay/sitecustomize.py" ',
)
if any(
    call + expected_source_digest_tail not in text
    for text, call in zip((installer, doctor, validator), expected_overlay_digest_calls)
):
    raise SystemExit('FAIL installer/doctor/validator digest order differs from manifest source order')
compose = Path('deploy/templates/open-webui.compose.yaml').read_text(encoding='utf-8')
compose_asset_names = set(re.findall(r'\$\{HADES_CONFIG_ROOT[^}]*\}/assets/([^:/]+):', compose))
required_asset_names = {Path(item).name for item in open_webui['required_assets']}
if compose_asset_names != required_asset_names:
    raise SystemExit(f'FAIL Open WebUI Compose assets and reconstruction manifest differ: {compose_asset_names} != {required_asset_names}')
for asset in required_asset_names:
    if f'webui/{asset}' not in installer or f'assets/{asset}' not in installer:
        raise SystemExit(f'FAIL installer does not declare and install the required asset: {asset}')
    if f'assets/{asset}' not in doctor or f'assets/{asset}' not in validator:
        raise SystemExit(f'FAIL doctor/validator do not require the installed asset: {asset}')
for source in expected_digest_sources:
    if source not in installer or source not in doctor or source not in validator:
        raise SystemExit(f'FAIL installer/doctor/validator digest omits source: {source}')

tracked = set(subprocess.check_output(['git', 'ls-files'], text=True).splitlines())
for raw in (
    'scripts/authorize-synthetic-deployment-test.sh',
    'scripts/synthetic-deployment-target.sh',
    'scripts/check-hermes-profile-contract.py',
):
    if not Path(raw).is_file() or raw not in tracked:
        raise SystemExit(f'FAIL synthetic deployment authorization source is missing or untracked: {raw}')
browser_fallback = next((item for item in manifest.get('optional_components', []) if item.get('component') == 'Anonymous dynamic public-page research fallback'), None)
if not browser_fallback or 'OPTIONAL/STAGED' not in browser_fallback.get('activation', '') or 'defaults false' not in browser_fallback.get('activation', ''):
    raise SystemExit('FAIL dynamic research fallback must stay explicitly staged and disabled by default')
hermes_profile = Path('hermes/config.yaml.example').read_text(encoding='utf-8')
receipt_ocr = next((item for item in manifest.get('optional_components', []) if item.get('component') == 'Receipt OCR gateway and worker'), None)
if not receipt_ocr or 'OWNER-GATED' not in receipt_ocr.get('activation', ''):
    raise SystemExit('FAIL owner-gated receipt OCR reconstruction row is missing')
if receipt_ocr.get('pinned_version', '').find('HADES_RECEIPT_OCR_BASE_IMAGE') < 0:
    raise SystemExit('FAIL receipt OCR reconstruction row does not use the authoritative base-image pin')
if not re.search(r'(?m)^  receipt-ocr-gateway:\n(?:.*\n)*?    enabled: false$', hermes_profile):
    raise SystemExit('FAIL receipt OCR MCP must remain disabled in the canonical profile')
for raw in receipt_ocr.get('source_files', []):
    if not Path(raw).is_file() or raw not in tracked:
        raise SystemExit(f'FAIL receipt OCR reconstruction source is missing or untracked: {raw}')
if '@sha256:' not in versions.get('HADES_RECEIPT_OCR_BASE_IMAGE', ''):
    raise SystemExit('FAIL receipt OCR base image is not immutable')
hermes_env_example = Path('hermes/env.example').read_text(encoding='utf-8')
if 'HADES_PUBLIC_RESEARCH_DYNAMIC_ENABLED=false' not in hermes_env_example or 'HADES_BROWSER_ALLOWED_HOSTS=' not in hermes_env_example:
    raise SystemExit('FAIL dynamic research fallback must document its disabled default and explicit host input')
for component, paths in sources.items():
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise SystemExit(f'FAIL {component} source is missing: {raw}')
        if path.is_file() and raw not in tracked:
            raise SystemExit(f'FAIL {component} source is not tracked: {raw}')
        if path.is_dir() and not any(item == raw or item.startswith(raw.rstrip('/') + '/') for item in tracked):
            raise SystemExit(f'FAIL {component} source directory is not tracked: {raw}')

hermes_profile = Path('hermes/config.yaml.example').read_text(encoding='utf-8')
profile_contract = manifest.get('hermes_profile_contract', {})
required_profile_servers = profile_contract.get('v1_required_servers', {})
owner_gated_profile_servers = profile_contract.get('owner_gated_servers', {})
staged_profile_servers = profile_contract.get('optional_staged_servers', {})
if set(required_profile_servers) & (set(owner_gated_profile_servers) | set(staged_profile_servers)) or set(owner_gated_profile_servers) & set(staged_profile_servers):
    raise SystemExit('FAIL Hermes profile activation classes overlap')
if set(required_profile_servers) | set(owner_gated_profile_servers) | set(staged_profile_servers) != set(re.findall(r'(?m)^  ([A-Za-z0-9_-]+):\s*$', hermes_profile[hermes_profile.index("mcp_servers:"):])):
    raise SystemExit('FAIL Hermes profile registrations are not completely classified')
subprocess.run(['python3', 'scripts/check-hermes-profile-contract.py', 'hermes/config.yaml.example', '--canonical-template'], check=True, capture_output=True, text=True)
recipe_start = hermes_profile.index('  recipe-url-ingest:\n')
recipe_end = hermes_profile.index('  receipt-ocr-gateway:\n', recipe_start)
with tempfile.TemporaryDirectory(prefix='hades-profile-contract-') as temporary:
    profile_path = Path(temporary) / 'config.yaml'
    profile_path.write_text(hermes_profile[:recipe_start] + hermes_profile[recipe_end:], encoding='utf-8')
    rejected = subprocess.run(
        ['python3', 'scripts/check-hermes-profile-contract.py', str(profile_path), '--canonical-template'],
        capture_output=True, text=True,
    )
    if rejected.returncode == 0 or 'recipe-url-ingest' not in rejected.stdout:
        raise SystemExit('FAIL Hermes profile contract accepted a missing V1 recipe-ingest registration')
    grocy_start = hermes_profile.index('  grocy:\n')
    grocy_block_start = grocy_start + len('  grocy:\n')
    disabled_profile = (
        hermes_profile[:grocy_block_start]
        + '    enabled: false\n'
        + hermes_profile[grocy_block_start:]
    )
    profile_path.write_text(disabled_profile, encoding='utf-8')
    rejected_disabled = subprocess.run(
        ['python3', 'scripts/check-hermes-profile-contract.py', str(profile_path)],
        capture_output=True, text=True,
    )
    if rejected_disabled.returncode == 0 or 'explicitly disabled' not in rejected_disabled.stdout:
        raise SystemExit('FAIL Hermes profile contract accepted a disabled V1-required server')
    owner_gated_marker = '  finance-file-import:\n    # Enable only after the owner approves the private file-intake path.\n    enabled: false\n'
    if hermes_profile.count(owner_gated_marker) != 1:
        raise SystemExit('FAIL expected exactly one disabled canonical finance owner-gated registration')
    owner_gated_enabled = hermes_profile.replace(
        owner_gated_marker,
        owner_gated_marker.replace('enabled: false', 'enabled: true'),
        1,
    )
    profile_path.write_text(owner_gated_enabled, encoding='utf-8')
    rejected_owner_activation = subprocess.run(
        ['python3', 'scripts/check-hermes-profile-contract.py', str(profile_path), '--canonical-template'],
        capture_output=True, text=True,
    )
    if rejected_owner_activation.returncode == 0 or 'must be disabled in the canonical profile' not in rejected_owner_activation.stdout:
        raise SystemExit('FAIL canonical Hermes profile contract accepted an enabled owner-gated server')
    operator_owner_activation = subprocess.run(
        ['python3', 'scripts/check-hermes-profile-contract.py', str(profile_path)],
        capture_output=True, text=True,
    )
    if operator_owner_activation.returncode != 0 or 'explicit owner activation must be verified' not in operator_owner_activation.stdout:
        raise SystemExit('FAIL operator Hermes profile contract did not warn about enabled owner-gated server')
optional_gateway = [
    item for item in manifest.get('optional_components', [])
    if item.get('component') == 'Agent Zero Operator gateway'
]
if len(optional_gateway) != 1:
    raise SystemExit('FAIL optional Agent Zero Operator gateway row is missing or duplicated')
gateway = optional_gateway[0]
if gateway.get('pinned_version') != 'config/versions.env:HADES_NGINX_IMAGE plus tracked proxy/auth source':
    raise SystemExit('FAIL optional Operator gateway pin does not reference the authoritative version manifest')
if 'OPTIONAL/STAGED' not in gateway.get('activation', '') or 'disabled by default' not in gateway.get('activation', ''):
    raise SystemExit('FAIL optional Operator gateway must remain staged and disabled by default')
agent_zero_mcp = [
    item for item in manifest.get('optional_components', [])
    if item.get('component') == 'Agent Zero bounded MCP delegation'
]
if len(agent_zero_mcp) != 1 or 'OPTIONAL/STAGED' not in agent_zero_mcp[0].get('activation', ''):
    raise SystemExit('FAIL bounded Agent Zero MCP must be declared as optional/staged')
if not re.search(r'(?m)^  hades-agent-zero:\n(?:.*\n)*?    enabled: false$', hermes_profile):
    raise SystemExit('FAIL bounded Agent Zero MCP must remain disabled in the canonical profile')
for raw in (
    'deploy/templates/agent-zero-operator.nginx.conf.in',
    'deploy/templates/agent-zero-operator-proxy.compose.yaml',
    'deploy/templates/agent-zero-operator-auth.service.in',
    'integrations/operator-access/proxy_auth_server.py',
    'integrations/operator-access/session_auth.py',
    'integrations/automation/phase3_lldap_authority.py',
    'scripts/test-agent-zero-operator-proxy.py',
    'scripts/test-agent-zero-operator-proxy-render.sh',
):
    if not Path(raw).is_file() or raw not in tracked:
        raise SystemExit(f'FAIL optional Operator gateway source is missing or untracked: {raw}')
if '@sha256:' not in versions.get('HADES_NGINX_IMAGE', ''):
    raise SystemExit('FAIL optional Operator gateway does not have an immutable image pin')

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
hermes = components['Hermes']
if hermes.get('pinned_version') != 'config/versions.env:HADES_HERMES_VERSION':
    raise SystemExit('FAIL reconstruction Hermes pin must reference the authoritative version manifest')
if hermes.get('required_profile') != 'hermes/config.yaml.example':
    raise SystemExit('FAIL Hermes reconstruction profile is not declared')
if not all(marker in hermes_profile for marker in (
    '  grocy_recipe_authoring:',
    '${HADES_HERMES_WORKING_DIRECTORY}/integrations/grocy-recipe-authoring/server.py',
    'GROCY_API_KEY_FILE: "${HADES_GROCY_API_KEY_FILE}"',
)):
    raise SystemExit('FAIL Hermes profile omits the bounded Grocy recipe-authoring adapter or file-backed credential')
for checker in ('scripts/hades-doctor.sh', 'scripts/validate-install.sh'):
    text = Path(checker).read_text(encoding='utf-8')
    if 'check-hermes-profile-contract.py' not in text:
        raise SystemExit(f'FAIL {checker} does not enforce the manifest-backed Hermes profile contract')
if versions.get('HADES_HERMES_VERSION') != versions.get('HADES_HERMES_SOURCE_VERSION'):
    raise SystemExit('FAIL Hermes runtime and source artifact versions differ')
dockerfile = Path('webui/Dockerfile').read_text(encoding='utf-8')
if 'HADES_OPEN_WEB_UI_BASE_IMAGE' in dockerfile or 'ARG OPEN_WEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui@sha256:' not in dockerfile:
    raise SystemExit('FAIL Open WebUI Dockerfile does not retain immutable upstream provenance')
if 'channel_response_compat.py' not in dockerfile:
    raise SystemExit('FAIL Open WebUI compatibility layer is absent from the build')

if [item['startup_order'] for item in sorted(components.values(), key=lambda x: x['startup_order'])] != [1, 2, 3, 4, 4, 5, 6, 7, 8]:
    raise SystemExit('FAIL manifest startup order is not a complete 1-8 sequence')
print('PASS every reconstruction component has tracked source and deployment closure')
print('PASS immutable image/source pins and Open WebUI compatibility provenance are present')
print('PASS reconstruction startup order is complete and explicit')
print('PASS anonymous dynamic research fallback is reconstructable and remains disabled by default')
PY
