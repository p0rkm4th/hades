#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json
from pathlib import Path
schema=json.loads(Path('config/hades.schema.json').read_text())
example=Path('config/hades.example.yaml').read_text()
for item in ('schema: 1','profile: standalone','exposure: lan','cloud_fallback:','personal_memory: false','finance: false'):
    assert item in example, item
for profile in ('standalone','standalone-gpu','cpu-only','distributed','existing-model-server','proxmox','development'):
    assert Path(f'config/profiles/{profile}.yaml').is_file(), profile
assert schema['properties']['deployment']['properties']['profile']['enum']
print('PASS public configuration schema, example, and profiles')
PY
