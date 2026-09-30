#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python3 - "$repo_dir/webui/hades-theme.js" <<'PY'
from pathlib import Path
import sys

source=Path(sys.argv[1]).read_text(encoding='utf-8')
honest="Your request may have completed, so check before trying again."
assert honest in source, 'network failures must communicate uncertain outcome before retry'
assert 'Nothing was changed; please try again.' not in source, 'network failure cannot promise no mutation occurred'
assert "showComposerFailureNotice(assistantCountAtStart);\n        throw error;" in source, 'rejected completion fetch must show HADES failure guidance'
assert "node.closest?.('#response-content-container')" in source and 'failed to fetch' in source.lower(), 'native transport error must be humanized in the chat'
print('PASS Open WebUI network failure guidance is human-readable and outcome-honest')
PY
node --check "$repo_dir/webui/hades-theme.js"
