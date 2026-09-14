#!/usr/bin/env bash
set -eu

# Deterministic long-conversation dogfood. It exercises the routing context
# contract with three identities and shared/private state; it does not contact
# owner services or claim model-quality acceptance.
python - <<'PY'
import importlib.util
import os

spec = importlib.util.spec_from_file_location("hades_overlay", "hermes/sitecustomize.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

os.environ["HADES_OWNER_SUBJECT_ID"] = "alpha"
assert overlay._hades_session_scope("hades-user-alpha") == "owner"
assert overlay._hades_session_scope("hades-user-beta") == "household"
assert overlay._hades_session_scope("hades-user-gamma") == "household"

private = {
    "alpha": "Alpha hates mushrooms",
    "beta": "Beta prefers spicy food",
    "gamma": "Gamma avoids dairy",
}
shared = {"milk": 2, "mushrooms": 0}
histories = {user: [] for user in private}

for turn in range(60):
    for user in private:
        topic = ("pantry" if turn % 5 == 0 else
                 "weather" if turn % 7 == 0 else
                 "correction" if turn == 23 else "conversation")
        content = f"{user} turn {turn} topic {topic}"
        if user == "alpha" and turn == 23:
            content = "correction: Alpha now likes mushrooms"
        if user == "beta" and turn == 30:
            shared["milk"] -= 1
            content = "consume milk"
        histories[user].append({"role": "user", "content": content})
        bounded = overlay._hades_conversation_intent_text(content, histories[user])
        assert content in bounded
        assert private[user] not in bounded
        if user != "alpha":
            assert "Alpha now likes mushrooms" not in bounded

# A new chat must not inherit the previous user's or previous topic's context.
fresh = overlay._hades_conversation_intent_text(
    "what is the pantry state?", []
)
assert fresh == "what is the pantry state?"
assert shared == {"milk": 1, "mushrooms": 0}
print("PASS multi-user long synthetic dogfood")
PY
