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
    'web': 'SearXNG',
    'smart_home': 'Home Assistant',
    'inventory': 'NetBox',
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
    ('web', 'last week\'s result', 'current result', 'last week\'s result'),
    ('smart_home', 'light was on', 'light is off', 'light was on'),
    ('inventory', 'scan suggests Node A', 'NetBox intends Node B', 'scan suggests Node A'),
]
for case in cases:
    result = resolve(*case)
    expected_source = {
        'runtime': 'Proxmox', 'pantry': 'Grocy', 'finance': 'Actual',
        'availability': 'Uptime Kuma', 'web': 'SearXNG',
        'smart_home': 'Home Assistant', 'inventory': 'NetBox',
    }[case[0]]
    if (case[2] not in result or f'source: {expected_source}' not in result
            or 'stale context' not in result):
        raise SystemExit(f'canonical precedence failed: {case}: {result}')
    if case[3] is not None and 'conflict' not in result:
        raise SystemExit(f'conflict disclosure failed: {case}: {result}')

unchanged = resolve('pantry', '0 cartons', '0 cartons')
if 'stale context' in unchanged or 'source: Grocy' not in unchanged:
    raise SystemExit(f'unchanged canonical result was misclassified: {unchanged}')

print('PASS synthetic source-of-truth contradictions')
PY
