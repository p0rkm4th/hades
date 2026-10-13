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
import json
import os
import tempfile
import urllib.request
from datetime import date, timedelta
from pathlib import Path
import run_agent
import sitecustomize as hades
from plugins.memory.hindsight import HindsightMemoryProvider

assert run_agent.AIAgent.run_conversation.__name__ == "_hades_run_conversation"
assert hades._hades_grocy_base_url() == "http://127.0.0.1:9"
assert hades._hades_grocy_api_key() == "synthetic-only"
actual_grocy_read = hades._hades_direct_household_grocy_read
grocy_requests = []
class SyntheticGrocyResponse:
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return b'[{"product":{"name":"milk"},"amount":2}]'
def synthetic_grocy_urlopen(request, timeout=5):
    grocy_requests.append((request.full_url, request.get_method(), timeout))
    return SyntheticGrocyResponse()
real_urlopen = urllib.request.urlopen
urllib.request.urlopen = synthetic_grocy_urlopen
try:
    for prompt in (
        "what's in my kitchen?",
        "what ingredients do i have in my kiytchen?",
    ):
        grocy_requests.clear()
        answer = actual_grocy_read(prompt)
        assert "milk (2 units)" in answer, (prompt, answer)
        assert len(grocy_requests) == 1 and grocy_requests[0][0].endswith("/api/stock"), (prompt, grocy_requests)
finally:
    urllib.request.urlopen = real_urlopen

# Exercise the actual provider handler as a fail-closed mutation boundary.
# The fake downstream handler records calls but never touches Hindsight.
provider = object.__new__(HindsightMemoryProvider)
provider._memory_mode = "hybrid"
saved_handlers = HindsightMemoryProvider._TOOL_HANDLERS
mutation_calls = []
HindsightMemoryProvider._TOOL_HANDLERS = dict(saved_handlers)
HindsightMemoryProvider._TOOL_HANDLERS["hindsight_retain"] = (
    "content",
    lambda _provider, args: mutation_calls.append(dict(args)) or "Memory stored successfully.",
    "Failed to store memory",
)
try:
    read_schemas = provider.get_tool_schemas()
    assert "hindsight_retain" not in {schema["name"] for schema in read_schemas}
    blocked = provider.handle_tool_call(
        "hindsight_retain", {"content": "What ingredients do I have in my kitchen?"}
    )
    assert "not changed" in blocked and mutation_calls == [], (blocked, mutation_calls)
    for prompt in (
        "remember that I keep the spare key in the drawer",
        "forget the old router",
        "update your memory: the server is now Maple",
    ):
        blocked = provider.handle_tool_call("hindsight_retain", {"content": prompt})
        assert "not changed" in blocked and mutation_calls == [], (prompt, blocked, mutation_calls)
finally:
    HindsightMemoryProvider._TOOL_HANDLERS = saved_handlers

reads = []
def synthetic_read(text):
    reads.append(text)
    return "The shared shopping list contains: milk."
hades._hades_direct_household_grocy_read = synthetic_read

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

for inventory_prompt in (
    "what's in my kitchen?",
    "what’s in the kitchen",
    'what ingredients do i have?',
    'what ingredients do i have in my kiytchen?',
    'whats in the kichen?',
    "what's in my pantry?",
    'what food do we have?',
    'do we have eggs?',
):
    reads.clear()
    inventory_result = agent.run_conversation(inventory_prompt)
    assert inventory_result.get('completed') is True, (inventory_prompt, inventory_result)
    assert inventory_result.get('api_calls') == 0, (inventory_prompt, inventory_result)
    assert reads == [inventory_prompt], (inventory_prompt, reads)

network_reads = []
def synthetic_homelab_source(tool_name, arguments=None):
    network_reads.append(tool_name)
    return {
        "status": "OK",
        "online_names": ["Thanatos", "Synthetic Node"],
        "inventory_only_names": ["Unknown Node"],
        "availability_summary": [
            {"name": "Synthetic Node check", "status": "down", "freshness": "FRESH"},
        ],
        "resources": [
            {"name": "Thanatos", "currently_online": True, "runtime_status": "running",
             "runtime_detail": {"name": "Thanatos", "vmid": 101, "status": "running", "node": "Synthetic Host"}},
            {"name": "Hermes", "currently_online": True, "runtime_status": "running",
             "runtime_detail": {"name": "Hermes", "vmid": 103, "status": "running", "node": "Synthetic Host"}},
            {"name": "Synthetic Node", "currently_online": True, "runtime_status": "running",
             "runtime_detail": {"name": "Synthetic Node", "vmid": 102, "status": "running", "node": "Synthetic Host"}},
        ],
    }
hades._hades_direct_homelab_tool_result = synthetic_homelab_source
hades._hades_configured_homelab_records = lambda: [
    {"name": "Thanatos", "aliases": ["Thanatos"]},
    {"name": "Hermes", "aliases": ["Hermes"]},
]
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
assert owner_agent._hades_session_scope == "owner", owner_agent._hades_session_scope
palworld_prompt = "I think i wanna build a game server for palworld, can you spin one up for me?"
palworld_result = owner_agent.run_conversation(palworld_prompt)
assert palworld_result.get("completed") is True and palworld_result.get("api_calls") == 0, palworld_result
assert "approved `palworld`" in palworld_result.get("final_response", ""), palworld_result
assert network_reads == [], network_reads
print("PASS Palworld provisioning request receives an explicit bounded-capability gap, not a homelab status dump")
for prompt in ("what's in my network?", "what devices are in my network?", "what's running in my homelab?", "what servers do i have?"):
    network_reads.clear()
    result = owner_agent.run_conversation(prompt)
    assert result.get("api_calls") == 0 and "Thanatos" in result.get("final_response", ""), (prompt, result)
    assert network_reads == ["homelab_summary"], (prompt, network_reads)
    network_reads.clear()

# Same-chat owner health follow-ups must retain node scope but refresh and
# synthesize the new operation from a new canonical summary read.
homelab_history = []
for prompt, expected in (
    ("Hows my network", "Some configured homelab evidence needs attention"),
    ("what about Thanatos and all the nodes?", "Thanatos VM 101"),
    ("are any of the nodes showing any problems?", "Failing configured checks"),
):
    request_history = [*homelab_history, {"role": "user", "content": prompt}]
    network_reads.clear()
    result = owner_agent.run_conversation(prompt, conversation_history=request_history)
    assert result.get("completed") is True and result.get("api_calls") == 0, result
    assert expected in result.get("final_response", ""), (prompt, result)
    assert network_reads == ["homelab_summary"], (prompt, network_reads)
    if prompt == "are any of the nodes showing any problems?":
        assert "Repository backup freshness" not in result["final_response"], result
        assert "No blocker was reported" not in result["final_response"], result
        assert len(result["final_response"]) < 1200, result
    homelab_history.extend([
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": result["final_response"]},
    ])
print("PASS same-chat homelab health keeps node scope and refreshes the summary per operation")

named_history = [
    {"role": "user", "content": "Hows my network"},
    {"role": "assistant", "content": "Synthetic network summary"},
    {"role": "user", "content": "what about thanatos or hermes?"},
]
network_reads.clear()
named_followup = owner_agent.run_conversation(
    "what about thanatos or hermes?", conversation_history=named_history,
)
named_answer = named_followup.get("final_response", "")
assert named_followup.get("completed") is True and named_followup.get("api_calls") == 0, named_followup
assert "Thanatos" in named_answer and "Hermes" in named_answer, named_followup
assert "Greek" not in named_answer and not named_answer.lstrip().startswith("{"), named_followup
assert network_reads == ["homelab_summary"], network_reads
print("PASS same-chat homelab aliases resolve against current per-node source after natural 'Hows' wording")

original_model_run = hades._hades_original_run_conversation
original_grocy_definitions = hades._hades_grocy_tool_definitions
original_recipe_read = hades._hades_direct_grocy_recipe_read
synthetic_grocy_tools = [
    {"type": "function", "function": {"name": "mcp_grocy_recipes_list_tool", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "mcp_grocy_recipe_details_tool", "parameters": {"type": "object", "properties": {"recipe_name": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "mcp_grocy_stock_overview_tool", "parameters": {"type": "object", "properties": {}}}},
]
hades._hades_grocy_tool_definitions = lambda _getter: synthetic_grocy_tools
hades._hades_direct_grocy_recipe_read = lambda _text: None
captured_choices = []
def synthetic_model_fallback(_agent, prompt, *args, **kwargs):
    captured_choices.append(dict(getattr(_agent, "request_overrides", {}) or {}))
    return {
        'final_response': 'synthetic ordinary-chat response',
        'messages': [{'role': 'assistant', 'content': 'synthetic ordinary-chat response'}],
        'api_calls': 1,
        'completed': True,
}
hades._hades_original_run_conversation = synthetic_model_fallback
try:
    for prompt, expected_tool in (
        ("list my recipes", "mcp_grocy_recipes_list_tool"),
        ("what recipes dfo i have?", "mcp_grocy_recipes_list_tool"),
        ("what ingredients are in Chicken Cordon Bleu?", "mcp_grocy_recipe_details_tool"),
        ("tell me about the best cordon bleu recipe", "mcp_grocy_recipe_details_tool"),
    ):
        captured_choices.clear()
        result = agent.run_conversation(prompt)
        assert result.get("completed") is True, (prompt, result)
        assert captured_choices and captured_choices[-1].get("tool_choice", {}).get("function", {}).get("name") == expected_tool, (prompt, captured_choices, result)
    detail_history = [
        {"role": "user", "content": "what recipes dfo i have?"},
        {"role": "assistant", "content": "Synthetic recipe list"},
        {"role": "user", "content": "tell me about the best cordon bleu recipe"},
    ]
    captured_choices.clear()
    detail_result = agent.run_conversation(
        "tell me about the best cordon bleu recipe",
        conversation_history=detail_history,
    )
    assert detail_result.get("completed") is True, detail_result
    assert captured_choices and captured_choices[-1].get("tool_choice", {}).get("function", {}).get("name") == "mcp_grocy_recipe_details_tool", (captured_choices, detail_result)
    # Historical recipe-list operation must not remain selected for the new
    # current-turn operation; kitchen stock is routed deterministically.
    captured_choices.clear()
    stock_history = [
        {"role": "user", "content": "list my recipes"},
        {"role": "assistant", "content": "Synthetic recipe list"},
        {"role": "user", "content": "whats in my kiytchen?"},
    ]
    stock_result = agent.run_conversation("whats in my kiytchen?", conversation_history=stock_history)
    assert stock_result.get("completed") is True and stock_result.get("api_calls") == 0, stock_result
    assert "milk" in stock_result.get("final_response", "").lower(), stock_result
    assert captured_choices == [], "stock read should use the direct canonical Grocy route"
    print("PASS same-chat Grocy operation changes select recipe details and direct stock independently")

    # Finance row aggregation is deterministic and same-chat follow-ups retain
    # the merchant/period rather than repeating only source coverage metadata.
    today = date.today()
    coverage = today - timedelta(days=31)
    with tempfile.TemporaryDirectory(prefix="hades-finance-task-completion-") as finance_dir:
        finance_path = Path(finance_dir) / "synthetic.csv"
        finance_path.write_text(
            "Date,Description,Amount,Category,Status\n"
            f"{today.year}-01-12,7 Brew,-10.00,Coffee,Posted\n"
            f"{today.year}-02-04,7BREW Coffee,-12.50,Coffee,Cleared\n"
            f"{today.year}-02-08,7 Brew refund,2.00,Coffee,Posted\n"
            f"{today.year}-03-01,Synthetic Grocery,-44.00,Groceries,Posted\n"
            f"{coverage.isoformat()},7 Brew,-3.00,Coffee,Pending\n"
            f"{today.year - 1}-12-20,7 Brew,-100.00,Coffee,Posted\n"
            f"{(today - timedelta(days=366)).isoformat()},7 Brew outside window,-500.00,Coffee,Posted\n",
            encoding="utf-8",
        )
        previous_finance_path = os.environ.get("HADES_FINANCE_CSV_PATH")
        os.environ["HADES_FINANCE_CSV_PATH"] = str(finance_path)
        try:
            finance_prompt = "How much have I spent at 7 Brew year-to-date?"
            first_history = [{"role": "user", "content": finance_prompt}]
            first_finance = owner_agent.run_conversation(
                finance_prompt, conversation_history=first_history,
            )
            assert "posted net spending at 7 Brew is $20.50" in first_finance.get("final_response", ""), first_finance
            followup_history = [
                {"role": "user", "content": finance_prompt},
                {"role": "assistant", "content": "CSV coverage metadata"},
                {"role": "user", "content": "But I need to know"},
                {"role": "assistant", "content": first_finance["final_response"]},
                {"role": "user", "content": "Calculate how much I spent there"},
            ]
            second_finance = owner_agent.run_conversation(
                "Calculate how much I spent there", conversation_history=followup_history,
            )
            assert "posted net spending at 7 Brew is $20.50" in second_finance.get("final_response", ""), second_finance
            assert "Pending transactions total $3.00" in second_finance.get("final_response", ""), second_finance
            assert "not a complete year-to-date total" in second_finance.get("final_response", ""), second_finance
            last_year_finance = owner_agent.run_conversation(
                "how much did I spend on 7 brew in the last year?",
            )
            last_year_answer = last_year_finance.get("final_response", "")
            assert "posted net spending at 7 brew is $120.50" in last_year_answer, last_year_finance
            assert "Pending transactions total $3.00" in last_year_answer, last_year_finance
            assert "not a complete-period total" in last_year_answer, last_year_finance
            assert "$500.00" not in last_year_answer, last_year_finance
            print("PASS same-chat finance follow-ups deterministically aggregate rows with posted, refund, pending, and coverage semantics")
        finally:
            if previous_finance_path is None:
                os.environ.pop("HADES_FINANCE_CSV_PATH", None)
            else:
                os.environ["HADES_FINANCE_CSV_PATH"] = previous_finance_path
    for ordinary_prompt in (
        "what is a neural network?",
        "explain TCP networking",
        "how does a social network grow?",
        "what's a network effect?",
    ):
        network_reads.clear()
        owner_agent.run_conversation(ordinary_prompt)
        assert network_reads == [], (ordinary_prompt, network_reads)
    for ordinary_prompt in (
        'how does a refrigerator cool food?',
        'what does kitchen mean in restaurant terminology?',
        'explain neural networks',
        'help me write a Python function',
        'what should i cook for dinner?',
    ):
        reads.clear()
        ordinary_result = agent.run_conversation(ordinary_prompt)
        assert reads == [], (ordinary_prompt, reads)
finally:
    hades._hades_original_run_conversation = original_model_run
    hades._hades_grocy_tool_definitions = original_grocy_definitions
    hades._hades_direct_grocy_recipe_read = original_recipe_read

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
baseline_payloads = {path: list(rows) for path, rows in payloads.items()}
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

# A named recipe-ingredient request is a distinct canonical read operation.
# The previous recipe-list result may remain in chat context, but the current
# turn must be resolved to the named recipe's ingredient positions.
payloads["/api/objects/recipes"] = [
    {"id": 1, "name": "Chicken Cordon Bleu"},
    {"id": 2, "name": "Synthetic Recipe B"},
    {"id": 3, "name": "Synthetic Recipe C"},
]
payloads["/api/objects/recipes_pos"] = [
    {"id": 11, "recipe_id": 1, "product_id": 10, "amount": 2, "qu_id": 1},
    {"id": 12, "recipe_id": 1, "product_id": 11, "amount": 0.5, "qu_id": 2},
    {"id": 13, "recipe_id": 2, "product_id": 12, "amount": 3, "qu_id": 1},
]
payloads["/api/objects/products"] = [
    {"id": 10, "name": "Synthetic Chicken"},
    {"id": 11, "name": "Synthetic Cheese"},
    {"id": 12, "name": "Unrelated Product"},
]
payloads["/api/objects/quantity_units"] = [
    {"id": 1, "name": "piece", "name_plural": "pieces"},
    {"id": 2, "name": "kilogram", "name_plural": "kilograms"},
]
recipe_reads.clear()
ingredient_history = [
    {"role": "user", "content": "list my recipes"},
    {"role": "assistant", "content": "Synthetic recipe list"},
    {"role": "user", "content": "what ingredients are in Chicken Cordon Bleu?"},
]
ingredient_result = agent.run_conversation(
    "what ingredients are in Chicken Cordon Bleu?",
    conversation_history=ingredient_history,
)
assert ingredient_result.get("completed") is True, ingredient_result
assert ingredient_result.get("api_calls") == 0, ingredient_result
ingredient_answer = ingredient_result.get("final_response", "")
assert "Grocy lists these ingredients for Chicken Cordon Bleu" in ingredient_answer, ingredient_result
assert "Synthetic Chicken (2 pieces)" in ingredient_answer, ingredient_result
assert "Synthetic Cheese (0.5 kilograms)" in ingredient_answer, ingredient_result
assert "Unrelated Product" not in ingredient_answer, ingredient_result
assert recipe_reads == [
    "/api/objects/recipes", "/api/objects/recipes_pos",
    "/api/objects/products", "/api/stock", "/api/objects/quantity_units",
], recipe_reads
print("PASS same-chat named recipe ingredient read returns only the current recipe from canonical Grocy")
payloads.clear()
payloads.update(baseline_payloads)

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
print("PASS kitchen and typo prompts read synthetic canonical Grocy stock")
print("PASS natural network inventory prompts read synthetic canonical homelab source; educational networking stays model-only")
print("PASS Hindsight model retain calls are rejected and automatic sync is disabled")
print("PASS Grocy offer affirmative is same-chat, stale-stock-checked, single-write, and canonically read back")
print("PASS Grocy offer decline and cross-chat confirmation perform no shopping-list write")
print("PASS expired Grocy stock does not suppress missing recipe ingredients from shopping list")
print("PASS named dinner feasibility and expiry data are both returned without writes")
PY
