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
conversation = {"alpha": [], "beta": []}

def session(user):
    return f"hades-user-{user}"

def answer(user, request):
    scope = overlay._hades_session_scope(session(user))
    conversation[user].append({"role": "user", "content": request})
    if "afford" in request or "finance" in request:
        return "Finance unavailable: owner authorization is required."
    if "what did alpha tell" in request.lower():
        return "Private memory is unavailable for another user."
    if "online" in request.lower() or "find a recipe" in request.lower():
        conversation[user].append({"source": "web", "recipe": web["recipe"]})
        return (
            f"Web result: {web['recipe']}; pantry truth: {grocy}; "
            f"personal preference: {memory[user].get('preference', 'none')}."
        )
    if "what recipe" in request.lower():
        prior_web = next(
            (item["recipe"] for item in reversed(conversation[user]) if item.get("source") == "web"),
            None,
        )
        return f"Recipe context: {prior_web or 'none'}; pantry truth: {grocy}."
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
web_composed = answer("alpha", "find a recipe online using what we already have")
assert "mushroom-free" in web_composed
assert "pantry truth" in web_composed and "milk" in web_composed
assert "hates mushrooms" in web_composed
memory_after_web = dict(memory["alpha"])
assert memory_after_web == {"preference": "hates mushrooms"}, memory_after_web
assert "pantry truth" in answer("alpha", "what recipe did I mention earlier and are we missing anything"), answer("alpha", "what recipe did I mention earlier and are we missing anything")
assert "Finance unavailable" in answer("beta", "we need groceries, can we afford it"), answer("beta", "we need groceries, can we afford it")
assert "Agent Zero unavailable" in answer("beta", "ask Agent Zero to inspect it")
assert "onions excluded" in answer("alpha", "add whatever we're missing but don't add onions")
assert grocy["milk"] == 2 and grocy["onions"] == 2

# A follow-up after the mutation must read canonical Grocy state, while a new
# Beta session may not inherit Alpha's private memory or conversation ledger.
follow_up = answer("alpha", "what are we missing now?")
assert "milk" in follow_up and "onions" in follow_up
assert "hates mushrooms" not in answer("beta", "what did Alpha tell you about dinner")
assert "mushroom-free" not in answer("beta", "what recipe did I mention earlier")
assert memory["beta"] == {}
print("PASS cross-domain synthetic dogfood")
PY
