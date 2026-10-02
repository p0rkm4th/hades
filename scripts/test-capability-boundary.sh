#!/usr/bin/env bash
set -eu

# Static regression check for privileged capability exposure. Finance must be
# explicitly authorized by a future server-side capability boundary; neither
# API initialization nor natural-language intent may add it.
python - <<'PY'
import logging
from pathlib import Path

logging.disable(logging.CRITICAL)

source = Path('hermes/sitecustomize.py').read_text()
init = source.split('    def _hades_agent_init', 1)[1].split(
    '    _AIAgent.__init__ = _hades_agent_init', 1
)[0]
run = source.split('    def _hades_run_conversation', 1)[1].split(
    '    _AIAgent.run_conversation = _hades_run_conversation', 1
)[0]
finance = 'mcp-actual-finance-readonly'
if finance in init or finance in run:
    raise SystemExit('finance toolset is still reachable from the default API overlay')
if 'finance_intent' in source:
    raise SystemExit('finance intent variable still implies prompt-based authorization')
if 'not household_session' not in source:
    raise SystemExit('household Agent Zero scope guard is missing')
if 'hades-user-' not in source or 'HADES_OWNER_SUBJECT_ID' not in source:
    raise SystemExit('server-selected subject scope is incomplete')
if 'subject = _hades_subject_from_session_key(session_key)' not in source:
    raise SystemExit('scope resolver does not reuse subject validation')
if 'client-selectable owner prefix' not in source or 'return ""' not in source:
    raise SystemExit('untrusted owner scope does not fail closed')
if '"recipe_url_ingest", "recipe-url-ingest"' not in source:
    raise SystemExit('owner-gated recipe tool filtering is missing')
for owner_recipe_tool in (
    '"grocy_recipe_authoring"', '"recipe_create_tool"',
    '"recipe_create_by_name_tool"',
    '"recipe_update_tool"', '"recipe_add_ingredient_tool"',
    '"recipe_remove_ingredient_tool"',
):
    if owner_recipe_tool not in source:
        raise SystemExit(f'owner-gated recipe authoring filter misses {owner_recipe_tool}')
if '_hades_filter_tools_for_scope(\n                    grocy_tools, self._hades_session_scope' not in source:
    raise SystemExit('dynamically materialized Grocy tools bypass authenticated scope filtering')
if 'if grocy_intent and not homelab_intent' not in source:
    raise SystemExit('homelab route can still be overwritten by inventory keywords')
if 'privileged_markers = (' not in source:
    raise SystemExit('household privileged tool filtering is missing')
if 'current_defs = _hades_filter_tools_for_scope(current_defs, "household")' not in source:
    raise SystemExit('deferred Grocy catalog bypasses household capability filtering')
if 'household and any(' not in source or 'recipe_create_tool' not in source:
    raise SystemExit('deferred raw tool_call does not deny generic recipe creation for households')

import os
import hermes.sitecustomize as overlay

os.environ['HADES_OWNER_SUBJECT_ID'] = 'owner-subject-123'
checks = {
    'hades-user-owner-subject-123': 'owner',
    'hades-user-household-456': 'household',
    'hades-user-': '',
    'hades-user-contains space': '',
    'owner-subject-123': '',
    'hades-owner-owner-subject-123': '',
}
for key, expected in checks.items():
    actual = overlay._hades_session_scope(key)
    if actual != expected:
        raise SystemExit(f'session scope mismatch for {key!r}: {actual!r}')
if overlay._hades_subject_from_session_key('hades-user-../owner'):
    raise SystemExit('path-like subject was accepted')
os.environ['HADES_OWNER_SUBJECT_ID'] = ''
if overlay._hades_session_scope('hades-user-owner-subject-123') != 'household':
    raise SystemExit('missing owner mapping granted owner scope')
if overlay._hades_session_scope('hades-user-'):
    raise SystemExit('empty subject gained a default scope')
os.environ['HADES_OWNER_SUBJECT_ID'] = 'owner-subject-123'
tools = [
    {'function': {'name': 'mcp_actual_finance_readonly'}},
    {'function': {'name': 'mcp__receipt_ocr_gateway__receipt_ocr_extract'}},
    {'function': {'name': 'agent_zero_delegate'}},
    {'function': {'name': 'mcp__homelab_control__homelab_provision_guest'}},
    {'function': {'name': 'mcp_homelab_readonly_homelab_summary'}},
    {'function': {'name': 'mcp_homelab_readonly_homelab_owner_snapshot'}},
    {'function': {'name': 'mcp_homelab_readonly_homelab_compute_capabilities'}},
    {'function': {'name': 'mcp_homelab_readonly_homelab_inference_inventory'}},
    {'function': {'name': 'mcp_homelab_readonly_homelab_discovery_scan'}},
    {'function': {'name': 'mcp_homelab_readonly_homelab_discovery_candidates'}},
    {'function': {'name': 'mcp_grocy_stock_overview_tool'}},
    {'function': {'name': 'mcp_recipe_url_ingest_recipe_url_preview'}},
    {'function': {'name': 'mcp_recipe_url_ingest_recipe_url_apply'}},
    {'function': {'name': 'mcp_recipe_url_ingest_recipe_paste_preview'}},
    {'function': {'name': 'mcp_grocy_recipe_create_by_name_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_create_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_update_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_add_ingredient_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_remove_ingredient_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_authoring_recipe_set_servings'}},
    {'function': {'name': 'mcp_grocy_recipe_authoring_recipe_set_servings'}},
    {'function': {'name': 'mcp_grocy_recipes_list_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_details_tool'}},
    {'function': {'name': 'mcp_grocy_recipe_add_to_shopping_tool'}},
]
household_scope = overlay._hades_session_scope('hades-user-household-456')
household_tools = overlay._hades_filter_tools_for_scope(tools, household_scope)
household_names = {item['function']['name'] for item in household_tools}
expected_household = {
    'mcp_grocy_stock_overview_tool', 'mcp_grocy_recipes_list_tool',
    'mcp_grocy_recipe_details_tool', 'mcp_grocy_recipe_add_to_shopping_tool',
}
if household_names != expected_household:
    raise SystemExit(f'channel household scope leaked privileged tools: {household_names}')
owner_scope = overlay._hades_session_scope('hades-user-owner-subject-123')
owner_tools = overlay._hades_filter_tools_for_scope(tools, owner_scope)
owner_names = {item['function']['name'] for item in owner_tools}
if owner_names != {item['function']['name'] for item in tools} - {'mcp_grocy_recipe_authoring_recipe_set_servings'}:
    raise SystemExit('owner scope lost an allowed tool or exposed the raw serving writer')
unauthenticated_tools = overlay._hades_filter_tools_for_scope(tools, '')
if unauthenticated_tools:
    raise SystemExit('unverified session received a Grocy tool')
print('PASS privileged capability boundary regression')
print('PASS household scope strips finance, receipt OCR, homelab control, and Agent Zero')
PY
