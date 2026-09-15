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
    '_hades_nonpersonal_state_intent',
    '_hades_transient_error',
    '_hades_nonpersonal_state_turn',
    '_hades_explicit_memory_intent',
    'skipping automatic hindsight retain for non-personal or transient-error turn',
    '_hindsight.hindsightmemoryprovider.sync_turn = _hades_sync_turn',
    'stale personal semantic-memory claims',
    '_hades_grocy_action_intent',
    '_hades_grocy_item_fragment',
    'agent\\s+zero',
    'delegat(?:e|ion|ed)',
    'transaction',
    'web_search',
    'endswith',
    'grocry',
    'grocerys',
    'outta',
)
missing = [value for value in required if value not in source.lower()]
if missing:
    raise SystemExit(f'missing memory-intent coverage: {missing}')

import importlib.util
import logging
logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location('hades_overlay_memory_policy', 'hermes/sitecustomize.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
for error in ('OUTCOME UNKNOWN', 'request timed out', 'service unavailable',
              'invalid JSON response', 'connection failed'):
    if not overlay._hades_transient_error_text(error):
        raise SystemExit(f'transient error was not suppressed: {error}')
for ordinary in ('I prefer basil', 'I hate mushrooms', 'remember my preference'):
    if overlay._hades_transient_error_text(ordinary):
        raise SystemExit(f'ordinary personal text was misclassified: {ordinary}')
for live_state in (
    'Grocy says there are 2 cartons of milk',
    'the shared shopping list contains onions',
    'the weather result says rain',
    'the web search returned a recipe',
    'the finance balance is $65',
    'Agent Zero returned execution output',
    'Proxmox says VM X is running on Node B',
    'NetBox lists the server at 10.0.0.5',
    'Uptime Kuma reports the service is offline',
    'the living-room light is on',
    'Home Assistant says the air purifier is unavailable',
):
    if not overlay._hades_nonpersonal_state_turn(live_state):
        raise SystemExit(f'live/shared state was eligible for private memory: {live_state}')
for personal in ('I prefer basil', 'I hate mushrooms', 'my favorite dinner is pasta'):
    if overlay._hades_nonpersonal_state_turn(personal):
        raise SystemExit(f'personal fact was suppressed as live state: {personal}')
print('PASS memory intent regression')
PY
