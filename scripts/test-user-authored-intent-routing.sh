#!/usr/bin/env bash
set -euo pipefail

# Assistant prose is conversational context, not authority to expose a HADES
# capability on the next short follow-up.
python - <<'PY'
import importlib.util
import logging

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("hades_overlay", "hermes/sitecustomize.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

history = [
    {"role": "user", "content": "Can you explain why Python generators are useful?"},
    {"role": "assistant", "content": (
        "Generators are useful for web scraping and online research pipelines. "
        "You can also inspect server logs and search files with code."
    )},
]
followup = overlay._hades_conversation_intent_text("Why?", history)
assert "Python generators" in followup and followup.endswith("Why?"), followup
assert "web scraping" not in followup and "server logs" not in followup, followup
assert not overlay._HADES_LIVE_WEB_INTENT.search(followup), followup
assert not overlay._HADES_PAGE_INTENT.search(followup), followup
assert not overlay._HADES_GROCY_ACTION_INTENT.search(followup), followup
assert not overlay._hades_is_homelab_intent(followup), followup

# A real user request remains in the bounded routing context, so a contextual
# follow-up to requested public research can still select that capability.
research_history = [
    {"role": "user", "content": "Research the latest Python release online."},
    {"role": "assistant", "content": "I found the release notes."},
]
research_followup = overlay._hades_conversation_intent_text("What changed?", research_history)
assert overlay._HADES_LIVE_WEB_INTENT.search(research_followup), research_followup
print("PASS assistant prose cannot activate unrelated HADES intent; user-authored domain context remains routable")
PY
