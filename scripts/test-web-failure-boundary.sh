#!/usr/bin/env bash
set -euo pipefail

# Dependency-free regression coverage for the live-web failure boundary.
python - <<'PY'
import importlib.util
import logging

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location('hades_web_failure', 'hermes/sitecustomize.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

assert overlay._hades_web_tool_failed({
    'role': 'tool', 'name': 'web_search',
    'content': '[TOOL_ERROR] Error executing web_search: connection failed',
})
assert overlay._hades_web_tool_failed({
    'role': 'tool', 'name': 'web_search',
    'content': '{"error":"service unavailable"}',
})
assert not overlay._hades_web_tool_failed({
    'role': 'tool', 'name': 'web_search',
    'content': '{"result":"Python.org downloads"}',
})
assert not overlay._hades_web_tool_failed({
    'role': 'tool', 'name': 'web_search',
    'content': 'A search snippet mentions an unavailable service.',
})
print('PASS web failure boundary regression')
PY
