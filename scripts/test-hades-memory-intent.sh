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
)
missing = [value for value in required if value not in source.lower()]
if missing:
    raise SystemExit(f'missing memory-intent coverage: {missing}')
print('PASS memory intent regression')
PY
