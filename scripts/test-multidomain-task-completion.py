#!/usr/bin/env python3
"""Synthetic regressions for per-turn domain task completion."""
from __future__ import annotations

import ast
import os
import re
import tempfile
from datetime import date, timedelta
from pathlib import Path


tree = ast.parse(Path("hermes/sitecustomize.py").read_text(encoding="utf-8"))
wanted = {
    "_hades_is_household_inventory_intent",
    "_hades_normalize_kitchen_typo",
    "_hades_grocy_read_operation",
    "_hades_grocy_read_tool_choice",
    "_hades_finance_followup_query",
    "_hades_direct_finance_guidance",
    "_hades_homelab_read_followup_query",
}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
assert {node.name for node in functions} == wanted
scope = {
    "re": re,
    "os": os,
    "Path": Path,
    "_HADES_KITCHEN_TYPO": re.compile(r"\b(?:kiytchen|kichen|kitcen)\b", re.I),
    "_HADES_HOUSEHOLD_INVENTORY_CONTEXT": re.compile(
        r"\b(?:what(?:'s| is|s)\s+in|what\s+do\s+(?:i|we)\s+have|"
        r"what\s+(?:ingredients?|food|groceries)\s+do\s+(?:i|we)\s+have)\b", re.I
    ),
    "_HADES_GROCY_ACTION_INTENT": re.compile(
        r"\b(?:add|remove|consume|create|update|delete|change)\b", re.I
    ),
    "_hades_is_homelab_intent": lambda text: bool(re.search(r"homelab|network|nodes?|thanatos", text, re.I)),
    "_hades_is_meal_budget_intent": lambda _text: False,
    "_hades_logger": type("Logger", (), {"warning": lambda *_a, **_k: None})(),
}
exec(compile(ast.Module(body=functions, type_ignores=[]), "sitecustomize.py", "exec"), scope)

operation = scope["_hades_grocy_read_operation"]
choice = scope["_hades_grocy_read_tool_choice"]
tools = [
    {"function": {"name": "mcp_grocy_recipes_list_tool"}},
    {"function": {"name": "mcp_grocy_recipe_details_tool"}},
    {"function": {"name": "mcp_grocy_stock_overview_tool"}},
]
assert operation("list my recipes") == "recipes_list_tool"
assert operation("what ingredients are in Chicken Cordon Bleu?") == "recipe_details_tool"
assert operation("what's in my kitchen?") == "stock_overview_tool"
assert operation("whats in my kiytchen?") == "stock_overview_tool"
assert operation("add milk to the shopping list") is None
assert choice("list my recipes", tools) == {
    "type": "function", "function": {"name": "mcp_grocy_recipes_list_tool"}
}
assert choice("what ingredients are in Chicken Cordon Bleu?", tools) == {
    "type": "function", "function": {"name": "mcp_grocy_recipe_details_tool"}
}
assert choice("what ingredients are in Chicken Cordon Bleu?", tools[:1]) is None

homelab_followup = scope["_hades_homelab_read_followup_query"]
journey = [
    {"role": "user", "content": "how's my network?"},
    {"role": "assistant", "content": "synthetic answer"},
    {"role": "user", "content": "what about Thanatos and all the nodes?"},
    {"role": "assistant", "content": "synthetic answer"},
    {"role": "user", "content": "are any of the nodes showing any problems?"},
]
assert "network health status" in homelab_followup("how's my network?", "owner", [])
assert "all nodes status" in homelab_followup(journey[-3]["content"], "owner", journey[:4])
assert "nodes problems status" in homelab_followup(journey[-1]["content"], "owner", journey)
assert homelab_followup("are any of the nodes showing any problems?", "household", journey) == journey[-1]["content"]

today = date.today()
coverage = today - timedelta(days=31)
rows = [
    (date(today.year, 1, 12), "7 Brew", -10.00, "Posted"),
    (date(today.year, 2, 4), "7BREW Coffee", -12.50, "Cleared"),
    (date(today.year, 2, 8), "7 Brew refund", 2.00, "Posted"),
    (date(today.year, 3, 1), "Synthetic Grocery", -44.00, "Posted"),
    (coverage, "7 Brew", -3.00, "Pending"),
    (date(today.year - 1, 12, 20), "7 Brew", -100.00, "Posted"),
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
    finally:
        if old is None:
            os.environ.pop("HADES_FINANCE_CSV_PATH", None)
        else:
            os.environ["HADES_FINANCE_CSV_PATH"] = old

print("PASS synthetic Grocy operation selection, homelab continuity, and finance aggregation")
