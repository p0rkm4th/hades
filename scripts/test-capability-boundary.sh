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
if 'client-selectable owner prefix' not in source or 'return ""' not in source:
    raise SystemExit('untrusted owner scope does not fail closed')
if 'privileged_markers = ("agent_zero", "agent-zero", "finance")' not in source:
    raise SystemExit('household privileged tool filtering is missing')
print('PASS privileged capability boundary regression')
PY
