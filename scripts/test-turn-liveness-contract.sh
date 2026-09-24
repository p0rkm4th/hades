#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

text = Path('hermes/config.yaml.example').read_text()
assert 'turn_liveness:' in text
assert 'timeout_s: 30' in text
assert 'poll_s: 5' in text
assert 'restart_drain_timeout: 0' in text
assert 'cron_drain_timeout: 0' in text
overlay = Path('hermes/sitecustomize.py').read_text()
assert 'HADES_SESSION_LEASE_WAIT_SECONDS' in overlay
assert 'LEASE_WAIT_SECONDS' in overlay
assert 'fallback_providers:' in text
assert 'model: gemma4:12b' in text
assert 'max_concurrent_runs: 32' in text
assert '"qwen3:8b":' in text
assert '"gemma4:12b":' in text
assert text.count('request_timeout_seconds: 10') >= 2
assert text.count('stale_timeout_seconds: 10') >= 2
print('PASS Hermes turn liveness watchdog is enabled and bounded')
PY
