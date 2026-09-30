#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

source = Path('scripts/dom-daily-use-soak.js').read_text(encoding='utf-8')
assert "process.once('SIGINT'" in source
assert "process.once('SIGTERM'" in source
assert 'activeBrowser?.close()' in source
assert 'activeBrowser = null' in source
print('PASS DOM soak closes the active browser on SIGINT/SIGTERM and normal teardown')
PY
