#!/usr/bin/env python3
"""Guard subject-bound Hindsight writes and recalls against cached bank sets."""
from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "hermes/sitecustomize.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
helper = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef)
    and node.name == "_hades_bind_memory_provider_bank"
)
namespace: dict[str, object] = {}
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(SOURCE), "exec"), namespace)
bind = namespace["_hades_bind_memory_provider_bank"]


class CachedHindsight0103:
    """Model the bank fields and builder used by the supported 0.10.3 plugin."""

    def __init__(self, bank: str):
        self._bank_id = bank
        self._static_bank_id = bank
        self._mirror_to_own_bank = True
        self._additional_bank_ids = ["configured-extra"]
        self._recall_additional_bank_ids = ["configured-read-only"]
        self._write_bank_ids = self._build_write_bank_ids()

    def _build_write_bank_ids(self) -> list[str]:
        ordered = [self._bank_id]
        if self._mirror_to_own_bank and self._static_bank_id not in ordered:
            ordered.append(self._static_bank_id)
        for bank in self._additional_bank_ids:
            if bank not in ordered:
                ordered.append(bank)
        return ordered

    def _build_recall_bank_ids(self) -> list[str]:
        ordered = list(self._write_bank_ids)
        for bank in self._recall_additional_bank_ids:
            if bank not in ordered:
                ordered.append(bank)
        return ordered


class LegacyHindsightProvider:
    """Older provider shape without cached multi-bank fields."""

    def __init__(self):
        self._bank_id = "legacy-default"


source = SOURCE.read_text(encoding="utf-8")
if "_hades_bind_memory_provider_bank(memory_provider, memory_bank)" not in source:
    raise SystemExit("authenticated agent scope does not bind Hindsight providers")

for bank in ("hades-owner", "hades-user-alpha", "hades-user-beta", "hades-denied"):
    provider = CachedHindsight0103("configured-static-bank")
    if bind(provider, bank) is not True:
        raise SystemExit(f"provider bank bind failed for {bank}")
    if provider._bank_id != bank:
        raise SystemExit(f"primary Hindsight bank did not follow scope: {bank}")
    if provider._write_bank_ids != [bank]:
        raise SystemExit(f"automatic retain can still fan out beyond {bank}: {provider._write_bank_ids}")
    if provider._build_recall_bank_ids() != [bank]:
        raise SystemExit(f"memory recall can still escape {bank}: {provider._build_recall_bank_ids()}")

legacy = LegacyHindsightProvider()
if bind(legacy, "hades-user-legacy") is not True or legacy._bank_id != "hades-user-legacy":
    raise SystemExit("legacy single-bank provider compatibility regressed")
if bind(object(), "hades-denied") is not False:
    raise SystemExit("provider without a Hindsight bank was treated as scoped")

print("PASS Hindsight 0.10.3 cached retain and recall banks follow trusted scope")
print("PASS profile fan-out cannot cross owner, household, or denied scopes")
print("PASS legacy single-bank provider compatibility is retained")
