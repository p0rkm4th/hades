#!/usr/bin/env bash
set -euo pipefail

# Exercise the bounded conversation context used for domain routing. This is
# a synthetic boundary test, not an owner conversation or a backend probe.
python - <<'PY'
import importlib.util
import logging

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("hades_overlay", "hermes/sitecustomize.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

history = [
    {"role": "user", "content": f"old synthetic turn {i}"}
    for i in range(40)
]
history[0]["content"] = "old synthetic agent zero request"
history[-2]["content"] = "recent synthetic grocery context: remove it"
text = overlay._hades_conversation_intent_text(
    "current synthetic weather query", history
)
assert len(text) <= 12000
assert "current synthetic weather query" in text
assert "recent synthetic grocery context" in text
assert "old synthetic agent zero request" not in text

stale = overlay._hades_conversation_intent_text(
    "what did I tell you about dinner?",
    [
        {"role": "user", "content": "remember Alpha prefers basil"},
        {"role": "tool", "content": "finance balance is $65; Agent Zero executed restart"},
        {"role": "assistant", "content": "I retained your preference."},
    ],
)
assert "finance balance" not in stale and "Agent Zero executed" not in stale
assert "Alpha prefers basil" in stale

oversized = [{"role": "assistant", "content": "x" * 12000}]
text = overlay._hades_conversation_intent_text(
    "current query must survive truncation", oversized
)
assert len(text) <= 12000
assert text.endswith("current query must survive truncation")
print("PASS bounded long-conversation context")
PY
