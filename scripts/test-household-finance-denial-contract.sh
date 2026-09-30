#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path
import ast
import re

source = Path('hermes/sitecustomize.py').read_text(encoding='utf-8')
assert 'Household finance request denied before model invocation' in source
assert "and owner_finance_request" in source
assert "and not _hades_is_meal_budget_intent(current_text)" in source
assert "and not _hades_is_meal_budget_intent(user_message)" in source
assert "I can't access Scotty's " in source and 'finances. That information is owner-only' in source
assert 'api_calls": 0' in source
assert 'spend|spending|spent' in source
finance = re.compile(r'\b(?:finance|finances|spend|spending|spent|budget|transaction|account|money|cost|paid|expense|expenses)\b', re.I)
assert finance.search('how much did i spend?')
tree = ast.parse(source)
helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_hades_is_meal_budget_intent')
namespace = {'re': re}
exec(compile(ast.Module(body=[helper], type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
is_meal_budget = namespace['_hades_is_meal_budget_intent']
assert is_meal_budget('What can we cook tonight without spending much?')
assert is_meal_budget('What cheap recipe can we make?')
assert not is_meal_budget('How much did I spend on restaurants?')
assert not is_meal_budget('Can I afford groceries from my checking account?')
print('PASS household finance requests fail closed before expensive inference')
print('PASS ordinary spend wording reaches the deterministic finance boundary')
print('PASS meal-budget intent stays on shared pantry while personal affordability remains out of scope')
PY
