#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
import json
schema=json.loads(Path('config/hades.schema.json').read_text())
example=Path('config/hades.example.yaml').read_text()
assert 'type: local' in example
assert 'enabled: false' in example
assert 'personal_memory: false' in example
assert 'finance: false' in example
profiles={p.read_text() for p in Path('config/profiles').glob('*.yaml')}
assert any('model_path: cpu' in p for p in profiles)
assert any('model_path: detected-local-gpu' in p for p in profiles)
assert any('model_path: existing-openai-compatible-endpoint' in p for p in profiles)
assert any('model_path: configured-private-model-servers' in p for p in profiles)
assert 'fallback' in schema['properties']['models']['required']
print('PASS local, GPU, existing-server, and explicit fallback policy contract')
PY
