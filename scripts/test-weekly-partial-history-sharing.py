#!/usr/bin/env python3
"""Join synthetic Weekly partial composition, canonical history, and sharing."""
from __future__ import annotations

import ast
import hashlib
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integrations.automation import LifecycleStore, SummaryHistory, compose_summary

source = (ROOT / "hermes/sitecustomize.py").read_text(encoding="utf-8")
tree = ast.parse(source)
weekly_route = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_phase2_weekly_response"
)

with tempfile.TemporaryDirectory(prefix="hades-weekly-partial-history-") as temporary:
    state_path = Path(temporary) / "epsilon.sqlite"
    owner, beta, gamma = "synthetic-owner", "synthetic-beta", "synthetic-gamma"
    store = LifecycleStore(str(state_path))
    store.put(
        "weekly-partial-operation", owner, "weekly-household-summary",
        {"shared_subjects": [beta]}, "PROMOTED",
        {"status": "PROMOTED", "production_schedule": True},
    )

    def unavailable_groceries() -> str:
        raise OSError("synthetic Grocy outage")

    composed = compose_summary(
        {
            "grocy.household": ("Groceries", unavailable_groceries),
            "hades-core.health": ("Servers", lambda: "All servers look okay."),
            "backup.evidence": ("Backups", lambda: "Last verified backup is healthy."),
        },
        lambda _resource: True,
    )
    assert "Unavailable this week: Groceries." in composed, composed
    assert "All servers look okay." in composed and "Last verified backup is healthy." in composed

    history = SummaryHistory(str(state_path))
    history.record(owner, "2026-09-26T12:00:00Z", composed, "groceries")
    namespace = {
        "re": re,
        "_HADES_PENDING_PHASE2": {},
        "_hades_health_watch_state_path": lambda: str(state_path),
    }
    exec(compile(ast.Module(body=[weekly_route], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
    answer = namespace["_hades_phase2_weekly_response"]

    digest_before = hashlib.sha256(state_path.read_bytes()).hexdigest()
    owner_result = answer("Show the latest weekly household summary.", owner, "owner")
    beta_result = answer("Show the latest weekly household summary.", beta, "household")
    gamma_result = answer("Show the latest weekly household summary.", gamma, "household")
    digest_after = hashlib.sha256(state_path.read_bytes()).hexdigest()

    assert owner_result == composed, owner_result
    assert beta_result == composed, beta_result
    assert "Unavailable this week: Groceries." in beta_result
    assert "Servers:" in beta_result and "Backups:" in beta_result
    assert "No shared Weekly Household Summary is available" in gamma_result, gamma_result
    assert "All servers look okay." not in gamma_result and "Last verified backup" not in gamma_result
    assert digest_after == digest_before, "history retrieval mutated canonical summary or sharing state"

print("PASS partial Weekly result preserves healthy sections and the unavailable Groceries disclosure")
print("PASS owner and the authorized household member read the same bounded result")
print("PASS unshared household member is denied and retrieval leaves stored state unchanged")
