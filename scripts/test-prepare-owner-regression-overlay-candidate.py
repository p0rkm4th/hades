#!/usr/bin/env python3
"""Exercise bounded composition against a synthetic deployment-local overlay."""
from __future__ import annotations

import importlib.util
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "owner_overlay_composer", ROOT / "scripts/prepare-owner-regression-overlay-candidate.py"
)
assert SPEC and SPEC.loader
composer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(composer)
source = (ROOT / "hermes/sitecustomize.py").read_text(encoding="utf-8")

active = r'''import re

_HADES_SHARED_MEMORY_INTENT = re.compile(r"\b(?:pantry)\b", re.I)
_HADES_HOUSEHOLD_INVENTORY_CONTEXT = re.compile(r"\bwhat's in\b", re.I)
_HADES_NONPERSONAL_STATE_INTENT = re.compile(r"\b(?:homelab)\b", re.I)

def _hades_direct_grocy_recipe_read(user_text):
    text = str(user_text or "")
    return "legacy recipe response"

def _hades_grocy_read_operation(user_text):
    return None

def _hades_broad_homelab_status_intent(text):
    return False

def _hades_homelab_read_followup_query(user_message, scope, conversation_history):
    return user_message

def _hades_grocy_read_tool_choice(user_text, tools):
    return None

def _hades_configured_homelab_alias_match(user_text):
    return None

def _hades_homelab_proxmox_node_load_target(text):
    return None

def _hades_homelab_proxmox_node_load_response(summary, target):
    return "node status"

def _hades_homelab_health_summary_response(summary):
    return "full health summary"

def _hades_homelab_availability_groups(rows):
    return {"down": [], "unknown": []}

def _hades_backup_restore_guest_state_intent(text):
    return False

def _hades_direct_homelab_read(user_text, subject="", scope="", context_text="", conversation_history=None):
    text = str(user_text or "")
    if _hades_backup_restore_guest_state_intent(text):
        return None

def _hades_p1_finance_merchant_calculation(user_text):
    def money(value):
        return str(value)
    if True:
        if True:
            if True:
                ytd_request = bool(re.search(r"ytd", user_text, re.I))
    return None

def _hades_direct_finance_guidance(user_text):
    return "existing"

_hades_p1_existing_finance_guidance = _hades_direct_finance_guidance
def _hades_direct_finance_guidance(user_text):
    ytd_merchant = bool(
        re.search(r"\b(?:year[ -]to[ -]date|ytd|this\s+year|since\s+january)\b", text, re.IGNORECASE)
        and re.search(r"\b(?:at|with|from)\s+\w", text, re.IGNORECASE)
    )
    if ytd_merchant:
        calculated = _hades_p1_finance_merchant_calculation(text)
        if calculated:
            return calculated
    return _hades_p1_existing_finance_guidance(user_text)

def _hades_run_conversation(user_text):
    current_grocy_intent = bool(re.search(r"shopping list|recipe|pantry", user_text))
    recipe_turn = True
    web_intent = True
    recipe_web_compound = bool(
        recipe_turn
        and web_intent
    )
    _read_choice = _hades_grocy_read_tool_choice(current_text, grocy_tools)
    grocy_read_only_turn = bool(re.search(r"\b(?:recipes?|ingredients?|make|cook|fulfill|missing)\\b", user_text))
    _server_status_turn = bool(re.search(r"server status", user_text))
    _early_provisioning_request = False
    if _early_provisioning_request:
        _pending_template = "minecraft"
    actions = (r"spin\s+up", r"spin\s+up", r"spin\s+up")
    return grocy_read_only_turn, actions, _server_status_turn

LIVE_ONLY_SENTINEL = "must remain byte-for-byte"
'''

candidate = composer.compose(active.encode(), source.encode()).decode()
assert compile(candidate, "candidate-overlay.py", "exec")
assert "LIVE_ONLY_SENTINEL = \"must remain byte-for-byte\"" in candidate
assert r"what(?:['’]s| is|s)\s+in" in candidate
assert "_hades_configured_homelab_alias_matches" in candidate
assert r"(?:at|on|with|from)\s+\w" in candidate
assert r"spin\s+(?:(?:one|it|a|the)\s+)?up" in candidate
assert r"missing)\b" in candidate
assert r"missing)\\b" not in candidate
assert "_hades_grocy_read_operation_for_turn(current_text, grocy_tools, _hades_history)" in candidate
assert "and _hades_grocy_read_operation(current_text) is None" in candidate
assert "node_status_targets = _hades_homelab_node_status_targets(text)" in candidate
assert "_hades_homelab_node_problems_response(summary)" in candidate
assert "_hades_homelab_named_resource_status(summary, target)" in candidate
assert "Current host evidence:" not in candidate
assert 'current_read_operation == "recipe_details_tool"' in candidate
assert "current_grocy_intent" in candidate
assert "def _hades_is_managed_server_status_request(user_text):" in candidate
assert "_server_status_turn = _hades_is_managed_server_status_request(_server_text)" in candidate
assert "def _hades_finance_followup_query(user_text, conversation_history, scope):" in candidate
assert "Unsupported workload provisioning refused before preparation" in candidate
assert candidate.index("_unsupported_workload = next((name for name in (\"factorio\", \"palworld\")") < candidate.index("_pending_template = \"minecraft\"")

# The deployment-local fulfillment shortcut must yield explicit detail
# operations to Hermes' canonical recipe detail tool. Otherwise a named
# recipe question can be answered with stock/shopping-list data.
candidate_tree = ast.parse(candidate)
detail_reader = next(
    node for node in candidate_tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name == "_hades_direct_grocy_recipe_read"
)
detail_scope = {
    "re": __import__("re"),
    "_hades_grocy_read_operation": lambda _text: "recipe_details_tool",
}
exec(compile(ast.Module(body=[detail_reader], type_ignores=[]), "candidate.py", "exec"), detail_scope)
assert detail_scope["_hades_direct_grocy_recipe_read"](
    "tell me about the best cordon bleu recipe"
) is None

# The candidate has no authority to replace the complete live runtime.
assert candidate.count("LIVE_ONLY_SENTINEL") == 1
assert "def _hades_run_conversation(user_text):" in candidate
recomposed = composer.compose(candidate.encode(), source.encode()).decode()
assert recomposed.count("node_status_targets = _hades_homelab_node_status_targets(text)") == 1
assert recomposed.count("view = _hades_homelab_named_resource_status(summary, target)") == 1
assert recomposed.count("_server_status_turn = _hades_is_managed_server_status_request(_server_text)") == 1
print("PASS owner-regression composition is bounded, reproducible, and preserves live-only content")
