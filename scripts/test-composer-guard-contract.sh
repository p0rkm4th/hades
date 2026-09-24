#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

theme = Path('webui/hades-theme.js').read_text()
entrypoint = Path('webui/entrypoint.sh').read_text()

assert 'window.__hadesCompletionFetchGuard' in theme
assert "String(url).includes('/api/chat/completions')" in theme
assert 'function guardBusyComposerEvent(event)' in theme
assert "window.addEventListener('keydown', guardBusyComposerEvent, true)" in theme
assert "window.addEventListener('submit', guardBusyComposerEvent, true)" in theme
assert 'hades-composer-busy-notice' in theme
assert 'Your message is still in the composer.' in theme
assert 'completionGeneration' in theme
assert 'stopButton.click()' in theme
assert 'completionSilentTimeoutMs' in theme
assert 'showComposerFailureNotice(assistantCountAtStart)' in theme
assert '/api/tasks/chat/' in theme
assert 'settleFromRenderedDom' in theme
assert 'renderedProviderError' in theme
assert 'there was an issue with the response' in theme
assert 'remote-prefs-18-receipt-type-filter' in entrypoint
print('PASS rapid-send guard tracks completion streams')
print('PASS rapid-send guard captures events before document handlers')
print('PASS rapid-send guard preserves the follow-up in the composer')
PY
