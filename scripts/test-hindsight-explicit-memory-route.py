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
    if isinstance(node, ast.FunctionDef)
    and node.name in {
        "_hades_overlay_non_hermes_interpreter",
        "_hades_is_hermes_auxiliary_prompt",
        "_hades_explicit_memory_recall_requested",
        "_hades_ensure_memory_bank",
        "_hades_direct_memory_response",
        "_hades_prefetch",
    }
}
REQUIRED_FUNCTIONS = {
    "_hades_overlay_non_hermes_interpreter",
    "_hades_is_hermes_auxiliary_prompt",
    "_hades_explicit_memory_recall_requested",
    "_hades_ensure_memory_bank",
    "_hades_direct_memory_response",
    "_hades_prefetch",
}
if FUNCTIONS.keys() != REQUIRED_FUNCTIONS:
    raise SystemExit(f"missing Hindsight functions: {REQUIRED_FUNCTIONS - FUNCTIONS.keys()}")


class FakeClient:
    instances: list["FakeClient"] = []
    next_recall_rows: list[SimpleNamespace] | None = None
    fail_next_recall = False

    def __init__(self, _base_url: str, *, timeout: int):
        self.timeout = timeout
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False
        self.recall_rows = type(self).next_recall_rows or [
            SimpleNamespace(text="semantic fallback result")
        ]
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
        return {"status": "synthetic"}

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
        r"what\s+is\s+(?:the|my)\s+.*(?:memory|fact|marker|fruit)|"
        r"what\s+(?:was|is|were|are)\s+(?:the|my)\s+.{1,80}\s+i\s+mentioned|"
        r"recall|look\s+in\s+(?:your|my)\s+memory)\b",
        re.IGNORECASE,
    ),
    "json": json,
    "os": os,
    "re": re,
    "_hades_nonpersonal_state_turn": lambda _text: False,
    "Path": Path,
    "_hades_logger": SimpleNamespace(
        warning=lambda *_args: None,
        info=lambda *_args: None,
        debug=lambda *_args: None,
    ),
}
exec(compile(ast.Module(
    body=[
        next(node for node in ast.walk(TREE)
             if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_HADES_HERMES_AUXILIARY_PROMPT" for target in node.targets)),
        FUNCTIONS["_hades_overlay_non_hermes_interpreter"],
        FUNCTIONS["_hades_is_hermes_auxiliary_prompt"],
        FUNCTIONS["_hades_explicit_memory_recall_requested"],
        FUNCTIONS["_hades_ensure_memory_bank"],
        FUNCTIONS["_hades_direct_memory_response"],
        FUNCTIONS["_hades_prefetch"],
    ],
    type_ignores=[],
), "sitecustomize.py", "exec"), namespace)
interpreter_check = namespace["_hades_overlay_non_hermes_interpreter"]
assert interpreter_check("/usr/bin/python3", "/opt/hades-hermes/bin/hermes")
assert not interpreter_check("/opt/hades-hermes/bin/python3", "/opt/hades-hermes/bin/hermes")
assert not interpreter_check("/usr/bin/python3", "")
route = namespace["_hades_direct_memory_response"]


class FakeSemanticClient:
    def __init__(self, calls):
        self.calls = calls

    def arecall(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(results=[])


class FakePrefetchProvider:
    _memory_mode = "hybrid"
    _auto_recall = True
    _recall_max_input_chars = 0
    _recall_max_tokens = 1200
    _recall_tags = []
    _recall_tags_match = "any"
    _recall_types = []
    _recall_prompt_preamble = ""
    _bank_id = "hades-user-alpha"
    _budget = "low"

    def __init__(self):
        self.semantic_calls = []

    def _run_hindsight_operation(self, operation):
        return operation(FakeSemanticClient(self.semantic_calls))


prefetch = namespace["_hades_prefetch"].__get__(
    FakePrefetchProvider(), FakePrefetchProvider
)
prefetch_provider = prefetch.__self__
for prompt in (
    "Remember that my favorite fruit is mango.",
    "What do you remember about the fruit I enjoy?",
    "What was the savings target I mentioned?",
    "What is my favorite fruit?",
    "What is my favrite frut?",
):
    assert prefetch(prompt) == "", prompt
assert prefetch("### Task:\nGenerate a concise title summarizing the chat history.") == ""
assert prefetch_provider.semantic_calls == [], prefetch_provider.semantic_calls
assert prefetch("Tell me about the restaurant I liked") == ""
assert len(prefetch_provider.semantic_calls) == 1, prefetch_provider.semantic_calls
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
    assert requests[-1][0] == (
        "http://hindsight.synthetic:8888/v1/default/banks/"
        "hades-user-alpha/memories/list?tags=hades-explicit-memory&tags_match=any&state=valid&limit=100"
    ), requests[-1]
    assert requests[-1][1] == 2, requests[-1]
    client = FakeClient.instances[-1]
    assert client.calls == [], client.calls
    assert client.closed

    # Natural follow-ups such as "what was ... I mentioned" must use the
    # authenticated private-memory path instead of the ordinary-chat fallback.
    state["items"] = [
        {
            "tags": ["hades-explicit-memory"],
            "text": "User explicitly asked HADES to remember: My savings target is $3,000.",
            "entities": [{"text": "My savings target is $3,000", "type": "explicit_fact"}],
            "updated_at": "2026-10-09T12:00:00Z",
        },
    ]
    answer = route("What was the savings target I mentioned?", "alpha", "owner")
    assert "$3,000" in answer, answer
    assert FakeClient.instances[-1].calls == [], FakeClient.instances[-1].calls

    # When a partial entity label ties the full memory's lexical score, keep
    # the full canonical text so the answer does not discard the remembered
    # value (for example, a numeric target).
    state["items"] = [{
        "tags": ["hades-explicit-memory"],
        "text": "User explicitly asked HADES to remember: My savings target is $3,000.",
        "entities": [{"text": "savings target", "type": "explicit_fact"}],
        "updated_at": "2026-10-09T12:00:00Z",
    }]
    answer = route("What was the savings target I mentioned?", "alpha", "owner")
    assert "$3,000" in answer, answer
    assert FakeClient.instances[-1].calls == [], FakeClient.instances[-1].calls

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
    assert answer == "I remember: semantic fallback result", answer
    assert requests[-1][0].split("/banks/", 1)[1].startswith("hades-user-beta/"), requests[-1]
    assert FakeClient.instances[-1].calls[0][1]["bank_id"] == "hades-user-beta"

    # A failed bounded list read still falls back to semantic recall for the
    # same actor rather than turning a temporary list outage into false memory.
    list_unavailable = True
    FakeClient.next_recall_rows = [SimpleNamespace(text="same-bank semantic result")]
    answer = route("What do you remember about an unusual trip?", "beta", "household")
    assert answer == "I remember: same-bank semantic result", answer
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

    # Explicit retain remains synchronous and scoped to the authenticated user's bank.
    answer = route("Remember that I like pear", "gamma", "household")
    assert "pear" in answer and "private memory" in answer
    retain = FakeClient.instances[-1].calls[0]
    assert retain[0] == "retain" and retain[1]["bank_id"] == "hades-user-gamma"
    assert retain[1]["tags"] == ["hades-explicit-memory"] and retain[1]["retain_async"] is False
    assert "hades-user-gamma" in created_banks, created_banks

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

print("PASS Hindsight explicit retain/recall uses only the authenticated actor bank")
print("PASS tagged recent-memory results reject unrelated tags and malformed entries")
print("PASS corrections, typoed preference queries, and paraphrases keep actor-scoped current memory")
print("PASS direct recent matches skip semantic recall; paraphrases and list timeouts fall back safely; semantic failures close the client and stay honest")
print("PASS explicit-memory retains and exact/typo recall skip automatic Hindsight prefetch")
