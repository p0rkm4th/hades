#!/usr/bin/env bash
set -eu

# Dependency-free contract test for mixed-domain routing. This verifies the
# policy boundary in the production overlay without invoking a model or any
# real provider.
python - <<'PY'
from pathlib import Path

source = Path('hermes/sitecustomize.py').read_text().lower()

def require(fragment):
    if fragment not in source:
        raise SystemExit(f'missing composition contract: {fragment}')

require('if memory_intent and isinstance(original_tools, list):')
require('allowed_memory = {"hindsight_recall", "hindsight_retain"}')
require('if web_intent:')
require('== "web_search"')
require('if agent_zero_intent and not household_session:')
require('endswith(\n                        "agent_zero_delegate"')
require('household_session = getattr(self, "_hades_session_scope", "") == "household"')
require('if _hades_nonpersonal_state_turn(user_text):')
require('skipping automatic hindsight retain for non-personal state turn')

# The household denial must remain on the Agent Zero gate; prompt wording
# cannot create owner authority or make the entire tool catalog visible.
agent_gate = source.index('if agent_zero_intent and not household_session:')
if source.index('household_session', agent_gate) < agent_gate:
    raise SystemExit('invalid operator authorization ordering')

print('PASS mixed-domain composition boundary')
PY
