#!/usr/bin/env python3
"""Synthetic contract for direct Hindsight explicit-memory routing."""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = Path(os.environ.get(
    "HADES_HINDSIGHT_OVERLAY_SOURCE", str(ROOT / "hermes/sitecustomize.py")
))
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
FUNCTIONS = {
    node.name: node for node in ast.walk(TREE)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name in {
        "_hades_overlay_non_hermes_interpreter",
        "_hades_is_hermes_auxiliary_prompt",
        "_hades_explicit_memory_recall_requested",
        "_hades_log_memory_recall_scores",
        "_hades_memory_visibility_state",
        "_hades_pending_memory_response",
        "_hades_natural_personal_recall_requested",
        "_hades_automatic_memory_recall_relevant",
        "_hades_ensure_memory_bank",
        "_hades_direct_memory_response",
        "_hades_explicit_memory_bank",
        "_hades_prefetch",
        "_hades_aretain",
        "_hades_aretain_batch",
    }
}
REQUIRED_FUNCTIONS = {
    "_hades_overlay_non_hermes_interpreter",
    "_hades_is_hermes_auxiliary_prompt",
    "_hades_explicit_memory_recall_requested",
    "_hades_log_memory_recall_scores",
    "_hades_memory_visibility_state",
    "_hades_pending_memory_response",
    "_hades_natural_personal_recall_requested",
    "_hades_automatic_memory_recall_relevant",
    "_hades_ensure_memory_bank",
    "_hades_direct_memory_response",
    "_hades_explicit_memory_bank",
    "_hades_prefetch",
    "_hades_aretain",
    "_hades_aretain_batch",
}
if FUNCTIONS.keys() != REQUIRED_FUNCTIONS:
    raise SystemExit(f"missing Hindsight functions: {REQUIRED_FUNCTIONS - FUNCTIONS.keys()}")


class FakeClient:
    instances: list["FakeClient"] = []
    next_recall_rows: list[SimpleNamespace] | None = None
    fail_next_recall = False
    retain_var_async = False
    bank_config_supported = False
    bank_configs: dict[str, dict[str, object]] = {}
    config_updates: list[tuple[str, dict[str, object]]] = []

    def __init__(self, _base_url: str, *, timeout: int):
        self.timeout = timeout
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False
        self.recall_rows = (
            type(self).next_recall_rows
            if type(self).next_recall_rows is not None
            else [SimpleNamespace(text="semantic fallback result")]
        )
        type(self).next_recall_rows = None
        type(self).instances.append(self)

    def recall(self, **kwargs):
        self.calls.append(("recall", kwargs))
        if type(self).fail_next_recall:
            type(self).fail_next_recall = False
            raise TimeoutError("synthetic semantic recall timeout")
        return SimpleNamespace(results=self.recall_rows)

    def retain(self, **kwargs):
        self.calls.append(("retain", kwargs))
        return SimpleNamespace(success=True, var_async=type(self).retain_var_async)

    def get_bank_config(self, bank_id):
        if not type(self).bank_config_supported:
            raise AttributeError("synthetic unsupported bank-config capability")
        if bank_id not in created_banks:
            raise LookupError("synthetic missing bank")
        return type(self).bank_configs.setdefault(bank_id, {
            "config": {
                "retain_extraction_mode": "concise",
                "enable_observations": True,
                "enable_auto_consolidation": True,
            },
            "overrides": {},
        })

    def update_bank_config(self, *, bank_id, **updates):
        type(self).config_updates.append((bank_id, updates))
        config = type(self).bank_configs[bank_id]
        config["overrides"].update(updates)
        config["config"].update(updates)

    def close(self):
        self.closed = True


class FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


score_log = []
state = {"items": []}
requests: list[tuple[str, int]] = []
created_banks: set[str] = set()
list_unavailable = False


def fake_urlopen(url: str, *, timeout: int):
    method = getattr(url, "method", None) or "GET"
    target = getattr(url, "full_url", url)
    requests.append((target if method == "GET" else f"{method} {target}", timeout))
    if list_unavailable and "/memories/list?" in target:
        raise TimeoutError("synthetic list timeout")
    if method == "PUT":
        created_banks.add(target.rsplit("/", 1)[-1])
        return FakeResponse({"id": target.rsplit("/", 1)[-1]})
    if "/banks?" in target:
        rows = [{"id": bank} for bank in sorted(created_banks)]
        return FakeResponse({"items": rows, "limit": 100, "offset": 0, "total": len(rows)})
    return FakeResponse({"items": state["items"], "limit": 100, "offset": 0, "total": len(state["items"])})


namespace = {
    "_HindsightClient": FakeClient,
    "_HADES_EXPLICIT_MEMORY_INTENT": re.compile(
        r"\b(?:remember|memorize|forget|memory|recall|do you remember|"
        r"actually my|correction)\b",
        re.IGNORECASE,
    ),
    "_HADES_EXPLICIT_MEMORY_RECALL": re.compile(
        r"\b(?:what\s+do\s+you\s+remember|what\s+do\s+i\s+remember|"
        r"what\b.{0,100}\bdid\s+i\s+(?:ask\s+you\s+to\s+)?remember|"
        r"what\s+is\s+(?:the|my)\s+.*(?:memory|fact|marker|fruit)|"
        r"recall|look\s+in\s+(?:your|my)\s+memory)\b",
        re.IGNORECASE,
    ),
    "_HADES_NATURAL_PERSONAL_RECALL": re.compile(
        r"\b(?:"
        r"(?:what|where|when|which|who|how)\b.{0,100}\b(?:did\s+i|"
        r"have\s+i|i\s+(?:mentioned|said|told\s+you)|"
        r"do\s+i\s+(?:like|love|prefer|usually|typically))|"
        r"(?:tell|remind|show|find)\s+me\b.{0,100}\bi\s+(?:liked|"
        r"loved|preferred|chose|picked|visited|went\s+to|tried|bought|ordered))\b",
        re.IGNORECASE,
    ),
    "json": json,
    "os": os,
    "re": re,
    "time": __import__("time"),
    "_hades_nonpersonal_state_turn": lambda _text: False,
    "Path": Path,
    "_hades_logger": SimpleNamespace(
        warning=lambda *_args: None,
        info=lambda *args: score_log.append(args),
        debug=lambda *_args: None,
    ),
}
exec(compile(ast.Module(
    body=[
        next(node for node in ast.walk(TREE)
             if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_HADES_HERMES_AUXILIARY_PROMPT" for target in node.targets)),
        next(node for node in ast.walk(TREE)
             if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_HADES_EXPLICIT_MEMORY_BANK_SUFFIX" for target in node.targets)),
        FUNCTIONS["_hades_overlay_non_hermes_interpreter"],
        FUNCTIONS["_hades_is_hermes_auxiliary_prompt"],
        FUNCTIONS["_hades_explicit_memory_recall_requested"],
        next(node for node in ast.walk(TREE)
             if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_HADES_NATURAL_PERSONAL_RECALL" for target in node.targets)),
        FUNCTIONS["_hades_natural_personal_recall_requested"],
        next(node for node in ast.walk(TREE)
             if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_HADES_AUTOMATIC_MEMORY_RELEVANCE" for target in node.targets)),
        FUNCTIONS["_hades_automatic_memory_recall_relevant"],
        FUNCTIONS["_hades_ensure_memory_bank"],
        FUNCTIONS["_hades_log_memory_recall_scores"],
        FUNCTIONS["_hades_memory_visibility_state"],
        FUNCTIONS["_hades_pending_memory_response"],
        FUNCTIONS["_hades_direct_memory_response"],
        FUNCTIONS["_hades_explicit_memory_bank"],
        FUNCTIONS["_hades_prefetch"],
        FUNCTIONS["_hades_aretain"],
        FUNCTIONS["_hades_aretain_batch"],
    ],
    type_ignores=[],
), "sitecustomize.py", "exec"), namespace)

class FakeVisibilityOperations:
    def __init__(self, rows_by_type=None, *, fail=False):
        self.rows_by_type = rows_by_type or {}
        self.fail = fail

    def list_operations(self, **kwargs):
        if self.fail:
            raise TimeoutError("synthetic operation-list timeout")
        return SimpleNamespace(operations=self.rows_by_type.get(kwargs.get("type"), []))


class FakeVisibilityProvider:
    _bank_id = "hades-user-alpha"

    def __init__(self, rows_by_type=None, *, fail=False):
        self.operations = FakeVisibilityOperations(rows_by_type, fail=fail)

    def _run_hindsight_operation(self, operation):
        return operation(SimpleNamespace(operations=self.operations))


visibility_state = namespace["_hades_memory_visibility_state"]
assert visibility_state(FakeVisibilityProvider()) == ("clear", [])
assert visibility_state(FakeVisibilityProvider({
    "retain": [SimpleNamespace(status="processing")],
})) == ("active", ["retain"])
assert visibility_state(FakeVisibilityProvider({
    "consolidation": [SimpleNamespace(status="pending")],
})) == ("active", ["consolidation"])
assert visibility_state(FakeVisibilityProvider(fail=True))[0] == "unknown"
assert visibility_state(FakeVisibilityProvider({
    "retain": [SimpleNamespace(status="completed")] * 100,
}))[0] == "unknown"

pending_response = namespace["_hades_pending_memory_response"]

class FakeMemoryAgent:
    _hades_subject = "alpha"
    _hades_session_scope = "household"

    def __init__(self, provider):
        self._memory_manager = SimpleNamespace(providers=[provider])

active_provider = FakeVisibilityProvider({
    "retain": [SimpleNamespace(status="processing")],
})
active_provider._bank_id = "hades-user-alpha"
active_agent = FakeMemoryAgent(active_provider)
active_text = "Where was I planning to move?"
assert pending_response(active_agent, active_text) == (
    "I'm still saving a recent detail, so I can't confirm it yet. "
    "I can check again shortly."
)
assert pending_response(active_agent, "How do I fix this Python test?") is None
wrong_bank_provider = FakeVisibilityProvider({
    "retain": [SimpleNamespace(status="processing")],
})
wrong_bank_provider._bank_id = "hades-owner"
assert pending_response(FakeMemoryAgent(wrong_bank_provider), active_text) is None
unknown_provider = FakeVisibilityProvider(fail=True)
unknown_provider._bank_id = "hades-user-alpha"
assert pending_response(FakeMemoryAgent(unknown_provider), active_text) is None
unauthenticated = FakeMemoryAgent(active_provider)
unauthenticated._hades_subject = ""
assert pending_response(unauthenticated, active_text) is None

interpreter_check = namespace["_hades_overlay_non_hermes_interpreter"]
assert interpreter_check("/usr/bin/python3", "/opt/hades-hermes/bin/hermes")
assert not interpreter_check("/opt/hades-hermes/bin/python3", "/opt/hades-hermes/bin/hermes")
assert not interpreter_check("/usr/bin/python3", "")
route = namespace["_hades_direct_memory_response"]


async def _capture_retain_kwargs(*args, **kwargs):
    return kwargs


namespace["_hades_original_aretain"] = _capture_retain_kwargs
namespace["_hades_original_aretain_batch"] = _capture_retain_kwargs
async_wrapper = namespace["_hades_aretain"]
async_batch_wrapper = namespace["_hades_aretain_batch"]
import asyncio
for wrapper in (async_wrapper, async_batch_wrapper):
    explicit_sync = asyncio.run(wrapper(object(), retain_async=False))
    default_async = asyncio.run(wrapper(object()))
    assert explicit_sync["retain_async"] is False, explicit_sync
    assert default_async["retain_async"] is True, default_async


class FakeSemanticClient:
    def __init__(self, calls, operation_calls, *, raw_memory=False,
                 operation_status="completed", visibility_operations=None):
        self.calls = calls
        self.operation_calls = operation_calls
        self.raw_memory = raw_memory
        self.operation_status = operation_status
        self.visibility_operations = visibility_operations or {}
        self.operations = self

    def list_operations(self, **kwargs):
        self.operation_calls.append(kwargs)
        if kwargs.get("type"):
            return SimpleNamespace(
                operations=self.visibility_operations.get(kwargs["type"], [])
            )
        if self.raw_memory and kwargs.get("status") == "pending" and len(
            [call for call in self.operation_calls if call.get("status") == "pending" and not call.get("type")]
        ) == 1:
            return SimpleNamespace(
                operations=[SimpleNamespace(task_type="batch_retain")]
            )
        return SimpleNamespace(operations=[])

    def get_operation_status(self, **kwargs):
        self.operation_calls.append(kwargs)
        return SimpleNamespace(status=self.operation_status)

    def arecall(self, **kwargs):
        self.calls.append(kwargs)
        if self.raw_memory and kwargs.get("types") == ["world", "experience"]:
            if "savings target" in str(kwargs.get("query", "")).casefold():
                return SimpleNamespace(
                    results=[SimpleNamespace(text="User's savings target is $3,000.")]
                )
            return SimpleNamespace(results=[SimpleNamespace(text="User moved to Denver in 2024.")])
        return SimpleNamespace(results=[])


class FakePrefetchProvider:
    _memory_mode = "hybrid"
    _auto_recall = True
    _recall_max_input_chars = 0
    _recall_max_tokens = 1200
    _recall_tags = []
    _recall_tags_match = "any"
    _recall_types = ["observation"]
    _recall_prompt_preamble = ""
    _bank_id = "hades-user-alpha"
    _budget = "low"
    _prefetch_waits_for_retain = True
    _prefetch_retain_drain_timeout = 4.0

    def __init__(self, *, raw_memory=False, retain_drain_complete=True,
                 pending_operation_status=None, visibility_operations=None):
        self.semantic_calls = []
        self.operation_calls = []
        self.drain_timeouts = []
        self.raw_memory = raw_memory
        self.retain_drain_complete = retain_drain_complete
        self.pending_operation_status = pending_operation_status
        self.visibility_operations = visibility_operations or {}
        self._pending_retain_ops = (
            {"synthetic-operation"} if pending_operation_status else set()
        )
        self._retain_ops_bank_id = self._bank_id
        self._config = {}

    def _run_hindsight_operation(self, operation):
        return operation(FakeSemanticClient(
            self.semantic_calls, self.operation_calls, raw_memory=self.raw_memory,
            operation_status=self.pending_operation_status or "completed",
            visibility_operations=self.visibility_operations,
        ))

    def _wait_for_retains_drained(self, timeout):
        self.drain_timeouts.append(timeout)
        if not self.retain_drain_complete:
            return False
        for operation_id in list(self._pending_retain_ops):
            if self._is_retain_op_complete(self._retain_ops_bank_id, operation_id):
                self._pending_retain_ops.discard(operation_id)
        return not self._pending_retain_ops

    def _is_retain_op_complete(self, bank_id, operation_id):
        return True


prefetch = namespace["_hades_prefetch"].__get__(
    FakePrefetchProvider(), FakePrefetchProvider
)
prefetch_provider = prefetch.__self__
for prompt in (
    "Remember that my favorite fruit is mango.",
    "What do you remember about the fruit I enjoy?",
    "What answer style did I ask you to remember?",
    "What is my favorite fruit?",
    "What is my favrite frut?",
):
    assert prefetch(prompt) == "", prompt
assert prefetch("### Task:\nGenerate a concise title summarizing the chat history.") == ""
assert prefetch_provider.semantic_calls == [], prefetch_provider.semantic_calls
for personal_statement in (
    "I prefer basil.",
    "I liked the restaurant.",
    "My usual lunch is soup.",
):
    assert not namespace["_hades_automatic_memory_recall_relevant"](personal_statement), personal_statement
for personal_history_question in (
    "What restaurant did I like?",
    "What kind of food do I like?",
    "What did I say about the move?",
    "What was the savings target I mentioned?",
    "Tell me about the restaurant I liked.",
    "We talked about my plans last time.",
):
    assert namespace["_hades_automatic_memory_recall_relevant"](personal_history_question), personal_history_question
for ordinary in (
    "Hi",
    "Why does this Python test fail?",
    "Explain how photosynthesis works.",
    "What is the weather like in Paris?",
):
    assert prefetch(ordinary) == "", ordinary
assert prefetch_provider.semantic_calls == [], prefetch_provider.semantic_calls
assert prefetch("I prefer basil.") == ""
assert prefetch("What restaurant did I like?") == ""
assert prefetch("Tell me about the restaurant I liked") == ""
assert len(prefetch_provider.semantic_calls) == 4, prefetch_provider.semantic_calls
assert prefetch("We talked about my plans last time.") == ""
assert len(prefetch_provider.semantic_calls) == 6, prefetch_provider.semantic_calls
assert prefetch("What was the savings target I mentioned?") == ""
assert len(prefetch_provider.semantic_calls) == 8, prefetch_provider.semantic_calls
assert [row["bank_id"] for row in prefetch_provider.semantic_calls] == [
    "hades-user-alpha", "hades-user-alpha", "hades-user-alpha",
    "hades-user-alpha", "hades-user-alpha", "hades-user-alpha",
    "hades-user-alpha", "hades-user-alpha",
], prefetch_provider.semantic_calls
assert all(
    call.get("bank_id") == "hades-user-alpha"
    for call in prefetch_provider.operation_calls
), prefetch_provider.operation_calls

raw_provider = FakePrefetchProvider(raw_memory=True)
raw_prefetch = namespace["_hades_prefetch"].__get__(
    raw_provider, FakePrefetchProvider
)
raw_memory_context = raw_prefetch("Where did I say I moved?")
assert "Denver" in raw_memory_context, raw_memory_context
assert "# Memory availability" not in raw_memory_context, raw_memory_context
assert "prior conversations" in raw_memory_context, raw_memory_context
assert "even when absent from this chat" in raw_memory_context, raw_memory_context
assert "without mentioning this context unless asked" in raw_memory_context, raw_memory_context
assert [call.get("types") for call in raw_provider.semantic_calls] == [
    ["observation"], ["world", "experience"],
], raw_provider.semantic_calls
assert all(call["bank_id"] == "hades-user-alpha" for call in raw_provider.semantic_calls)
savings_context = raw_prefetch("What was the savings target I mentioned?")
assert "$3,000" in savings_context, savings_context
assert [call.get("types") for call in raw_provider.semantic_calls[-2:]] == [
    ["observation"], ["world", "experience"],
], raw_provider.semantic_calls
assert all(call["bank_id"] == "hades-user-alpha" for call in raw_provider.semantic_calls)
assert raw_provider.operation_calls, "raw fallback must inspect the bank-scoped retain queue"
assert all(
    call.get("bank_id") == "hades-user-alpha"
    and call.get("type") in {"retain", "consolidation"}
    for call in raw_provider.operation_calls
), raw_provider.operation_calls
assert {call.get("type") for call in raw_provider.operation_calls} == {
    "retain", "consolidation"
}, (
    "relevant recall checks both fresh retain and derived-observation work",
    raw_provider.operation_calls,
)

configured_provider = FakePrefetchProvider(raw_memory=True)
configured_provider._config = {"prefer_observations": True}
configured_prefetch = namespace["_hades_prefetch"].__get__(
    configured_provider, FakePrefetchProvider
)
configured_prefetch("Where did I say I moved?")
assert configured_provider.semantic_calls[0].get("prefer_observations") is True

pending_provider = FakePrefetchProvider(visibility_operations={
    "retain": [SimpleNamespace(status="processing")],
})
pending_prefetch = namespace["_hades_prefetch"].__get__(
    pending_provider, FakePrefetchProvider
)
pending_context = pending_prefetch("Where did I say I moved?")
assert "# Personal memory is still processing" in pending_context, pending_context
assert "respond with this concise message" in pending_context, pending_context
assert "Do not mention access to conversation history or memory context" in pending_context, pending_context
assert "Do not imply the user never mentioned it" in pending_context, pending_context
assert pending_provider.semantic_calls == [], pending_provider.semantic_calls

pending_with_partial_provider = FakePrefetchProvider(
    raw_memory=True,
    visibility_operations={"consolidation": [SimpleNamespace(status="pending")]},
)
pending_with_partial_prefetch = namespace["_hades_prefetch"].__get__(
    pending_with_partial_provider, FakePrefetchProvider
)
pending_partial_context = pending_with_partial_prefetch("Where did I say I moved?")
assert "Denver" not in pending_partial_context, pending_partial_context
assert "# Personal memory is still processing" in pending_partial_context, pending_partial_context

failed_retain_provider = FakePrefetchProvider(
    visibility_operations={"retain": [SimpleNamespace(status="failed")]}
)
failed_retain_prefetch = namespace["_hades_prefetch"].__get__(
    failed_retain_provider, FakePrefetchProvider
)
failed_retain_context = failed_retain_prefetch("Where did I say I moved?")
assert "# Memory availability" not in failed_retain_context, failed_retain_context

completed_retain_provider = FakePrefetchProvider(
    raw_memory=True,
)
completed_retain_prefetch = namespace["_hades_prefetch"].__get__(
    completed_retain_provider, FakePrefetchProvider
)
completed_retain_context = completed_retain_prefetch("Where did I say I moved?")
assert "Denver" in completed_retain_context, completed_retain_context
assert "# Memory availability" not in completed_retain_context, completed_retain_context

assert prefetch("We talked about the move last time.") == ""
old_urlopen = urllib.request.urlopen
old_endpoint = os.environ.get("HADES_HINDSIGHT_URL")
urllib.request.urlopen = fake_urlopen
os.environ["HADES_HINDSIGHT_URL"] = "http://hindsight.synthetic:8888"

try:
    # Non-HADES scopes and missing identities never instantiate a Hindsight client.
    before = len(FakeClient.instances)
    assert route("What is my favorite fruit?", "", "household") is None
    assert route("What is my favorite fruit?", "alpha", "unknown") is None
    assert route("What is my shopping list?", "alpha", "household") is None
    assert len(FakeClient.instances) == before

    state["items"] = [
        {
            "tags": ["recipe"],
            "text": "My favorite fruit is pineapple.",
            "entities": [{"text": "My favorite fruit is pineapple", "type": "explicit_fact"}],
            "updated_at": "2026-09-24T12:00:00Z",
        },
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite fruit is mango.",
            "entities": [{"text": "My favorite fruit is mango", "type": "explicit_fact"}],
            "updated_at": "2026-09-24T11:00:00Z",
        },
        {"tags": None, "text": None, "entities": None},
    ]
    answer = route("What is my favorite fruit?", "alpha", "household")
    assert "mango" in answer and "pineapple" not in answer, answer
    implicit_answer = route("What kind of fruit do I like?", "alpha", "household")
    assert "mango" in implicit_answer and "pineapple" not in implicit_answer, implicit_answer
    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: I prefer short answers for quick questions and more detail for research.",
        "updated_at": "2026-10-06T12:00:00Z",
    }]
    FakeClient.next_recall_rows = [
        SimpleNamespace(text="I prefer short answers for quick questions and more detail for research."),
        SimpleNamespace(text="My favorite fruit is pear."),
        SimpleNamespace(text="My savings target is $3,000."),
    ]
    answer = route("What answer style did I ask you to remember?", "alpha", "household")
    assert "short answers" in answer and "research" in answer, answer
    assert "pear" not in answer and "$3,000" not in answer, answer
    assert namespace["_hades_explicit_memory_recall_requested"](
        "What answer style did I ask you to remember?"
    )
    assert not prefetch("What answer style did I ask you to remember?")
    assert requests[-1][0] == (
        "http://hindsight.synthetic:8888/v1/default/banks/"
        "hades-user-alpha/memories/list?tags=hades-explicit-memory&tags_match=any&state=valid&limit=100"
    ), requests[-1]
    assert requests[-1][1] == 2, requests[-1]
    client = FakeClient.instances[-1]
    assert client.calls[0][0] == "recall" and client.calls[0][1]["query"] == (
        "What answer style did I ask you to remember?"
    ), client.calls
    assert client.closed

    # A natural history question with no explicitly retained match must fall
    # through so the provider can enrich it from canonical automatic memory.
    state["items"] = [{"tags": ["personal"], "text": "I moved to Denver in 2024."}]
    assert route("Where did I say I moved?", "alpha", "household") is None
    assert FakeClient.instances[-1].calls == []
    assert FakeClient.instances[-1].closed
    assert route("What was the savings target I mentioned?", "alpha", "household") is None
    assert FakeClient.instances[-1].calls == []
    assert FakeClient.instances[-1].closed

    # Entity arrays are normalized to their text, not Python's repr of dicts.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "A preference was recorded.",
            "entities": [{"text": "My favorite fruit is kiwi", "type": "explicit_fact"}],
            "created_at": "2026-09-24T12:00:00Z",
        }
    ]
    answer = route("What is my favorite fruit?", "alpha", "household")
    assert "My favorite fruit is kiwi" in answer and "{'text'" not in answer, answer

    # A newer correction must not be followed by the contradictory old value.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite fruit is mango.",
            "entities": [{"text": "My favorite fruit is mango", "type": "explicit_fact"}],
            "updated_at": "2026-09-23T12:00:00Z",
        },
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite fruit is pear.",
            "entities": [{"text": "My favorite fruit is pear", "type": "explicit_fact"}],
            "updated_at": "2026-09-24T12:00:00Z",
        },
    ]
    answer = route("What is my favorite fruit?", "alpha", "household")
    assert "pear" in answer and "mango" not in answer, answer

    # A more lexically detailed older version must not beat a newer
    # correction merely because it overlaps a broad query more strongly.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite fruit is mango, and I often use mango in breakfast smoothies.",
            "entities": [],
            "updated_at": "2026-09-23T12:00:00Z",
        },
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite fruit is pear.",
            "entities": [],
            "updated_at": "2026-09-24T12:00:00Z",
        },
    ]
    answer = route("What do you remember about my favorite fruit and breakfast smoothies?", "alpha", "household")
    assert "pear" in answer and "mango" not in answer, answer

    # Hindsight may return both an observation phrased as "User's ..." and
    # its supporting explicit fact phrased as "My ...". They describe one
    # subject and should not appear twice in a memory answer.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "User's favorite tea is mint. | Involving: user",
            "entities": "user, my favorite tea is mint, mint tea",
            "updated_at": "2026-09-25T12:00:00Z",
        },
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite tea is mint.",
            "entities": [{"text": "My favorite tea is mint", "type": "explicit_fact"}],
            "updated_at": "2026-09-24T12:00:00Z",
        },
    ]
    answer = route("What is my tea preference?", "alpha", "household")
    assert answer.casefold().count("mint") == 1, answer

    # Ordinary spelling errors should still resolve the newest explicit fact
    # when enough content words remain recognizable, even if Hindsight's raw
    # text is generic and the canonical fact exists only in its entity field.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "The synthetic user prefers violet comet-42 markers. | Involving: user | Explicit synthetic acceptance fact.",
            "entities": "My favorite fruit is mango, user, violet comet-42 markers",
            "updated_at": "2026-09-23T12:00:00Z",
        },
        {
            "tags": ["hades-explicit-memory"],
            "text": "The synthetic user prefers violet comet-42 markers. | Involving: user | Explicit synthetic acceptance fact.",
            "entities": "user, My favorite fruit is pear, violet comet-42 markers",
            "updated_at": "2026-09-24T12:00:00Z",
        },
    ]
    answer = route("What is my favrite frut?", "alpha", "household")
    assert "pear" in answer and "mango" not in answer, answer

    # The tracked 0.9.2 list API can return the full corrected fact text and
    # comma-separated entities where "favorite fruit" ties the fact's fuzzy
    # overlap. Keep the complete value instead of returning the entity label.
    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "My favorite fruit is pear. | Involving: user | Synthetic correction fixture.",
        "entities": "user, pear, favorite fruit",
        "updated_at": "2026-10-06T12:00:00Z",
    }]
    answer = route("What is my favrite frut?", "legacy-shape", "household")
    assert "pear" in answer and "favorite fruit is pear" in answer.casefold(), answer
    assert "involving:" not in answer.casefold(), answer
    assert "mango" not in answer.casefold(), answer

    # A genuine paraphrase with no lexical match should keep Hindsight's
    # same-bank semantic answer instead of fabricating a local match.
    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: I like pears.",
        "entities": [{"text": "I like pears", "type": "explicit_fact"}],
        "updated_at": "2026-09-24T12:00:00Z",
    }]
    FakeClient.next_recall_rows = [SimpleNamespace(text="You said you enjoy pears.")]
    answer = route("What do you remember about the snack I enjoy?", "alpha", "household")
    assert "enjoy pears" in answer, answer
    assert FakeClient.instances[-1].calls[0][1]["bank_id"] == "hades-user-alpha"

    # Distinct matching subjects remain available on a broad question.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My favorite fruit is pear.",
            "entities": [{"text": "My favorite fruit is pear", "type": "explicit_fact"}],
            "updated_at": "2026-09-24T12:00:00Z",
        },
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My least favorite fruit is durian.",
            "entities": [{"text": "My least favorite fruit is durian", "type": "explicit_fact"}],
            "updated_at": "2026-09-24T11:00:00Z",
        },
    ]
    answer = route("What do I remember about fruit?", "alpha", "household")
    assert "pear" in answer and "durian" in answer, answer

    # Empty/unmatched lists preserve same-bank semantic recall.
    state["items"] = [{"tags": ["hades-explicit-memory"], "text": "Remember the weekly meal plan", "entities": []}]
    answer = route("What is my favorite fruit?", "beta", "household")
    assert answer == "I remember: Semantic fallback result.", answer
    assert requests[-1][0].split("/banks/", 1)[1].startswith("hades-user-beta/"), requests[-1]
    assert FakeClient.instances[-1].calls[0][1]["bank_id"] == "hades-user-beta"

    # A failed bounded list read still falls back to semantic recall for the
    # same actor rather than turning a temporary list outage into false memory.
    list_unavailable = True
    FakeClient.next_recall_rows = [SimpleNamespace(text="same-bank semantic result")]
    answer = route("What do you remember about an unusual trip?", "beta", "household")
    assert answer == "I remember: Same-bank semantic result.", answer
    assert requests[-1][1] == 2, requests[-1]
    assert FakeClient.instances[-1].calls[0][1]["bank_id"] == "hades-user-beta"
    assert FakeClient.instances[-1].closed
    list_unavailable = False

    # An upstream semantic timeout remains honest and still closes the client.
    state["items"] = []
    FakeClient.fail_next_recall = True
    answer = route("What do you remember about a distant holiday?", "beta", "household")
    assert "couldn't complete" in answer and "remembered" in answer, answer
    assert FakeClient.instances[-1].closed

    # Owner memory remains isolated in its dedicated bank.
    state["items"] = []
    route("What is my favorite fruit?", "owner-subject", "owner")
    assert requests[-1][0].split("/banks/", 1)[1].startswith("hades-owner/"), requests[-1]
    assert FakeClient.instances[-1].calls[0][1]["bank_id"] == "hades-owner"

    # The acknowledgement must match Hindsight's actual completion state.
    FakeClient.bank_config_supported = False
    FakeClient.retain_var_async = False
    answer = route("Remember that I like pear", "gamma", "household")
    assert "pear" in answer and "I'll remember that privately" in answer
    retain = FakeClient.instances[-1].calls[0]
    assert retain[0] == "retain" and retain[1]["bank_id"] == "hades-user-gamma"
    assert retain[1]["tags"] == ["hades-explicit-memory"] and retain[1]["retain_async"] is False
    assert "hades-user-gamma" in created_banks, created_banks

    FakeClient.retain_var_async = True
    queued = route("Remember that I like mango", "gamma", "household")
    assert "still saving that privately" in queued and "may not be available yet" in queued, queued
    assert "I'll remember that privately" not in queued, queued
    FakeClient.retain_var_async = False

    # Hindsight 0.10+ stores explicit facts in a dedicated fast bank so their
    # no-extraction retain cannot start a competing same-bank consolidation.
    FakeClient.bank_config_supported = True
    FakeClient.bank_configs["hades-user-delta-explicit"] = {
        "config": {
            "retain_extraction_mode": "concise",
            "enable_observations": True,
            "enable_auto_consolidation": True,
        },
        "overrides": {
            "retain_strategies": {"existing_strategy": {"retain_extraction_mode": "concise"}},
            "enable_observations": True,
        },
    }
    fast = route("Remember that my favorite tea is calendula", "delta", "household")
    assert "I'll remember that privately" in fast, fast
    fast_client = FakeClient.instances[-1]
    fast_call = fast_client.calls[0]
    assert fast_call[0] == "retain", fast_call
    assert fast_call[1]["bank_id"] == "hades-user-delta-explicit", fast_call
    assert fast_call[1]["retain_async"] is False, fast_call
    config_bank, config_updates = FakeClient.config_updates[-1]
    assert config_bank == "hades-user-delta-explicit", (config_bank, config_updates)
    assert config_updates == {
        "retain_extraction_mode": "chunks",
        "enable_observations": False,
    }, config_updates
    assert "existing_strategy" in FakeClient.bank_configs[config_bank]["overrides"]["retain_strategies"]

    # A configured isolated bank needs no second update; lexical recall checks
    # both legacy and isolated banks without crossing actor boundaries.
    updates_before = len(FakeClient.config_updates)
    route("Remember that my tea is rose", "delta", "household")
    assert len(FakeClient.config_updates) == updates_before

    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: My favorite tea is calendula.",
        "entities": [{"text": "My favorite tea is calendula", "type": "explicit_fact"}],
        "updated_at": "2026-10-06T12:00:00Z",
    }]
    answer = route("What do you remember about my favorite tea?", "delta", "household")
    assert "calendula" in answer, answer
    assert any("hades-user-delta-explicit/memories/list" in row[0] for row in requests[-2:]), requests[-2:]

    state["items"] = []
    semantic = route("What do you remember about the flavor I usually drink?", "delta", "household")
    assert semantic == "I remember: Semantic fallback result.", semantic
    semantic_calls = FakeClient.instances[-1].calls
    assert [call[1]["bank_id"] for call in semantic_calls] == [
        "hades-user-delta-explicit", "hades-user-delta",
    ], semantic_calls

    # Natural correction language updates only an existing matching fact for
    # the same subject; a correction prefix without a matching saved detail is
    # left to the ordinary model path and does not create memory.
    FakeClient.bank_configs["hades-user-correction-explicit"] = {
        "config": {
            "retain_extraction_mode": "chunks",
            "enable_observations": False,
        },
        "overrides": {},
    }
    created_banks.add("hades-user-correction-explicit")
    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: my favorite fruit is mango.",
        "entities": "user, mango, favorite fruit",
        "updated_at": "2026-10-06T11:00:00Z",
    }]
    corrected = route("Correction: my favorite fruit is pear.", "correction", "household")
    assert "I'll remember that privately" in corrected, corrected
    correction_client = FakeClient.instances[-1]
    assert correction_client.calls[0][1]["bank_id"] == "hades-user-correction-explicit", correction_client.calls

    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: my favorite fruit is mango.",
        "updated_at": "2026-10-06T11:00:00Z",
    }, {
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: my favorite fruit is pear.",
        "updated_at": "2026-10-06T12:00:00Z",
    }]
    answer = route("What is my favrite frut?", "correction", "household")
    assert "pear" in answer.casefold() and "mango" not in answer.casefold(), answer

    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: My favorite tea is mint.",
        "updated_at": "2026-10-06T11:00:00Z",
    }]
    before_calls = len(FakeClient.instances)
    config_updates_before = len(FakeClient.config_updates)
    unmatched_correction = route("Correction: my favorite fruit is pear.", "correction-unmatched", "household")
    assert unmatched_correction is None, unmatched_correction
    assert len(FakeClient.instances) == before_calls + 1
    assert FakeClient.instances[-1].calls == []
    assert "hades-user-correction-unmatched-explicit" not in created_banks
    assert len(FakeClient.config_updates) == config_updates_before

    # Legacy APIs stay on the original bank and receive no newer bank config.
    FakeClient.api_version = "0.9.2"
    route("Remember that I like pear", "legacy", "household")
    assert FakeClient.instances[-1].calls[0][0] == "retain"

    # An existing bank is not recreated or renamed.
    created_banks.add("hades-user-existing")
    before_puts = sum(row[0].startswith("PUT ") for row in requests)
    namespace["_hades_ensure_memory_bank"]("hades-user-existing")
    after_puts = sum(row[0].startswith("PUT ") for row in requests)
    assert before_puts == after_puts
    assert FakeClient.instances[-1].closed
finally:
    urllib.request.urlopen = old_urlopen
    if old_endpoint is None:
        os.environ.pop("HADES_HINDSIGHT_URL", None)
    else:
        os.environ["HADES_HINDSIGHT_URL"] = old_endpoint

score_diagnostics = namespace["_hades_log_memory_recall_scores"]
old_score_diagnostics = os.environ.get("HADES_MEMORY_SCORE_DIAGNOSTICS")
score_log_before = len(score_log)
try:
    os.environ["HADES_MEMORY_SCORE_DIAGNOSTICS"] = "1"
    score_diagnostics("synthetic", [SimpleNamespace(
        id="private-memory-id",
        text="PRIVATE-SYNTHETIC-FACT",
        type="observation",
        scores={"final": 0.82, "reranker": 0.71, "private": "excluded"},
    )])
    assert len(score_log) == score_log_before + 1, score_log
    diagnostic_payload = score_log[-1][2]
    assert '\"rank\": 1' in diagnostic_payload and '\"final\": 0.82' in diagnostic_payload
    assert '\"type\": \"observation\"' in diagnostic_payload
    assert "PRIVATE-SYNTHETIC-FACT" not in diagnostic_payload
    assert "private-memory-id" not in diagnostic_payload
    assert "excluded" not in diagnostic_payload
    os.environ["HADES_MEMORY_SCORE_DIAGNOSTICS"] = "0"
    score_diagnostics("synthetic", [SimpleNamespace(scores={"final": 0.99})])
    assert len(score_log) == score_log_before + 1, score_log
finally:
    if old_score_diagnostics is None:
        os.environ.pop("HADES_MEMORY_SCORE_DIAGNOSTICS", None)
    else:
        os.environ["HADES_MEMORY_SCORE_DIAGNOSTICS"] = old_score_diagnostics

print("PASS Hindsight explicit retain/recall uses only the authenticated actor bank")
print("PASS tagged recent-memory results reject unrelated tags and malformed entries")
print("PASS corrections, typoed preference queries, and paraphrases keep actor-scoped current memory")
print("PASS direct recent matches skip semantic recall; paraphrases and list timeouts fall back safely; semantic failures close the client and stay honest")
print("PASS explicit-memory retains and exact/typo recall skip automatic Hindsight prefetch")
print("PASS opt-in recall score diagnostics exclude memory text, IDs, and nonnumeric fields")
