#!/usr/bin/env bash
set -Eeuo pipefail

python3 - <<'PY'
from pathlib import Path

reconstruction = Path('docs/reconstruction.md').read_text(encoding='utf-8')
required_rows = {
    'Full-stack synthetic clean reconstruction': 'PASS',
    'Actual-image application composition': 'PASS',
    'Full application clean reconstruction': 'NOT PROVEN',
    'Fresh-install synthetic household soak': 'PASS',
    'Fresh-install full application household soak': 'NOT PROVEN',
}
for level, status in required_rows.items():
    rows = [line for line in reconstruction.splitlines() if line.startswith(f'| {level} |')]
    if len(rows) != 1 or not rows[0].split('|')[2].strip().startswith(status):
        raise SystemExit(f'FAIL reconstruction evidence row is missing or overstated: {level}')
if '| Full-stack clean reconstruction |' in reconstruction or '| Fresh-install household soak |' in reconstruction:
    raise SystemExit('FAIL stale collapsed reconstruction evidence row remains')
if 'test-full-application-image-startup.sh' not in reconstruction:
    raise SystemExit('FAIL actual-image composition harness is not documented')

readiness = Path('docs/stable-v1-readiness.md').read_text(encoding='utf-8')
row = next((line for line in readiness.splitlines() if line.startswith('| Installation/rebuild |')), '')
if '| PARTIAL |' not in row or 'full application' not in row.lower():
    raise SystemExit('FAIL stable-v1 installation/rebuild status is missing or overstated')
print('PASS reconstruction evidence documentation remains honest and granular')
PY
