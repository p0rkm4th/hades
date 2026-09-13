#!/usr/bin/env bash
set -eu

# Static regression check for privileged capability exposure. Finance must be
# explicitly authorized by a future server-side capability boundary; neither
# API initialization nor natural-language intent may add it.
python - <<'PY'
from pathlib import Path

source = Path('hermes/sitecustomize.py').read_text()
init = source.split('    def _hades_agent_init', 1)[1].split(
    '    _AIAgent.__init__ = _hades_agent_init', 1
)[0]
run = source.split('    def _hades_run_conversation', 1)[1].split(
    '    _AIAgent.run_conversation = _hades_run_conversation', 1
)[0]
finance = 'mcp-actual-finance-readonly'
if finance in init or finance in run:
    raise SystemExit('finance toolset is still reachable from the default API overlay')
if 'finance_intent' in source:
    raise SystemExit('finance intent variable still implies prompt-based authorization')
if 'not household_session' not in source:
    raise SystemExit('household Agent Zero scope guard is missing')
if 'hades-user-' not in source or 'HADES_OWNER_SUBJECT_ID' not in source:
    raise SystemExit('server-selected subject scope is incomplete')
if 'subject = _hades_subject_from_session_key(session_key)' not in source:
    raise SystemExit('scope resolver does not reuse subject validation')
if 'client-selectable owner prefix' not in source or 'return ""' not in source:
    raise SystemExit('untrusted owner scope does not fail closed')
if 'privileged_markers = ("agent_zero", "agent-zero", "finance")' not in source:
    raise SystemExit('household privileged tool filtering is missing')

import os
import hermes.sitecustomize as overlay

os.environ['HADES_OWNER_SUBJECT_ID'] = 'owner-subject-123'
checks = {
    'hades-user-owner-subject-123': 'owner',
    'hades-user-household-456': 'household',
    'hades-user-': '',
    'hades-user-contains space': '',
    'owner-subject-123': '',
    'hades-owner-owner-subject-123': '',
}
for key, expected in checks.items():
    actual = overlay._hades_session_scope(key)
    if actual != expected:
        raise SystemExit(f'session scope mismatch for {key!r}: {actual!r}')
if overlay._hades_subject_from_session_key('hades-user-../owner'):
    raise SystemExit('path-like subject was accepted')
print('PASS privileged capability boundary regression')
PY
