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
print('PASS privileged capability boundary regression')
PY
