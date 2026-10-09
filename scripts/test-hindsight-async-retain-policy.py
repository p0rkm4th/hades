#!/usr/bin/env python3
"""Check automatic Hindsight writes stay async while explicit sync survives."""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / "hermes/sitecustomize.py").read_text(encoding="utf-8"))
wrappers = {}
for node in ast.walk(TREE):
    if isinstance(node, ast.AsyncFunctionDef) and node.name in {
        "_hades_aretain", "_hades_aretain_batch",
    }:
        wrappers[node.name] = node
if wrappers.keys() != {"_hades_aretain", "_hades_aretain_batch"}:
    raise SystemExit("Hindsight retain wrappers were not found")


class FakeClient:
    def __init__(self):
        self.calls = []


async def original_retain(self, *args, **kwargs):
    self.calls.append(("retain", kwargs.get("retain_async")))
    return kwargs.get("retain_async")


async def original_retain_batch(self, *args, **kwargs):
    self.calls.append(("retain_batch", kwargs.get("retain_async")))
    return kwargs.get("retain_async")


namespace = {
    "_hades_original_aretain": original_retain,
    "_hades_original_aretain_batch": original_retain_batch,
}
exec(compile(ast.Module(body=list(wrappers.values()), type_ignores=[]),
             "sitecustomize.py", "exec"), namespace)

for name, operation in (
    ("_hades_aretain", "retain"),
    ("_hades_aretain_batch", "retain_batch"),
):
    wrapped = namespace[name]
    automatic = FakeClient()
    assert asyncio.run(wrapped(automatic)) is True
    assert automatic.calls == [(operation, True)], automatic.calls

    explicit_sync = FakeClient()
    assert asyncio.run(wrapped(explicit_sync, retain_async=False)) is False
    assert explicit_sync.calls == [(operation, False)], explicit_sync.calls

    explicit_async = FakeClient()
    assert asyncio.run(wrapped(explicit_async, retain_async=True)) is True
    assert explicit_async.calls == [(operation, True)], explicit_async.calls

print("PASS automatic Hindsight writes are async; explicit sync/async settings are preserved")
