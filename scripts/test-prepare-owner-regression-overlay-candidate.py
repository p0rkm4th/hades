#!/usr/bin/env python3
"""Exercise bounded composition against a synthetic deployment-local overlay."""
from __future__ import annotations

import importlib.util
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

def _hades_configured_homelab_alias_match(user_text):
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
    grocy_read_only_turn = bool(re.search(r"\b(?:recipes?|ingredients?|make|cook|fulfill|missing)\\b", user_text))
    actions = (r"spin\s+up", r"spin\s+up", r"spin\s+up")
    return grocy_read_only_turn, actions

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

# The candidate has no authority to replace the complete live runtime.
assert candidate.count("LIVE_ONLY_SENTINEL") == 1
assert "def _hades_run_conversation(user_text):" in candidate
print("PASS owner-regression composition is bounded, reproducible, and preserves live-only content")
