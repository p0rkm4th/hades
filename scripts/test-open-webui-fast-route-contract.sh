#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import re
from urllib.parse import urlparse

route = Path('webui/configure_fast_route.py').read_text(encoding='utf-8')
compose = Path('deploy/templates/open-webui.compose.yaml').read_text(encoding='utf-8')
entrypoint = Path('webui/entrypoint.sh').read_text(encoding='utf-8')
assert 'HADES_FAST_OPENAI_API_BASE_URL' in route
assert 'openai.api_base_urls' in route
assert 'openai.api_configs' in route
assert 'builtin_tools": False' in route
for candidate in re.findall(r"https?://[^\s\"']+", route):
    host = urlparse(candidate).hostname or ""
    assert not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host), "Fast route must not bake in a node address"
assert 'HADES_FAST_OPENAI_API_BASE_URL' in compose
assert 'configure_fast_route.py' in entrypoint
print('PASS Fast route migration is provider-correct, completion-only, and environment-scoped')
PY
