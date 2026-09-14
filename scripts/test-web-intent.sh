#!/usr/bin/env bash
set -euo pipefail

# Secret-free regression coverage for the bounded live-information intent
# contract. Importing the overlay is safe without Hermes' optional packages:
# its provider setup is guarded and the regex is defined before that setup.

python - <<'PY'
import importlib.util
from pathlib import Path

path = Path("hermes/sitecustomize.py")
source = path.read_text().lower()
spec = importlib.util.spec_from_file_location("hades_overlay_test", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for phrase in (
    "title or snippet is not evidence",
    "do not infer or invent an answer",
):
    assert phrase in source, phrase

direct = (
    "what happened today?",
    "who won that game?",
    "what was the score?",
    "did they release another one?",
    "what's the latest version?",
)
for prompt in direct:
    assert module._HADES_LIVE_WEB_INTENT.search(prompt), prompt

history_followup = "what happened today?\nassistant: The event was discussed.\nanything newer?"
assert module._HADES_LIVE_WEB_INTENT.search(history_followup)

for prompt in ("remember my test drink", "what food do we have?"):
    assert not module._HADES_LIVE_WEB_INTENT.search(prompt), prompt

print("PASS bounded live-web intent regression")
PY
