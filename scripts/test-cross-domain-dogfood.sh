#!/usr/bin/env bash
set -eu

# Synthetic cross-domain conversation contract. Each response is produced from
# a separate fake authority so the test can prove that context is composed,
# not substituted, without using owner data or external credentials.
python - <<'PY'
import importlib.util
import logging
import os

logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location("hades_overlay", "hermes/sitecustomize.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
os.environ["HADES_OWNER_SUBJECT_ID"] = "alpha"

memory = {"alpha": {"preference": "hates mushrooms"}, "beta": {}}
grocy = {"milk": 1, "onions": 2}
web = {"recipe": "mushroom-free pasta"}

def session(user):
    return f"hades-user-{user}"

def answer(user, request):
    scope = overlay._hades_session_scope(session(user))
    if "afford" in request or "finance" in request:
        return "Finance unavailable: owner authorization is required."
    if "what did alpha tell" in request.lower():
        return "Private memory is unavailable for another user."
    if "online" in request.lower() or "find a recipe" in request.lower():
        return f"Web result: {web['recipe']}."
    if "what recipe" in request.lower():
        return f"Recipe context: {web['recipe']}; pantry truth: {grocy}."
    if "add" in request.lower() and "don't add onions" in request.lower():
        grocy["milk"] = 2
        return "Grocy shopping state updated and verified; onions excluded."
    if "missing" in request.lower():
        return f"Grocy says missing items are computed from pantry state: {grocy}."
    if "agent zero" in request.lower() and scope != "owner":
        return "Agent Zero unavailable for household scope."
    return f"Personal context for {user}: {memory[user].get('preference', 'none')}."

# The request is deliberately phrased as a recall of the current user's fact;
# no model-generated text may turn Beta's identity into Alpha's bank.
alpha_answer = answer("alpha", "what do I hate?")
assert "hates mushrooms" in alpha_answer
beta_private = answer("beta", "what did Alpha tell you about dinner")
assert "hates mushrooms" not in beta_private
assert "mushroom-free" in answer("alpha", "find a recipe online using what we have"), answer("alpha", "find a recipe online using what we have")
assert "pantry truth" in answer("alpha", "what recipe did I mention earlier and are we missing anything"), answer("alpha", "what recipe did I mention earlier and are we missing anything")
assert "Finance unavailable" in answer("beta", "we need groceries, can we afford it"), answer("beta", "we need groceries, can we afford it")
assert "Agent Zero unavailable" in answer("beta", "ask Agent Zero to inspect it")
assert "onions excluded" in answer("alpha", "add whatever we're missing but don't add onions")
assert grocy["milk"] == 2 and grocy["onions"] == 2
print("PASS cross-domain synthetic dogfood")
PY
