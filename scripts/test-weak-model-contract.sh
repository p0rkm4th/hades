#!/usr/bin/env bash
set -eu

# Static interface audit for weaker model lanes. It checks that schemas and
# routing guidance carry the safety/selection information a model needs.
python - <<'PY'
from pathlib import Path

overlay = Path('hermes/sitecustomize.py').read_text().lower()
agent = Path('integrations/agent-zero-mcp/server.py').read_text().lower()
recipe = Path('integrations/grocy-recipe-authoring/server.py').read_text().lower()

for fragment in (
    'call web_search before answering',
    'allowed_memory = {"hindsight_recall", "hindsight_retain"}',
    'if completion_only_model:',
    'self.tools = []',
    'if agent_zero_intent and not household_session:',
    'hades timing stage=tool',
    'hades timing stage=turn',
):
    if fragment not in overlay:
        raise SystemExit(f'missing weak-model routing contract: {fragment}')
for fragment in (
    'read-only task', 'never include credentials', 'minlength', 'maxlength',
    'do not request writes', 'outcome unknown',
):
    if fragment not in agent:
        raise SystemExit(f'missing operator interface contract: {fragment}')
for fragment in ('"type": "integer"', '"minimum": 1', '"maximum": max_servings'):
    if fragment not in recipe:
        raise SystemExit(f'missing recipe schema contract: {fragment}')
print('PASS weak-model interface contract')
PY
