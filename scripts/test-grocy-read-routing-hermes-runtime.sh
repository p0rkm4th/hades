#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(readlink -f "$(command -v hermes || true)")
  [[ -z "$hermes_bin" ]] || hermes_python="$(dirname "$hermes_bin")/python3.11"
fi
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python 3.11 is unavailable' >&2; exit 2; }
hermes_source=$(env -u PYTHONPATH "$hermes_python" -c 'import pathlib, run_agent; print(pathlib.Path(run_agent.__file__).resolve().parent)')
work=$(mktemp -d "${TMPDIR:-/tmp}/hades-grocy-read-routing.XXXXXX")
chmod 700 "$work"
mkdir -m 700 "$work/home" "$work/hermes"
if [[ -n "${HADES_HINDSIGHT_PLUGIN:-}" ]]; then
  [[ -d "$HADES_HINDSIGHT_PLUGIN" ]] || { echo 'FAIL configured Hindsight plugin directory is unavailable' >&2; exit 2; }
  mkdir -m 700 "$work/hermes/plugins"
  ln -s "$(realpath "$HADES_HINDSIGHT_PLUGIN")" "$work/hermes/plugins/hindsight"
fi
printf '%s' 'synthetic-only' > "$work/grocy-api-key"
chmod 600 "$work/grocy-api-key"
trap 'find "$work" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "$work" 2>/dev/null || true' EXIT

HOME="$work/home" HERMES_HOME="$work/hermes" \
PYTHONPATH="$repo_dir/hermes:$repo_dir:$hermes_source" \
HADES_OWNER_SUBJECT_IDS=synthetic-owner \
HADES_TASK_STATE_FILE="$work/tasks.sqlite" \
HADES_EPSILON_STATE_FILE="$work/epsilon.sqlite" \
HADES_GROCY_AUDIT_FILE="$work/grocy-audit.jsonl" \
HADES_GROCY_URL=http://127.0.0.1:9 HADES_GROCY_API_KEY_FILE="$work/grocy-api-key" \
env -u GROCY_URL -u GROCY_API_KEY -u GROCY_API_KEY_FILE \
"$hermes_python" - "$repo_dir" <<'PY'
import sys
import datetime
import logging
import run_agent
import sitecustomize as hades

assert run_agent.AIAgent.run_conversation.__name__ == "_hades_run_conversation"
assert hades._hades_grocy_base_url() == "http://127.0.0.1:9"
assert hades._hades_grocy_api_key() == "synthetic-only"

# A missing canonical source is a user-facing limitation, not an architecture
# explanation. Keep this failure short, truthful, and free of internal names.
from unittest.mock import patch
with patch("urllib.request.urlopen", side_effect=OSError("synthetic source offline")):
    expiry_unavailable = hades._hades_direct_grocy_expiry_read(
        "Help me check the pantry expiry list."
    )
assert expiry_unavailable == (
    "I can't check the pantry's expiry dates right now because the pantry data "
    "isn't available. I haven't changed anything."
), expiry_unavailable
assert "grocy" not in expiry_unavailable.casefold()
assert "metadata" not in expiry_unavailable.casefold()
assert hades._hades_is_current_grocy_read_turn(
    True, "Is the old spaghetti recipe already on the shopping list?"
)
assert not hades._hades_is_current_grocy_read_turn(
    True, "Can I make the saved spaghetti recipe with current pantry stock?"
)
assert not hades._hades_is_current_grocy_read_turn(
    True, "Can I make dinner from ingredients on the shopping list?"
)
assert hades._hades_previous_user_message(
    [
        {"role": "user", "content": "Is the old spaghetti recipe already on the shopping list?"},
        {"role": "assistant", "content": "The list data isn't available."},
        {"role": "user", "content": "That’s not what I meant. I was asking whether it is already on the list."},
    ],
    "That’s not what I meant. I was asking whether it is already on the list.",
) == "Is the old spaghetti recipe already on the shopping list?"

# An ordinary chat turn passes through the recipe classifier, but private user
# text must not be copied into the INFO log as a routing diagnostic.
class CaptureLogs(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())

logger = logging.getLogger("hades.overlay")
old_level, old_propagate = logger.level, logger.propagate
capture = CaptureLogs()
logger.addHandler(capture)
logger.setLevel(logging.INFO)
logger.propagate = False
private_sentinel = "PRIVATE-LOG-REGRESSION-7f91"
try:
    assert hades._hades_direct_grocy_recipe_read(private_sentinel) is None
finally:
    logger.removeHandler(capture)
    logger.setLevel(old_level)
    logger.propagate = old_propagate
assert not any(private_sentinel in message for message in capture.messages), capture.messages
print("PASS ordinary-turn Grocy classification does not log raw user text")

reads = []
def synthetic_read(text):
    reads.append(text)
    return "The shared shopping list contains: milk."
real_direct_grocy_read = hades._hades_direct_household_grocy_read

agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-household",
    session_id="synthetic-household-chat",
    stream_delta_callback=lambda _chunk: None,
    base_url="http://127.0.0.1:9/v1",
    api_key="synthetic-only",
    provider="custom",
    api_mode="chat_completions",
    model="synthetic-no-call",
    enabled_toolsets=[],
    disabled_toolsets=[],
    quiet_mode=True,
    skip_context_files=True,
    skip_memory=True,
    skip_background_review=True,
    load_soul_identity=False,
)
import io, json, urllib.parse, urllib.request
canonical_requests = []
class CanonicalListResponse:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps([{"name": "Synthetic Grocy Milk"}]).encode()
def canonical_list_get(request, timeout=5):
    canonical_requests.append((request.get_method(), urllib.parse.urlparse(request.full_url).path))
    assert request.get_header("Grocy-api-key") == "synthetic-only"
    return CanonicalListResponse()
with patch("urllib.request.urlopen", side_effect=canonical_list_get):
    canonical_list_result = agent.run_conversation("What's on the shopping list?")
assert canonical_list_result.get("completed") is True, canonical_list_result
assert canonical_list_result.get("api_calls") == 0, canonical_list_result
assert canonical_list_result.get("final_response") == (
    "The shared shopping list contains: Synthetic Grocy Milk."
), canonical_list_result
assert canonical_requests == [("GET", "/api/objects/shopping_list")], canonical_requests
print("PASS an available canonical list read returns fixture state before the no-source fallback")

recipe_requests = []
recipe_payloads = {
    "/api/objects/recipes": [],
    "/api/objects/recipes_pos": [],
    "/api/objects/products": [],
    "/api/stock": [],
}
def canonical_recipe_get(request, timeout=5):
    path = urllib.parse.urlparse(request.full_url).path
    recipe_requests.append((request.get_method(), path))
    assert request.get_header("Grocy-api-key") == "synthetic-only"
    return CanonicalListResponseForPayload(recipe_payloads[path])
class CanonicalListResponseForPayload:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()
with patch("urllib.request.urlopen", side_effect=canonical_recipe_get):
    canonical_recipe_result = agent.run_conversation("Which recipes can we make right now?")
assert canonical_recipe_result.get("completed") is True, canonical_recipe_result
assert canonical_recipe_result.get("api_calls") == 0, canonical_recipe_result
assert canonical_recipe_result.get("final_response") == (
    "I couldn't find any stocked recipes in the shared pantry yet."
), canonical_recipe_result
assert recipe_requests == [
    ("GET", "/api/objects/recipes"),
    ("GET", "/api/objects/recipes_pos"),
    ("GET", "/api/objects/products"),
    ("GET", "/api/stock"),
], recipe_requests
print("PASS an available canonical recipe read completes before the no-source fallback")

with patch("urllib.request.urlopen", side_effect=OSError("synthetic source offline")):
    expiry_result = agent.run_conversation("Help me check the pantry expiry list.")
assert expiry_result.get("completed") is True, expiry_result
assert expiry_result.get("api_calls") == 0, expiry_result
assert expiry_result.get("final_response") == (
    "I can't check the pantry's expiry dates right now because the pantry data "
    "isn't available. I haven't changed anything."
), expiry_result
print("PASS an unavailable expiry source returns a task-specific limitation without a model guess")

hades._hades_direct_household_grocy_read = synthetic_read

from agent.memory_manager import memory_provider_tools_exposed
assert "memory" in agent.disabled_toolsets, agent.disabled_toolsets
assert memory_provider_tools_exposed(agent) is False
owner_agent = run_agent.AIAgent(
    gateway_session_key="hades-user-synthetic-owner",
    session_id="synthetic-owner-chat",
    stream_delta_callback=lambda _chunk: None,
    base_url="http://127.0.0.1:9/v1",
    api_key="synthetic-only",
    provider="custom",
    api_mode="chat_completions",
    model="synthetic-no-call",
    enabled_toolsets=[],
    disabled_toolsets=[],
    quiet_mode=True,
    skip_context_files=True,
    skip_memory=True,
    skip_background_review=True,
    load_soul_identity=False,
)
assert "memory" in owner_agent.disabled_toolsets, owner_agent.disabled_toolsets
assert memory_provider_tools_exposed(owner_agent) is False
print("PASS Hermes native memory-tool prompt gate is closed for HADES owner and household API agents")
captured_ordinary_prompts = []
original_hades_turn = hades._hades_original_run_conversation
def synthetic_ordinary_turn(agent, *args, **kwargs):
    captured_ordinary_prompts.append(agent.ephemeral_system_prompt)
    return {"final_response": "I'm here. What's up?", "messages": [], "api_calls": 1, "completed": True}
hades._hades_original_run_conversation = synthetic_ordinary_turn
ordinary_result = owner_agent.run_conversation("Hey, how's your morning going?")
hades._hades_original_run_conversation = original_hades_turn
assert ordinary_result.get("api_calls") == 1, ordinary_result
ordinary_prompt = "\n".join(str(prompt or "") for prompt in captured_ordinary_prompts).casefold()
assert "for ordinary conversation, speak naturally" not in ordinary_prompt, ordinary_prompt
assert "respond to what they said; do not describe system capacity" not in ordinary_prompt, ordinary_prompt
print("PASS ordinary chat reaches the model without HADES-authored generic behavior instructions")
offer = "I can add only the missing items to the shared shopping list if you'd like."
decline_history = [
    {"role": "assistant", "content": f"Not quite yet: recipe needs eggs. {offer}"},
    {"role": "user", "content": "No thanks."},
]
assert hades._hades_preemptive_grocy_offer_decline(
    "No thanks.", decline_history
) == "Okay, I won't add anything to the shopping list."
assert hades._hades_preemptive_grocy_offer_decline(
    "No thanks.", [{"role": "assistant", "content": offer}]
) == "Okay, I won't add anything to the shopping list."
assert hades._hades_preemptive_grocy_offer_decline(
    "No thanks, do we have milk?", decline_history
) is None
stale_offer_history = [
    {"role": "assistant", "content": offer},
    {"role": "user", "content": "Which recipes can we make?"},
    {"role": "assistant", "content": "Saved Grocy recipes: ..."},
    {"role": "user", "content": "No thanks."},
]
assert hades._hades_preemptive_grocy_offer_decline(
    "No thanks.", stale_offer_history
) is None
history = [
    {"role": "user", "content": "Add milk to the shopping list."},
    {"role": "assistant", "content": "Added milk to the shared shopping list and verified it."},
]
result = agent.run_conversation("What's on the shopping list?", conversation_history=history)
assert result.get("completed") is True, result
assert result.get("api_calls") == 0, result
assert result.get("final_response") == "The shared shopping list contains: milk.", result
assert reads == ["What's on the shopping list?"], reads

# Missing list data is unknown, not evidence that the list is empty. If neither
# the direct canonical read nor a scoped Grocy MCP tool is available, finish
# truthfully without asking the model to guess.
with patch.object(hades, "_hades_direct_household_grocy_read", return_value=None), \
     patch.object(hades, "_hades_grocy_tool_definitions", return_value=[]):
    unavailable_list = agent.run_conversation(
        "Is the old spaghetti recipe already on the shopping list?"
    )
assert unavailable_list.get("completed") is True, unavailable_list
assert unavailable_list.get("api_calls") == 0, unavailable_list
unavailable_text = unavailable_list.get("final_response", "").casefold()
assert "can't verify what's on the shopping list" in unavailable_text, unavailable_list
assert "list is empty" not in unavailable_text, unavailable_list
print("PASS unavailable canonical shopping-list reads preserve unknown state without a model guess")

followup_history = [
    {"role": "user", "content": "Is the old spaghetti recipe already on the shopping list?"},
    {"role": "assistant", "content": unavailable_list["final_response"]},
    {"role": "user", "content": "That’s not what I meant. I was asking whether it is already on the list."},
]
with patch.object(hades, "_hades_direct_household_grocy_read", return_value=None), \
     patch.object(hades, "_hades_grocy_tool_definitions", return_value=[]):
    unavailable_followup = agent.run_conversation(
        "That’s not what I meant. I was asking whether it is already on the list.",
        conversation_history=followup_history,
    )
assert unavailable_followup.get("completed") is True, unavailable_followup
assert unavailable_followup.get("api_calls") == 0, unavailable_followup
followup_text = unavailable_followup.get("final_response", "").casefold()
assert "can't verify what's on the shopping list" in followup_text, unavailable_followup
assert "not on the list" not in followup_text, unavailable_followup
print("PASS shopping-list correction follow-up keeps the prior canonical source boundary")

with patch.object(hades, "_hades_direct_grocy_recipe_read", return_value=None), \
     patch.object(hades, "_hades_grocy_tool_definitions", return_value=[]):
    unavailable_recipe = agent.run_conversation(
        "I'm looking at the spaghetti recipe in Grocy. Can you check whether we have the ingredients?"
    )
assert unavailable_recipe.get("completed") is True, unavailable_recipe
assert unavailable_recipe.get("api_calls") == 0, unavailable_recipe
recipe_text = unavailable_recipe.get("final_response", "").casefold()
assert "data isn't available" in recipe_text, unavailable_recipe
assert "media:" not in recipe_text, unavailable_recipe
print("PASS unavailable saved-recipe reads do not invent image artifacts or promise ungrounded checks")

# A current shared-list read must not be swallowed by an older recipe offer
# in the same conversation after the household accepted that offer.
reads.clear()
stale_recipe_history = [
    {"role": "user", "content": "Can I make Synthetic Pancakes again?"},
    {"role": "assistant", "content": "Not quite yet: Synthetic Pancakes still needs eggs. I can add only the missing items to the shared shopping list if you'd like."},
    {"role": "user", "content": "Yes, please"},
    {"role": "assistant", "content": "For Synthetic Pancakes, added and verified eggs. I did not change pantry quantities."},
    {"role": "user", "content": "What's on the shopping list?"},
]
stale_recipe_read = agent.run_conversation(
    "What's on the shopping list?", conversation_history=stale_recipe_history
)
assert stale_recipe_read.get("completed") is True, stale_recipe_read
assert stale_recipe_read.get("api_calls") == 0, stale_recipe_read
assert stale_recipe_read.get("final_response") == "The shared shopping list contains: milk.", stale_recipe_read
assert reads == ["What's on the shopping list?"], reads
print("PASS a current shared-list read outranks stale recipe intent after same-chat confirmation")

# Broad recipe inventory wording can contain the phrase "can we make";
# it must not be misparsed as a lookup for a recipe literally named "right now".
import io, json, urllib.parse, urllib.request
recipe_reads = []
real_urlopen = urllib.request.urlopen
payloads = {
    "/api/objects/recipes": [{"id": 1, "name": "Synthetic Pancakes"}],
    "/api/objects/recipes_pos": [],
    "/api/objects/products": [],
    "/api/stock": [],
}
def synthetic_grocy_open(request, timeout=5):
    assert request.get_header("Grocy-api-key") == "synthetic-only"
    path = urllib.parse.urlparse(request.full_url).path
    recipe_reads.append(path)
    return io.BytesIO(json.dumps(payloads[path]).encode())
urllib.request.urlopen = synthetic_grocy_open
inventory = hades._hades_direct_grocy_recipe_read(
    "Which recipes can we make right now?"
)
assert inventory and "Synthetic Pancakes" in inventory, inventory
assert "right now" not in inventory, inventory
assert recipe_reads == [
    "/api/objects/recipes", "/api/objects/recipes_pos",
    "/api/objects/products", "/api/stock",
], recipe_reads

# Natural meal-planning questions with a follow-up clause must use shared
# saved recipes and stock instead of falling through to unconstrained chat or
# treating the clause after "make" as a recipe title.
for meal_prompt in (
    "What is an easy dinner we can make tonight with what is already in the kitchen?",
    "Are there any meals we can make tonight without going shopping?",
):
    recipe_reads.clear()
    meal_answer = hades._hades_direct_grocy_recipe_read(meal_prompt)
    assert meal_answer and "Synthetic Pancakes" in meal_answer, (meal_prompt, meal_answer)
    assert "couldn't match" not in meal_answer.lower(), (meal_prompt, meal_answer)
    assert recipe_reads == [
        "/api/objects/recipes", "/api/objects/recipes_pos",
        "/api/objects/products", "/api/stock",
    ], (meal_prompt, recipe_reads)

meal_route_calls = []
real_recipe_read = hades._hades_direct_grocy_recipe_read
def synthetic_meal_read(text):
    meal_route_calls.append(text)
    return "The canonical pantry supports Synthetic Pancakes; nothing was changed."
hades._hades_direct_grocy_recipe_read = synthetic_meal_read
for meal_prompt in (
    "What is an easy dinner we can make tonight with what is already in the kitchen?",
    "Are there any meals we can make tonight without going shopping?",
):
    meal_result = agent.run_conversation(meal_prompt)
    assert meal_result.get("completed") is True, (meal_prompt, meal_result)
    assert meal_result.get("api_calls") == 0, (meal_prompt, meal_result)
    assert "canonical pantry supports Synthetic Pancakes" in meal_result.get("final_response", ""), meal_result
assert meal_route_calls == [
    "What is an easy dinner we can make tonight with what is already in the kitchen?",
    "Are there any meals we can make tonight without going shopping?",
], meal_route_calls
hades._hades_direct_grocy_recipe_read = real_recipe_read

expiry_route_calls = []
real_expiry_route = hades._hades_direct_grocy_expiry_recipe_compound_read
def synthetic_expiry_route(text):
    expiry_route_calls.append(text)
    return "Known to expire within 7 days: synthetic fruit. No stock was changed."
hades._hades_direct_grocy_expiry_recipe_compound_read = synthetic_expiry_route
expiry_prompt = "Which recipes can we make with food that will expire soon?"
expiry_result = agent.run_conversation(expiry_prompt)
assert expiry_result.get("completed") is True, expiry_result
assert expiry_result.get("api_calls") == 0, expiry_result
assert "Known to expire within 7 days: synthetic fruit" in expiry_result.get("final_response", ""), expiry_result
assert expiry_route_calls == [expiry_prompt], expiry_route_calls
hades._hades_direct_grocy_expiry_recipe_compound_read = real_expiry_route

# A recipe feasibility answer may offer one useful next step, but must not
# mutate the shopping list or infer that the user accepted the offer.
recipe_reads.clear()
payloads["/api/objects/recipes_pos"] = [
    {"id": 1, "recipe_id": 1, "product_id": 4, "amount": 2, "qu_id": 1},
]
payloads["/api/objects/products"] = [
    {"id": 4, "name": "eggs", "qu_id_stock": 1},
]
payloads["/api/stock"] = [
    {"product_id": 4, "amount_aggregated": 1},
]
feasibility = hades._hades_direct_grocy_recipe_read(
    "Can I make Synthetic Pancakes again?"
)
assert feasibility and "still needs eggs (1 more)" in feasibility, feasibility
assert "I can add only the missing items to the shared shopping list if you'd like." in feasibility, feasibility
assert recipe_reads == [
    "/api/objects/recipes", "/api/objects/recipes_pos",
    "/api/objects/products", "/api/stock",
], recipe_reads
payloads["/api/objects/recipes"].append(
    {"id": 2, "name": "Unrelated Rice Bake"}
)
payloads["/api/objects/recipes_pos"].append(
    {"recipe_id": 2, "product_id": 5, "amount": 1, "qu_id": 2}
)
payloads["/api/objects/products"].append(
    {"id": 5, "name": "rice", "qu_id_stock": 1}
)
payloads["/api/stock"].append(
    {"product_id": 5, "amount_aggregated": 1}
)
recipe_reads.clear()
feasibility = hades._hades_direct_grocy_recipe_read(
    "Can I make Synthetic Pancakes again?"
)
assert feasibility and "still needs eggs (1 more)" in feasibility, feasibility
assert not any(
    path.startswith("/api/objects/quantity_unit_conversions_resolved")
    for path in recipe_reads
), recipe_reads
urllib.request.urlopen = real_urlopen

authoring_prompts = [
    'Please add my new recipe HADES Synthetic Authoring Soup. It needs 1 milk and 2 eggs.',
    'Please add eggs to my recipe HADES Synthetic Authoring Soup.',
    'Save this recipe called HADES Synthetic Authoring Soup.',
]
for prompt in authoring_prompts:
    assert hades._hades_direct_grocy_recipe_add_missing(prompt, "synthetic-owner") is None, prompt
shopping_request = hades._hades_direct_grocy_recipe_add_missing(
    'Add the missing ingredients for HADES Synthetic Authoring Soup to the shopping list.',
    "synthetic-owner",
)
assert shopping_request and 'couldn\'t safely complete' in shopping_request.lower(), shopping_request
print("PASS Hermes runtime keeps a current Grocy list read deterministic after historical user and assistant mutation wording")
print("PASS broad recipe inventory wording reads canonical recipes instead of looking up 'right now' as a recipe name")
print("PASS natural dinner/meal questions use deterministic canonical recipe and stock reads")
print("PASS exact recipe feasibility offers one optional shopping-list next step without a write")
print("PASS a named recipe read does not resolve units for unrelated recipes")
print("PASS current-turn refusal closes only the immediately preceding optional shopping-list offer")
print("PASS recipe creation and ingredient-edit wording reaches owner tools; explicit missing-to-list intent remains on the safe Grocy route")

# A positive reply to the bounded feasibility offer must be an explicit,
# same-chat opt-in. It is compared with a fresh canonical read before write.
offer_products = [
    {"id": 11, "name": "milk", "qu_id_stock": 1, "qu_id_purchase": 1},
    {"id": 12, "name": "eggs", "qu_id_stock": 1, "qu_id_purchase": 1},
]
offer_recipes = [{"id": 21, "name": "Synthetic Pancakes"}]
offer_positions = [
    {"recipe_id": 21, "product_id": 11, "amount": 2, "qu_id": 1},
    {"recipe_id": 21, "product_id": 12, "amount": 2, "qu_id": 1},
]
offer_stock = [
    {"product_id": 11, "amount_aggregated": 2},
    {"product_id": 12, "amount_aggregated": 1},
]
offer_shopping = []
offer_requests = []
def offer_open(request, timeout=5):
    assert request.get_header("Grocy-api-key") == "synthetic-only"
    path = urllib.parse.urlparse(request.full_url).path
    method = request.get_method()
    body = json.loads(request.data.decode()) if request.data else None
    offer_requests.append((method, path, body))
    if path == "/api/objects/recipes":
        value = offer_recipes
    elif path == "/api/objects/recipes_pos":
        value = offer_positions
    elif path == "/api/objects/products":
        value = offer_products
    elif path == "/api/stock":
        value = offer_stock
    elif path == "/api/objects/shopping_list" and method == "GET":
        value = offer_shopping
    elif path == "/api/objects/shopping_list" and method == "POST":
        row = {"id": len(offer_shopping) + 1, "product_id": body["product_id"],
               "amount": body["amount"], "qu_id": body["qu_id"], "done": False}
        offer_shopping.append(row)
        value = {"created_object_id": row["id"]}
    else:
        raise AssertionError((method, path, body))
    return io.BytesIO(json.dumps(value).encode())

urllib.request.urlopen = offer_open
alpha_offer = hades._hades_direct_grocy_recipe_read("Can I make Synthetic Pancakes again?")
assert alpha_offer and "I can add only the missing items" in alpha_offer, alpha_offer
alpha_chat = "conversation:synthetic-alpha-chat"
alpha_offer = hades._hades_prepare_grocy_offer(alpha_offer, "synthetic-household", alpha_chat)
history_with_offer = [{"role": "assistant", "content": alpha_offer}]
cross_chat = hades._hades_grocy_offer_confirmation(
    "Yes, please", "synthetic-household", "household",
    "conversation:synthetic-beta-chat", history_with_offer,
)
assert cross_chat and "couldn't match that confirmation" in cross_chat, cross_chat
assert not offer_shopping and not any(row[0] == "POST" for row in offer_requests), offer_requests
changed_stock_offer = hades._hades_direct_grocy_recipe_read("Can I make Synthetic Pancakes again?")
assert changed_stock_offer and "I can add only the missing items" in changed_stock_offer
decline_chat = "conversation:synthetic-decline-chat"
decline_offer = hades._hades_prepare_grocy_offer(changed_stock_offer, "synthetic-household", decline_chat)
decline_result = hades._hades_grocy_offer_confirmation(
    "No thanks", "synthetic-household", "household", decline_chat,
    [{"role": "assistant", "content": decline_offer}],
)
assert decline_result == "Okay, I won't add anything to the shopping list.", decline_result
assert not offer_shopping and not any(row[0] == "POST" for row in offer_requests), offer_requests
compound_chat = "conversation:synthetic-compound-chat"
compound_offer = hades._hades_prepare_grocy_offer(
    changed_stock_offer, "synthetic-household", compound_chat
)
compound_result = hades._hades_grocy_offer_confirmation(
    "Yes, please, and do we have milk?", "synthetic-household", "household",
    compound_chat, [{"role": "assistant", "content": compound_offer}],
)
assert compound_result and "includes another request" in compound_result, compound_result
assert not offer_shopping and not any(row[0] == "POST" for row in offer_requests), offer_requests
stale_chat = "conversation:synthetic-stale-chat"
stale_offer = hades._hades_prepare_grocy_offer(changed_stock_offer, "synthetic-household", stale_chat)
offer_stock[1]["amount_aggregated"] = 2
stale_result = hades._hades_grocy_offer_confirmation(
    "Yes please", "synthetic-household", "household", stale_chat,
    [{"role": "assistant", "content": stale_offer}],
)
assert stale_result and "stock changed" in stale_result and "didn't add anything" in stale_result, stale_result
assert not offer_shopping and not any(row[0] == "POST" for row in offer_requests), offer_requests
offer_stock[1]["amount_aggregated"] = 1
fresh_result = hades._hades_grocy_offer_confirmation(
    "Yes, please", "synthetic-household", "household", alpha_chat,
    [{"role": "assistant", "content": alpha_offer}],
)
assert fresh_result and "added and verified eggs" in fresh_result, fresh_result
assert len(offer_shopping) == 1 and offer_shopping[0]["product_id"] == 12, offer_shopping
assert sum(row[0] == "POST" for row in offer_requests) == 1, offer_requests
assert hades._hades_grocy_offer_confirmation(
    "Yes, please", "synthetic-household", "household", alpha_chat,
    [{"role": "assistant", "content": fresh_result}],
) is None
assert sum(row[0] == "POST" for row in offer_requests) == 1, offer_requests
offer_shopping.clear()
offer_stock[1] = {"product_id": 12, "amount_aggregated": 2, "best_before_date": "2000-01-01"}
expired_add = hades._hades_direct_grocy_recipe_add_missing(
    "Add the missing ingredients for Synthetic Pancakes to the shopping list",
    "synthetic-household",
)
assert expired_add and "added and verified eggs" in expired_add, expired_add
assert len(offer_shopping) == 1 and offer_shopping[0]["product_id"] == 12
assert offer_shopping[0]["amount"] == 2, offer_shopping
offer_stock[:] = [
    {"product_id": 11, "product": {"name": "milk"}, "amount_aggregated": 2,
     "best_before_date": (datetime.date.today() + datetime.timedelta(days=2)).isoformat()},
    {"product_id": 12, "product": {"name": "eggs"}, "amount_aggregated": 1,
     "best_before_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat()},
]
offer_products[:] = [
    {"id": 11, "name": "milk", "qu_id_stock": 1},
    {"id": 12, "name": "eggs", "qu_id_stock": 1},
    {"id": 13, "name": "cocoa", "qu_id_stock": 1},
]
offer_recipes[:] = [
    {"id": 21, "name": "Synthetic Pancakes"},
    {"id": 22, "name": "Synthetic Cocoa Pudding"},
]
offer_positions[:] = [
    {"recipe_id": 21, "product_id": 11, "amount": 1, "qu_id": 1},
    {"recipe_id": 21, "product_id": 12, "amount": 1, "qu_id": 1},
    {"recipe_id": 22, "product_id": 11, "amount": 1, "qu_id": 1},
    {"recipe_id": 22, "product_id": 13, "amount": 1, "qu_id": 1},
]
compound_write_count = sum(row[0] == "POST" for row in offer_requests)
compound_food = hades._hades_direct_grocy_expiry_recipe_compound_read(
    "Which recipes can we make with food that will expire soon?"
)
assert compound_food and "Recipes you can make using food that expires within 7 days: Synthetic Pancakes." in compound_food, compound_food
assert "Synthetic Cocoa Pudding (still needs cocoa (1 more))" in compound_food, compound_food
assert "Known to expire within 7 days: milk (2 units," in compound_food, compound_food
assert "Known expired: none." in compound_food, compound_food
assert sum(row[0] == "POST" for row in offer_requests) == compound_write_count, offer_requests
compound_food = hades._hades_direct_grocy_expiry_recipe_compound_read(
    "Can we make Synthetic Cocoa Pudding for dinner, and what food is going to expire?"
)
assert compound_food and "Not quite yet: Synthetic Cocoa Pudding still needs cocoa (1 more)" in compound_food, compound_food
assert "Known to expire within 7 days: milk" in compound_food, compound_food
assert sum(row[0] == "POST" for row in offer_requests) == compound_write_count, offer_requests
urllib.request.urlopen = real_urlopen
print("PASS Grocy offer affirmative is same-chat, stale-stock-checked, single-write, and canonically read back")
print("PASS Grocy offer decline and cross-chat confirmation perform no shopping-list write")
print("PASS expired Grocy stock does not suppress missing recipe ingredients from shopping list")
print("PASS named dinner feasibility and expiry data are both returned without writes")
PY
