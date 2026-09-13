#!/usr/bin/env bash
set -eu

# Regression check for natural-language memory questions that must not be
# routed to a live household system. This deliberately checks the deployed
# overlay source without importing Hermes' runtime dependencies.
python - <<'PY'
from pathlib import Path

source = Path('hermes/sitecustomize.py').read_text()
required = (
    'did i tell',
    'do you remember',
    'hindsight_recall',
    '_hades_original_sync_turn',
    '_hades_shared_memory_intent',
    '_hades_explicit_memory_intent',
    'skipping automatic hindsight retain for shared-state turn',
    '_hindsight.hindsightmemoryprovider.sync_turn = _hades_sync_turn',
    'stale personal semantic-memory claims',
    '_hades_shared_memory_intent.search(query)',
    '_hades_grocy_action_intent',
    'grocry',
    'grocerys',
    'outta',
)
missing = [value for value in required if value not in source.lower()]
if missing:
    raise SystemExit(f'missing memory-intent coverage: {missing}')
print('PASS memory intent regression')
PY
