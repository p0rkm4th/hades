#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import re
from urllib.parse import urlparse

compose = Path('deploy/templates/open-webui.compose.yaml').read_text()
assert 'ENABLE_OLLAMA_API: "true"' in compose
assert 'OLLAMA_BASE_URLS:' in compose
assert 'HADES_OLLAMA_BASE_URLS:-' in compose
assert 'HADES_FAST_OLLAMA_API_BASE_URL:-' in compose
assert "HADES_OLLAMA_BASE_URLS" in compose and "HADES_FAST_OLLAMA_API_BASE_URL" in compose
for candidate in re.findall(r"https?://[^\s\"']+", compose):
    host = urlparse(candidate).hostname or ""
    assert not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host), "compose must not bake in a node address"
assert 'OPENAI_API_BASE_URLS:' in compose
print('PASS Open WebUI distributed Ollama catalog contract')
PY
