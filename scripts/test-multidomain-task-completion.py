#!/usr/bin/env python3
"""Synthetic regressions for per-turn domain task completion."""
from __future__ import annotations

import ast
import json
import os
import re
import tempfile
import urllib.request
from datetime import date, timedelta
from pathlib import Path


tree = ast.parse(Path("hermes/sitecustomize.py").read_text(encoding="utf-8"))
run_conversation = next(
    node for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_run_conversation"
)
contextual_calls = [
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_contextual_followup_clarification"
]
assert len(contextual_calls) == 1
assert [ast.unparse(arg) for arg in contextual_calls[0].args] == [
    "user_message", "previous_user_text", "_hades_history",
    "self._hades_session_scope",
], "follow-up clarification must defer to current actor-scoped homelab entity resolution"
# Domain history can carry entities and conversational scope, but deterministic
# recipe reads must receive the current operation. Otherwise a prior "list my
# recipes" turn can override a later ingredients or stock question.
recipe_reads = [
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_grocy_recipe_read"
]
assert len(recipe_reads) == 2, len(recipe_reads)
assert all(
    node.args
    and isinstance(node.args[0], ast.Name)
    and node.args[0].id == "current_text"
    for node in recipe_reads
), "direct recipe reads must use the current turn, not reconstructed history"
stock_matches = [
    node for node in ast.walk(run_conversation)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_grocy_recipe_stock_match"
]
assert len(stock_matches) == 1
assert [ast.unparse(arg) for arg in stock_matches[0].args] == [
    "current_text", "_hades_history",
], "recipe/pantry follow-ups must resolve history before the generic pantry read"
wanted = {
    "_hades_is_household_inventory_intent",
    "_hades_normalize_kitchen_typo",
    "_hades_grocy_read_operation",
    "_hades_direct_grocy_named_recipe_read",
    "_hades_direct_grocy_recipe_instructions",
    "_hades_direct_grocy_recipe_stock_match",
    "_hades_grocy_recipe_stock_followup",
    "_hades_grocy_recent_recipe_prompt",
    "_hades_grocy_match_saved_recipe",
    "_hades_grocy_read_tool_choice",
    "_hades_grocy_ingredient_followup",
    "_hades_grocy_read_operation_for_turn",
    "_hades_finance_followup_query",
    "_hades_direct_finance_guidance",
    "_hades_direct_grocy_recipe_read",
    "_hades_direct_homelab_read",
    "_hades_homelab_inventory_intent",
    "_hades_homelab_owner_health_response",
    "_hades_homelab_read_followup_query",
    "_hades_homelab_network_diagnostic_intent",
    "_hades_homelab_node_status_targets",
    "_hades_configured_homelab_alias_matches",
    "_hades_broad_homelab_status_intent",
    "_hades_is_provisioning_request",
    "_hades_is_managed_server_status_request",
    "_hades_endpoint_intent_before_provision",
    "_hades_nonpersonal_state_turn",
    "_hades_contextual_followup_clarification",
}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
assert {node.name for node in functions} == wanted
scope = {
    "re": re,
    "os": os,
    "Path": Path,
    "json": json,
    "urllib": urllib,
    "_HADES_KITCHEN_TYPO": re.compile(r"\b(?:kiytchen|kichen|kitcen)\b", re.I),
    "_HADES_HOUSEHOLD_INVENTORY_CONTEXT": re.compile(
        r"\b(?:what(?:['’]s| is|s)\s+in|what\s+do\s+(?:i|we)\s+have|"
        r"what\s+(?:ingredients?|food|groceries)\s+do\s+(?:i|we)\s+have)\b", re.I
    ),
    "_HADES_SHARED_MEMORY_INTENT": re.compile(
        r"\b(?:kitchen|pantry|grocy|recipe|food|inventory|stock)\b", re.I
    ),
    "_HADES_NONPERSONAL_STATE_INTENT": re.compile(r"\b(?:kitchen|pantry)\b", re.I),
    "_HADES_PROVISIONING_ACTION": re.compile(
        r"\b(?:spin\s+(?:(?:one|it|a|the)\s+)?up|provision|deploy|create|make|host)\b", re.I
    ),
    "_HADES_PROVISIONING_TARGET": re.compile(
        r"\b(?:server|palworld|minecraft|factorio|proxmox|vm|virtual\s+machine|sandbox|workload|website|linux\s+box)\b", re.I
    ),
    "_HADES_GROCY_ACTION_INTENT": re.compile(
        r"\b(?:add|remove|consume|create|update|delete|change)\b", re.I
    ),
    "_HADES_MEAL_RECOMMENDATION_INTENT": re.compile(
        r"\b(?:what|which)\s+(?:can|could)\s+(?:i|we)\s+(?:make|cook)\b", re.I
    ),
    "_hades_is_homelab_intent": lambda text: bool(re.search(r"homelab|network|nodes?|thanatos", text, re.I)),
    "_HADES_EXPLICIT_PUBLIC_RESEARCH_INTENT": re.compile(r"(?!)"),
    "_HADES_LIVE_WEB_INTENT": re.compile(r"(?!)"),
    "_hades_configured_homelab_records": lambda: [
        {"name": "Thanatos", "aliases": ["thanatos"]},
        {"name": "Hermes", "aliases": ["hermes"]},
    ],
    "_hades_service_health_target": lambda _text: False,
    "_hades_homelab_conflict_intent": lambda _text: False,
    "_hades_homelab_guest_visibility_intent": lambda _text: False,
    "_hades_homelab_service_placement_intent": lambda _text: False,
    "_hades_homelab_resource_ranking_intent": lambda _text: False,
    "_hades_broad_homelab_status_intent": lambda text: bool(
        re.search(r"how(?:['’]s|s|\s+is)\s+(?:my\s+)?network", text, re.I)
    ),
    "_HADES_GROCY_ITEM_FRAGMENT": re.compile(r"\b(?:eggs?|milk)\b", re.I),
    "_hades_is_meal_budget_intent": lambda _text: False,
    "_hades_grocy_base_url": lambda: "http://grocy.synthetic",
    "_hades_grocy_api_key": lambda: "synthetic-key",
    "_hades_logger": type("Logger", (), {
        "info": lambda *_a, **_k: None,
        "warning": lambda *_a, **_k: None,
    })(),
    "_hades_homelab_health_summary_response": lambda _summary: "synthetic health caveats",
    "_hades_direct_homelab_reachability_response": lambda *_args: None,
}
exec(compile(ast.Module(body=functions, type_ignores=[]), "sitecustomize.py", "exec"), scope)

owner_health = scope["_hades_homelab_owner_health_response"]({
    "online_names": ["Synthetic Core", "  Synthetic Worker  "],
})
assert owner_health == (
    "Live Proxmox currently reports: Synthetic Core, Synthetic Worker. synthetic health caveats"
), owner_health
assert scope["_hades_homelab_owner_health_response"]({}) == "synthetic health caveats"

operation = scope["_hades_grocy_read_operation"]
choice = scope["_hades_grocy_read_tool_choice"]
tools = [
    {"function": {"name": "mcp_grocy_recipes_list_tool"}},
    {"function": {"name": "mcp_grocy_recipe_details_tool"}},
    {"function": {"name": "mcp_grocy_stock_overview_tool"}},
]
assert operation("list my recipes") == "recipes_list_tool"
assert operation("what ingredients are in Chicken Cordon Bleu?") == "recipe_details_tool"
assert operation("what recipes dfo i have?") == "recipes_list_tool"
assert operation("tell me about the best cordon bleu recipe") == "recipe_details_tool"
saved_reader = scope["_hades_direct_grocy_recipe_read"]
saved_instruction_reader = scope["_hades_direct_grocy_recipe_instructions"]
named_read = scope["_hades_direct_grocy_named_recipe_read"]
named_calls = []
instruction_calls = []
def synthetic_named_recipe_reader(text):
    named_calls.append(text)
    if text == "list my recipes":
        return "Saved Grocy recipes: Family: Chicken Cordon Bleu — makeable with current stock; Recipe B — missing: rice. I only checked canonical recipes and stock."
    if text == "what ingredients are in Family: Chicken Cordon Bleu?":
        return "Grocy lists these ingredients for Family: Chicken Cordon Bleu: Synthetic Chicken (2 pieces). Nothing was changed."
    return None
def synthetic_named_recipe_instructions(text):
    instruction_calls.append(text)
    return "Grocy's stored instructions for Family: Chicken Cordon Bleu: Synthetic preparation notes."
scope["_hades_direct_grocy_recipe_read"] = synthetic_named_recipe_reader
scope["_hades_direct_grocy_recipe_instructions"] = synthetic_named_recipe_instructions
named_details = named_read("tell me about the best cordon bleu recipe")
assert named_details and "Grocy's stored instructions for Family: Chicken Cordon Bleu" in named_details
assert "Grocy lists these ingredients for Family: Chicken Cordon Bleu" in named_details
assert "Synthetic preparation notes" in named_details and "Synthetic Chicken (2 pieces)" in named_details
assert named_calls == [
    "list my recipes",
    "what ingredients are in Family: Chicken Cordon Bleu?",
]
assert instruction_calls == ["how do i make Family: Chicken Cordon Bleu recipe?"]
# If Grocy has no preparation text, the detail operation must still be honest
# and return canonical ingredients rather than substituting model knowledge.
scope["_hades_direct_grocy_recipe_instructions"] = lambda _text: (
    "Grocy has no preparation instructions stored for Family: Chicken Cordon Bleu. "
    "Grocy lists these ingredients for Family: Chicken Cordon Bleu: Synthetic Chicken (2 pieces)."
)
missing_steps = named_read("tell me about the best cordon bleu recipe")
assert missing_steps and "no preparation instructions stored" in missing_steps
assert "Synthetic Chicken (2 pieces)" in missing_steps
scope["_hades_direct_grocy_recipe_instructions"] = synthetic_named_recipe_instructions
scope["_hades_direct_grocy_recipe_read"] = lambda _text: (
    "Saved Grocy recipes: Chicken Cordon Bleu Classic — makeable; "
    "Chicken Cordon Bleu Special — missing. I only checked canonical recipes and stock."
)
ambiguous_details = named_read("tell me about the best cordon bleu recipe")
assert ambiguous_details and "multiple saved recipes" in ambiguous_details and "Which one" in ambiguous_details
scope["_hades_direct_grocy_recipe_instructions"] = saved_instruction_reader
scope["_hades_direct_grocy_recipe_read"] = saved_reader
assert named_read("what ingredients do i have in my kiytchen?") is None
real_urlopen = urllib.request.urlopen
def forbidden_grocy_request(*_args, **_kwargs):
    raise AssertionError("a recipe list/detail operation must not fall through to feasibility fetch")
urllib.request.urlopen = forbidden_grocy_request
try:
    assert scope["_hades_direct_grocy_recipe_read"]("tell me about the best cordon bleu recipe") is None
finally:
    urllib.request.urlopen = real_urlopen
assert operation("what's in my kitchen?") == "stock_overview_tool"
assert operation("what’s in the kitchen") == "stock_overview_tool"
assert operation("whats in my kiytchen?") == "stock_overview_tool"
assert operation("add milk to the shopping list") is None
assert choice("list my recipes", tools) == {
    "type": "function", "function": {"name": "mcp_grocy_recipes_list_tool"}
}
assert choice("what ingredients are in Chicken Cordon Bleu?", tools) == {
    "type": "function", "function": {"name": "mcp_grocy_recipe_details_tool"}
}
assert choice("what ingredients are in Chicken Cordon Bleu?", tools[:1]) is None
assert choice("what recipes dfo i have?", tools) == {
    "type": "function", "function": {"name": "mcp_grocy_recipes_list_tool"}
}
assert choice("tell me about the best cordon bleu recipe", tools) == {
    "type": "function", "function": {"name": "mcp_grocy_recipe_details_tool"}
}
assert operation("what's in my kitchen?") == "stock_overview_tool"
assert operation("what recipes dfo i have?") == "recipes_list_tool"
assert operation("tell me about the best cordon bleu recipe") == "recipe_details_tool"
recipe_history = [
    {"role": "user", "content": "what recipes dfo i have?"},
    {"role": "assistant", "content": "Synthetic recipes listed."},
    {"role": "user", "content": "tell me about the best cordon bleu recipe"},
    {"role": "assistant", "content": "Synthetic recipe details."},
]
assert scope["_hades_grocy_ingredient_followup"](
    "what ingredients does it need?", recipe_history
)
assert scope["_hades_grocy_recipe_stock_followup"](
    "What ingredients do I have for it?", recipe_history
) == "tell me about the best cordon bleu recipe"
assert not scope["_hades_grocy_ingredient_followup"](
    "what ingredients does it need?", []
)
assert scope["_hades_grocy_recipe_stock_followup"](
    "What ingredients do I have for it?", []
) is None
assert scope["_hades_grocy_read_operation_for_turn"](
    "what ingredients does it need?", tools, recipe_history
) == {"type": "function", "function": {"name": "mcp_grocy_recipe_details_tool"}}
assert scope["_hades_grocy_read_operation_for_turn"](
    "What ingredients do I have for it?", tools, recipe_history
) == {"type": "function", "function": {"name": "mcp_grocy_recipe_details_tool"}}
assert scope["_hades_grocy_read_operation_for_turn"](
    "what's in my kitchen?", tools, recipe_history
) == {"type": "function", "function": {"name": "mcp_grocy_stock_overview_tool"}}
assert scope["_hades_is_household_inventory_intent"]("what’s in the kitchen") is True
assert scope["_hades_nonpersonal_state_turn"]("what’s in the kitchen") is True

# Exercise the canonical recipe detail read with three recipes and separate
# stock data. The detail operation must return only that recipe's ingredient
# positions, using GETs, while kitchen inventory wording remains a stock task.
grocy_payloads = {
    "/api/objects/recipes": [
        {"id": 1, "name": "Chicken Cordon Bleu"},
        {"id": 2, "name": "Recipe B"},
        {"id": 3, "name": "Recipe C"},
    ],
    "/api/objects/recipes_pos": [
        {"recipe_id": 1, "product_id": 10, "amount": 2, "qu_id": 1},
        {"recipe_id": 1, "product_id": 11, "amount": 0.5, "qu_id": 2},
        {"recipe_id": 2, "product_id": 12, "amount": 3, "qu_id": 1},
    ],
    "/api/objects/products": [
        {"id": 10, "name": "Synthetic Chicken", "qu_id_stock": 1},
        {"id": 11, "name": "Synthetic Cheese", "qu_id_stock": 2},
        {"id": 12, "name": "Unrelated Product", "qu_id_stock": 1},
    ],
    "/api/stock": [
        {"product_id": 10, "amount_aggregated": 2},
        {"product_id": 11, "amount_aggregated": 1},
    ],
    "/api/objects/quantity_units": [
        {"id": 1, "name": "piece", "name_plural": "pieces"},
        {"id": 2, "name": "kilogram", "name_plural": "kilograms"},
    ],
}
grocy_requests = []

class SyntheticGrocyResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()

def synthetic_recipe_urlopen(request, timeout=5):
    path = request.full_url.removeprefix("http://grocy.synthetic")
    grocy_requests.append((path, request.get_method(), timeout))
    return SyntheticGrocyResponse(grocy_payloads[path])

real_urlopen = urllib.request.urlopen
urllib.request.urlopen = synthetic_recipe_urlopen
try:
    saved_recipes = scope["_hades_direct_grocy_recipe_read"](
        "what recipes dfo i have?"
    )
    assert saved_recipes.startswith("Saved Grocy recipes:"), saved_recipes
    assert "Chicken Cordon Bleu" in saved_recipes
    assert "Recipe B" in saved_recipes
    assert all(method == "GET" for _, method, _ in grocy_requests)
    assert {path for path, _, _ in grocy_requests} == {
        "/api/objects/recipes", "/api/objects/recipes_pos",
        "/api/objects/products", "/api/stock",
    }
    grocy_requests.clear()
    pantry_match = scope["_hades_direct_grocy_recipe_stock_match"](
        "What ingredients do I have for it?", recipe_history,
    )
    assert pantry_match and pantry_match.startswith(
        "For Chicken Cordon Bleu, based on current Grocy stock"
    ), pantry_match
    assert "Synthetic Chicken" in pantry_match and "Synthetic Cheese" in pantry_match
    assert "Nothing was changed" in pantry_match
    assert all(method == "GET" for _, method, _ in grocy_requests)
    grocy_requests.clear()
    saved_recipes = scope["_hades_direct_grocy_recipe_read"]("list my recipes")
    assert saved_recipes.startswith("Saved Grocy recipes:")
    assert "Chicken Cordon Bleu" in saved_recipes
    assert all(method == "GET" for _, method, _ in grocy_requests)
    grocy_requests.clear()
    ingredients = scope["_hades_direct_grocy_recipe_read"](
        "what ingredients are in Chicken Cordon Bleu?"
    )
    assert "Grocy lists these ingredients for Chicken Cordon Bleu" in ingredients
    assert "Synthetic Chicken (2 pieces)" in ingredients
    assert "Synthetic Cheese (0.5 kilograms)" in ingredients
    assert "Unrelated Product" not in ingredients
    assert all(method == "GET" for _, method, _ in grocy_requests)
    assert {path for path, _, _ in grocy_requests} == set(grocy_payloads)
    grocy_payloads["/api/objects/recipes"][0]["name"] = "Family: Chicken Cordon Bleu"
    grocy_requests.clear()
    ingredients = scope["_hades_direct_grocy_recipe_read"](
        "what ingredients are in Chicken Cordon Bleu?"
    )
    assert "Grocy lists these ingredients for Family: Chicken Cordon Bleu" in ingredients
    assert "Synthetic Chicken (2 pieces)" in ingredients
    grocy_payloads["/api/objects/recipes"][1]["name"] = "Chicken Cordon Bleu Special"
    grocy_requests.clear()
    ambiguous = scope["_hades_direct_grocy_recipe_read"](
        "what ingredients are in Chicken Cordon Bleu?"
    )
    assert "couldn't match" in ambiguous
    grocy_requests.clear()
    assert scope["_hades_direct_grocy_recipe_read"](
        "what ingredients do i have in my kiytchen?"
    ) is None
    assert grocy_requests == []
finally:
    urllib.request.urlopen = real_urlopen

homelab_followup = scope["_hades_homelab_read_followup_query"]
homelab_summary_reads = []
scope["_hades_direct_homelab_tool_result"] = lambda operation: (
    homelab_summary_reads.append(operation)
    or {"resources": [{"name": "Thanatos"}, {"name": "Hermes"}]}
)
journey = [
    {"role": "user", "content": "how's my network?"},
    {"role": "assistant", "content": "synthetic answer"},
    {"role": "user", "content": "what about Thanatos and all the nodes?"},
    {"role": "assistant", "content": "synthetic answer"},
    {"role": "user", "content": "are any of the nodes showing any problems?"},
]
assert "network health status" in homelab_followup("how's my network?", "owner", [])
assert scope["_hades_broad_homelab_status_intent"]("Hows my network")
assert homelab_followup("Hows my network", "owner", []) == "network health status"
diagnostic_prompt = (
    "Something feels slow on the network; check node status, network health, "
    "recent resource usage, and services, then tell me what looks abnormal."
)
assert homelab_followup(diagnostic_prompt, "owner", []) == diagnostic_prompt
named_followup = [
    {"role": "user", "content": "Hows my network"},
    {"role": "assistant", "content": "synthetic health summary"},
]
assert homelab_followup("what about thanatos?", "owner", named_followup) == "What is Thanatos doing right now?"
assert homelab_followup("what about thanatos or hermes?", "owner", named_followup) == "homelab node status for thanatos and hermes"
contextual_followup = scope["_hades_contextual_followup_clarification"]
same_chat_node_pair = [
    *named_followup,
    {"role": "user", "content": "what about thanatos or hermes?"},
]
assert contextual_followup(
    "what about thanatos or hermes?", "Hows my network",
    same_chat_node_pair, "owner",
) is None, "a resolvable owner homelab follow-up must reach canonical entity resolution"
assert contextual_followup(
    "what about it?", "Hows my network",
    [*named_followup, {"role": "user", "content": "what about it?"}], "owner",
) == "Which server or node do you mean? Name the one you want me to check; I haven't changed anything."
assert contextual_followup(
    "what about thanatos or hermes?", "Hows my network",
    same_chat_node_pair, "household",
) == "Which server or node do you mean? Name the one you want me to check; I haven't changed anything."
configured_alias_match = scope["_hades_configured_homelab_alias_matches"]
homelab_classifier = scope["_hades_is_homelab_intent"]
scope["_hades_configured_homelab_alias_matches"] = lambda _text: []
scope["_hades_is_homelab_intent"] = lambda text: bool(
    re.search(r"homelab|network|nodes?", text, re.I)
    and not re.search(r"\bneural networks?\b", text, re.I)
)
try:
    # Real production composition may not have every conversational node name
    # in its small alias file. A same-chat disjunction still needs a fresh
    # canonical homelab read instead of model-only mythology fallback.
    assert homelab_followup("what about Thanatos or Hermes?", "owner", named_followup) == "homelab node status for Thanatos and Hermes"
    homelab_summary_reads.clear()
    assert homelab_followup("what about Thanatos or Hermes?", "owner", []) == "homelab node status for Thanatos and Hermes"
    assert homelab_summary_reads == ["homelab_summary"]
    homelab_summary_reads.clear()
    assert homelab_followup("what about Zeus or Apollo?", "owner", []) == "what about Zeus or Apollo?"
    assert homelab_summary_reads == ["homelab_summary"]
    chained_followup = named_followup + [
        {"role": "assistant", "content": "synthetic node summary"},
        {"role": "user", "content": "what about Thanatos or Hermes?"},
        {"role": "assistant", "content": "synthetic node summary"},
    ]
    assert homelab_followup("are any of the nodes showing problems?", "owner", chained_followup) == "homelab nodes problems status"
    assert homelab_followup("are any of the nodes showing problems?", "owner", []) == "homelab nodes problems status"
    unrelated_turn = named_followup + [
        {"role": "assistant", "content": "synthetic answer"},
        {"role": "user", "content": "explain neural networks"},
    ]
    assert homelab_followup("what about Zeus or Apollo?", "owner", unrelated_turn) == "what about Zeus or Apollo?"
finally:
    scope["_hades_configured_homelab_alias_matches"] = configured_alias_match
    scope["_hades_is_homelab_intent"] = homelab_classifier
assert "all nodes status" in homelab_followup(journey[-3]["content"], "owner", journey[:4])
assert "nodes problems status" in homelab_followup(journey[-1]["content"], "owner", journey)
assert homelab_followup("are any of the nodes showing any problems?", "household", journey) == journey[-1]["content"]
assert scope["_hades_homelab_node_status_targets"](
    "homelab node status for Thanatos and Hermes"
) == ["Thanatos", "Hermes"]
assert scope["_hades_homelab_node_status_targets"]("homelab all nodes status") == []

palworld_request = "I think i wanna build a game server for palworld, can you spin one up for me?"
assert scope["_hades_is_provisioning_request"](palworld_request)
assert not scope["_hades_endpoint_intent_before_provision"](palworld_request)
assert not scope["_hades_is_managed_server_status_request"](
    palworld_request + " Do not provision it yet; tell me what specific approval, decision, or capability is needed first."
), "a provisioning request must not be intercepted as existing-server status"
assert scope["_hades_is_managed_server_status_request"]("What is my HADES-managed server status?")
assert scope["_hades_direct_homelab_read"](
    palworld_request, subject="synthetic-owner", scope="owner"
) is None, "a provisioning action must not be intercepted as a homelab status read"

today = date.today()
coverage = today - timedelta(days=31)
rows = [
    (date(today.year, 1, 12), "7 Brew", -10.00, "Posted"),
    (date(today.year, 2, 4), "7BREW Coffee", -12.50, "Cleared"),
    (date(today.year, 2, 8), "7 Brew refund", 2.00, "Posted"),
    (date(today.year, 3, 1), "Synthetic Grocery", -44.00, "Posted"),
    (coverage, "7 Brew", -3.00, "Pending"),
    (date(today.year - 1, 12, 20), "7 Brew", -100.00, "Posted"),
    (date(today.year - 1, today.month, today.day) - timedelta(days=1), "7 Brew", -500.00, "Posted"),
]
with tempfile.TemporaryDirectory(prefix="hades-multidomain-finance-") as temp:
    path = Path(temp) / "transactions.csv"
    path.write_text(
        "Date,Description,Amount,Category,Status\n" + "".join(
            f"{when.isoformat()},{description},{amount},Coffee,{status}\n"
            for when, description, amount, status in rows
        ), encoding="utf-8",
    )
    old = os.environ.get("HADES_FINANCE_CSV_PATH")
    os.environ["HADES_FINANCE_CSV_PATH"] = str(path)
    try:
        finance = scope["_hades_direct_finance_guidance"]
        first = finance("How much have I spent at 7 Brew year-to-date?")
        assert "posted net spending at 7 Brew is $20.50" in first, first
        assert "Pending transactions total $3.00" in first and "not a complete year-to-date total" in first, first
        followup = scope["_hades_finance_followup_query"](
            "But I need to know", [
                {"role": "user", "content": "How much have I spent at 7 Brew year-to-date?"},
                {"role": "assistant", "content": "CSV coverage metadata"},
                {"role": "user", "content": "But I need to know"},
            ], "owner",
        )
        assert "7 Brew" in followup and "year-to-date" in followup
        second = finance(followup)
        assert "posted net spending at 7 Brew is $20.50" in second, second
        assert "100.00" not in second
        trailing_year = finance("how much did I spend on 7 brew in the last year?")
        assert "posted net spending at 7 brew is $120.50" in trailing_year, trailing_year
        assert "Pending transactions total $3.00" in trailing_year, trailing_year
        assert "not a complete-period total" in trailing_year, trailing_year
        assert "$500.00" not in trailing_year, trailing_year
        explicit_followup = scope["_hades_finance_followup_query"](
            "Calculate how much I spent there", [
                {"role": "user", "content": "How much did I spend on 7 Brew in the last year?"},
                {"role": "assistant", "content": trailing_year},
                {"role": "user", "content": "But I need to know"},
                {"role": "assistant", "content": "I'm here to help—what do you need to know?"},
                {"role": "user", "content": "Calculate how much I spent there"},
            ], "owner",
        )
        assert "7 Brew" in explicit_followup and "last year" in explicit_followup
        third = finance(explicit_followup)
        assert "posted net spending at 7 Brew is $120.50" in third, third
        assert "Pending transactions total $3.00" in third, third
        assert "$500.00" not in third
        original_homelab_intent = scope["_hades_is_homelab_intent"]
        def missing_overlay_alias_helper(_text):
            raise NameError("_hades_configured_homelab_alias_match")
        scope["_hades_is_homelab_intent"] = missing_overlay_alias_helper
        try:
            same_chat_query = scope["_hades_finance_followup_query"](
                "Calculate how much I spent there", [
                    {"role": "user", "content": "How much have I spent at 7 Brew year-to-date?"},
                    {"role": "assistant", "content": first},
                    {"role": "user", "content": "But I need to know"},
                    {"role": "assistant", "content": second},
                    {"role": "user", "content": "Calculate how much I spent there"},
                ], "owner",
            )
            assert "7 Brew" in same_chat_query and "year-to-date" in same_chat_query
            recovered = finance(same_chat_query)
            assert "posted net spending at 7 Brew is $20.50" in recovered, recovered
        finally:
            scope["_hades_is_homelab_intent"] = original_homelab_intent
    finally:
        if old is None:
            os.environ.pop("HADES_FINANCE_CSV_PATH", None)
        else:
            os.environ["HADES_FINANCE_CSV_PATH"] = old

print("PASS synthetic Grocy operation selection, homelab continuity, and finance aggregation")
