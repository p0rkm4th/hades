#!/usr/bin/env bash
set -eu

# Regression check for natural-language memory questions that must not be
# routed to a live household system. This deliberately checks the deployed
# overlay source without importing Hermes' runtime dependencies.
python - <<'PY'
from pathlib import Path

source = Path('hermes/sitecustomize.py').read_text()
required = (
    'did i tell',
    'do you remember',
    'hindsight_recall',
    '_hades_original_sync_turn',
    '_hades_shared_memory_intent',
    '_hades_nonpersonal_state_intent',
    '_hades_transient_error',
    '_hades_nonpersonal_state_turn',
    '_hades_service_health_target',
    '_hades_should_skip_automatic_memory',
    '_hades_automatic_memory_qualification',
    '_hades_automatic_memory_actor_bound',
    '_hades_sync_qualified_memory_turn',
    'hades_hindsight_auto_retain_subject_ids',
    '_hades_explicit_memory_intent',
    'skipping automatic hindsight retain status=%s reason=%s',
    '_hades_sync_qualified_memory_turn(',
    '_hindsight.hindsightmemoryprovider.sync_turn = _hades_sync_turn',
    'stale personal semantic-memory claims',
    '_hades_grocy_action_intent',
    '_hades_grocy_item_fragment',
    'agent\\s+zero',
    'delegat(?:e|ion|ed)',
    'transaction',
    'web_search',
    'public[_\\s]+research',
    'investigate',
    'osint',
    'endswith',
    'grocry',
    'grocerys',
    'outta',
    'hades_task_notification_feed_v1',
)
missing = [value for value in required if value not in source.lower()]
if missing:
    raise SystemExit(f'missing memory-intent coverage: {missing}')

import importlib.util
import logging
import os
logging.disable(logging.CRITICAL)
spec = importlib.util.spec_from_file_location('hades_overlay_memory_policy', 'hermes/sitecustomize.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)
for error in ('OUTCOME UNKNOWN', 'request timed out', 'service unavailable',
              'invalid JSON response', 'connection failed'):
    if not overlay._hades_transient_error_text(error):
        raise SystemExit(f'transient error was not suppressed: {error}')
for ordinary in ('I prefer basil', 'I hate mushrooms', 'remember my preference'):
    if overlay._hades_transient_error_text(ordinary):
        raise SystemExit(f'ordinary personal text was misclassified: {ordinary}')
for live_state in (
    'Grocy says there are 2 cartons of milk',
    'the shared shopping list contains onions',
    'the weather result says rain',
    'the web search returned a recipe',
    'the finance balance is $65',
    'Agent Zero returned execution output',
    'Proxmox says VM X is running on Node B',
    'NetBox lists the server at 198.51.100.5',
    'Uptime Kuma reports the service is offline',
    'the living-room light is on',
    'Home Assistant says the air purifier is unavailable',
    'HADES_TASK_NOTIFICATION_FEED_V1',
    'Research the public launch date of Synthetic Product.',
    'Investigate public claims about Synthetic Organization.',
    'Use public_research for Synthetic Event.',
    'Run an OSINT lookup for Synthetic Corporation.',
):
    if not overlay._hades_nonpersonal_state_turn(live_state):
        raise SystemExit(f'live/shared state was eligible for private memory: {live_state}')
for personal in ('I prefer basil', 'I hate mushrooms', 'my favorite dinner is pasta'):
    if overlay._hades_nonpersonal_state_turn(personal):
        raise SystemExit(f'personal fact was suppressed as live state: {personal}')

# Exercise the dependency-free qualification used by the runtime wrapper.
# Assistant/tool output is never the retained source; transient failure still
# suppresses the current turn.
for fact in (
    "I prefer concise technical answers.",
    "My cat's name is Lyxa.",
    "I'm moving in December.",
    "For HADES, use composition before custom code.",
    "I usually want the shortest useful answer first.",
    "I'm working toward a remote AI role.",
    "My main project is called HADES.",
):
    decision = overlay._hades_automatic_memory_qualification(fact)
    assert decision["status"] == "QUALIFIED", (fact, decision)
assert overlay._hades_should_skip_automatic_memory("I prefer basil", "The web result says rain.") is False
assert overlay._hades_should_skip_automatic_memory("Grocy says there are 2 cartons of milk", "Current stock: 2 cartons.") is True
assert overlay._hades_should_skip_automatic_memory("I prefer basil", "The service is unavailable.") is True
assert overlay._hades_should_skip_automatic_memory("HADES_TASK_NOTIFICATION_FEED_V1", '{"version":1,"tasks":[]}') is True
assert overlay._hades_nonpersonal_state_turn("Is Minecraft healthy enough for tonight?") is True
assert overlay._hades_should_skip_automatic_memory("Is Minecraft healthy enough for tonight?", "Uptime Kuma's configured check is up.") is True
assert overlay._hades_should_skip_automatic_memory("Are all the computers okay?", "The live status is synthetic-core-node only.") is True
assert overlay._hades_should_skip_automatic_memory("Why does the network feel slow?", "No current network telemetry is available.") is True
for public_research_turn in (
    'Research the public launch date of Synthetic Product.',
    'Investigate public claims about Synthetic Organization.',
    'Use public_research for Synthetic Event.',
    'Run an OSINT lookup for Synthetic Corporation.',
):
    assert overlay._hades_should_skip_automatic_memory(public_research_turn, 'Synthetic public-source result.') is True

for inventory in (
    "what's in my kitchen?",
    'what ingredients do i have?',
    'what ingredients do i have in my kiytchen?',
    'whats in the kichen?',
    "what's in my pantry?",
    'what food do we have?',
    'what can i cook with what we have?',
):
    assert overlay._hades_is_household_inventory_intent(inventory), inventory
for ordinary in (
    'how does a refrigerator cool food?',
    'what does kitchen mean in restaurant terminology?',
    'what should i cook for dinner?',
    'do we have a plan?',
    'what do we have to do about the router?',
    "what's in the database?",
):
    assert not overlay._hades_is_household_inventory_intent(ordinary), ordinary
for network in (
    "what's in my network?",
    'what devices are in my network?',
    "what's running at home?",
    "what's on the homelab?",
    'what servers do i have?',
):
    assert overlay._hades_is_homelab_intent(network), network
for ordinary in (
    'what is a neural network?',
    'explain TCP networking',
    'how does a social network grow?',
    "what's a network effect?",
):
    assert not overlay._hades_is_homelab_intent(ordinary), ordinary

read_prompts = (
    "what's in my kitchen?", 'what ingredients do i have?', 'what food do we have?',
    "what's in my pantry?", "what's in my network?", "what's running in my homelab?",
    "did you forget what's in my pantry?", "why don't you remember my network setup?",
    'what did i tell you about my kitchen?',
)
for prompt in read_prompts:
    assert overlay._hades_explicit_memory_mutation_intent(prompt) is None, prompt
    assert overlay._hades_should_skip_automatic_memory(prompt, 'synthetic answer'), prompt

for text in (
    "My password is synthetic-pass-123.",
    "The API key: synthetic-key-123",
    "My recovery code is synthetic-recovery-123.",
    "The bearer token is synthetic-token-123.",
    "My SSH key is synthetic-private-key-material.",
    "-----BEGIN PRIVATE KEY----- synthetic fixture -----END PRIVATE KEY-----",
    "The test output says my favorite fruit is mango.",
    "The assistant said I prefer dark mode.",
    "I prefer concise answers, and here is a pasted log:\nline one\nline two\nline three\nline four",
    "Did you forget what's in my pantry?",
    "I can't remember my server name.",
    "My pantry currently has 4 eggs.",
    "The server is healthy.",
):
    decision = overlay._hades_automatic_memory_qualification(text)
    assert decision["status"] != "QUALIFIED", (text, decision)
assert overlay._hades_automatic_memory_qualification("remember that I prefer basil.")["status"] == "EXPLICIT_ONLY"
assert overlay._hades_automatic_memory_qualification("I prefer basil", "The service is unavailable.")["status"] == "REJECTED"

from types import SimpleNamespace
previous_allowlist = os.environ.get("HADES_HINDSIGHT_AUTO_RETAIN_SUBJECT_IDS")
os.environ.pop("HADES_HINDSIGHT_AUTO_RETAIN_SUBJECT_IDS", None)
bound = SimpleNamespace(_user_id="synthetic-owner", _write_bank_ids=["hades-user-synthetic-owner"])
assert not overlay._hades_automatic_memory_actor_bound(bound, "conversation-alpha")
os.environ["HADES_HINDSIGHT_AUTO_RETAIN_SUBJECT_IDS"] = "synthetic-owner,synthetic-household"
assert overlay._hades_automatic_memory_actor_bound(bound, "conversation-alpha")
assert not overlay._hades_automatic_memory_actor_bound(
    SimpleNamespace(_user_id="", _write_bank_ids=["hades-owner"]), "conversation-alpha"
)
assert not overlay._hades_automatic_memory_actor_bound(
    SimpleNamespace(_user_id="synthetic-owner", _write_bank_ids=["hades-user-other"]), "conversation-alpha"
)
assert not overlay._hades_automatic_memory_actor_bound(
    SimpleNamespace(_user_id="synthetic-owner", _write_bank_ids=["hades-user-synthetic-owner", "shared"]),
    "conversation-alpha",
)
assert not overlay._hades_automatic_memory_actor_bound(bound, "")
assert not overlay._hades_automatic_memory_actor_bound(
    SimpleNamespace(_user_id="synthetic-other", _write_bank_ids=["hades-user-synthetic-other"]),
    "conversation-alpha",
)

submitted = []
def spy_sync(provider, user_text, assistant_text, *, session_id):
    submitted.append((provider._user_id, user_text, assistant_text, session_id))
    return None

first = overlay._hades_sync_qualified_memory_turn(
    bound,
    "I prefer concise technical answers.",
    "Assistant inferred that I dislike light mode.",
    "conversation-alpha",
    spy_sync,
)
second_provider = SimpleNamespace(
    _user_id="synthetic-household", _write_bank_ids=["hades-user-synthetic-household"]
)
second = overlay._hades_sync_qualified_memory_turn(
    second_provider,
    "My cat's name is Lyxa.",
    "tool output: unrelated",
    "conversation-beta",
    spy_sync,
)
assert first["submitted"] and second["submitted"]
assert submitted == [
    ("synthetic-owner", "I prefer concise technical answers.", "", "conversation-alpha"),
    ("synthetic-household", "My cat's name is Lyxa.", "", "conversation-beta"),
], submitted
before_denied = len(submitted)
denied = overlay._hades_sync_qualified_memory_turn(
    bound, "What's in my kitchen?", "", "conversation-gamma", spy_sync
)
assert denied["status"] == "REJECTED" and not denied["submitted"]
denied_actor = overlay._hades_sync_qualified_memory_turn(
    SimpleNamespace(_user_id="synthetic-owner", _write_bank_ids=["hades-user-other"]),
    "I prefer basil.", "", "conversation-delta", spy_sync
)
assert denied_actor["reason"] == "actor_binding_unavailable", denied_actor
assert len(submitted) == before_denied
if previous_allowlist is None:
    os.environ.pop("HADES_HINDSIGHT_AUTO_RETAIN_SUBJECT_IDS", None)
else:
    os.environ["HADES_HINDSIGHT_AUTO_RETAIN_SUBJECT_IDS"] = previous_allowlist

positive_mutations = (
    ('remember that I keep the spare key in the drawer', [], 'I keep the spare key in the drawer', 'retain'),
    ('save that preference', [{'role': 'user', 'content': 'I prefer basil.'}], 'I prefer basil', 'retain'),
    ('forget what I told you about the old router', [], 'Forget the old router', 'forget'),
    ('remove that memory', [{'role': 'assistant', 'content': 'I remember: the old router was named X.'}], 'Remove the old router was named X', 'forget'),
    ('update your memory: the server is no longer called X', [], 'The server is no longer called X', 'update'),
    ('correct what you remember about Y', [], 'Correct Y with the new confirmed name', 'update'),
)
for prompt, history, content, operation in positive_mutations:
    intent = overlay._hades_explicit_memory_mutation_intent(prompt, history)
    assert intent and intent['operation'] == operation, (prompt, intent)
    assert overlay._hades_should_skip_automatic_memory(prompt, 'synthetic answer', history), prompt
print('PASS memory intent regression')
print('PASS automatic Hindsight qualification retains only bounded durable user claims')
print('PASS automatic Hindsight writes require a server-bound actor bank and conversation')
print('PASS owner routing and read-style prompts cannot authorize memory writes')
print('PASS explicit target-bound memory mutation controls remain authorized')
PY
