#!/usr/bin/env bash
set -eu

# Synthetic contradiction harness. It tests authority selection and conflict
# disclosure without contacting real memory, finance, homelab, or web APIs.
python - <<'PY'
def resolve(domain, remembered, canonical, observed=None):
    labels = {
        'runtime': 'Proxmox',
        'pantry': 'Grocy',
        'finance': 'Actual',
        'availability': 'Uptime Kuma',
    }
    answer = f"Current {domain}: {canonical} (source: {labels[domain]})."
    if remembered != canonical:
        answer += f" Memory said {remembered}; that is stale context, not current truth."
    if observed is not None and observed != canonical:
        answer += f" {labels[domain]} and the other observation conflict; report the canonical value and investigate the discrepancy."
    return answer

cases = [
    ('runtime', 'Node A', 'Node B', 'Node A'),
    ('pantry', '2 cartons', '0 cartons', None),
    ('finance', '$50', '$65', None),
    ('availability', 'online', 'down', 'online'),
]
for case in cases:
    result = resolve(*case)
    if case[2] not in result or 'source:' not in result or 'stale context' not in result:
        raise SystemExit(f'canonical precedence failed: {case}: {result}')
    if case[3] is not None and 'conflict' not in result:
        raise SystemExit(f'conflict disclosure failed: {case}: {result}')

print('PASS synthetic source-of-truth contradictions')
PY
