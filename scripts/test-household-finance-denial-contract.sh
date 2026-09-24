#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

source = Path('hermes/sitecustomize.py').read_text(encoding='utf-8')
assert 'Household finance request denied before model invocation' in source
assert "if self._hades_session_scope == \"household\" and owner_finance_request:" in source
assert "I can't access Scotty's " in source and 'finances. That information is owner-only' in source
assert 'api_calls": 0' in source
assert 'spend|spending|spent' in source
import re
finance = re.compile(r'\b(?:finance|finances|spend|spending|spent|budget|transaction|account|money|cost|paid|expense|expenses)\b', re.I)
assert finance.search('how much did i spend?')
print('PASS household finance requests fail closed before expensive inference')
print('PASS ordinary spend wording reaches the deterministic finance boundary')
PY
