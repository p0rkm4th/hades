#!/usr/bin/env python3
"""Keep workspace benchmark validation snapshots bounded and informative."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "workspace_pair_benchmark",
    ROOT / "scripts" / "benchmark-hades-workspace-read-pair.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

agent = SimpleNamespace(
    valid_tool_names={"read_file", "terminal", "private_tool"},
    tools=[
        {"type": "function", "function": {"name": "read_file"}},
        {"type": "function", "function": {"name": "search_files"}},
        {"type": "function", "function": {"name": "private_tool"}},
    ],
)
assert MODULE.workspace_catalog_snapshot(agent) == {
    "valid_workspace_tools": ["read_file", "terminal"],
    "present_workspace_tool_schemas": ["read_file", "search_files"],
}
assert MODULE.command_runs_tests("python -m unittest discover -v")
assert MODULE.command_runs_tests("python -B -m unittest tests.test_feature")
assert MODULE.command_runs_tests("pytest -q tests/test_feature.py")
assert not MODULE.command_runs_tests("python scripts/check_workspace.py")
assert not MODULE.command_runs_tests(None)
for prompt, phase in (
    (MODULE.DIAGNOSE_PROMPT, "diagnose"),
    (MODULE.FIX_PROMPT, "fix"),
    (MODULE.PROMPT, "read"),
    (MODULE.README_PROMPT, "readme"),
    (MODULE.EXPLAIN_PROMPT, "explain"),
    (MODULE.SEARCH_PROMPT, "search"),
    (MODULE.SMALL_EDIT_CONTEXT_PROMPT, "inspect"),
    (MODULE.SMALL_EDIT_PROMPT, "edit"),
    (MODULE.FOCUSED_TEST_PROMPT, "focused_test"),
    (MODULE.SMALL_DIFF_PROMPT, "review_diff"),
    (MODULE.COMMIT_PROMPT, "commit"),
):
    assert MODULE.classify_benchmark_phase([
        {"role": "user", "content": prompt},
    ]) == phase
assert MODULE.classify_benchmark_phase([
    {"role": "user", "content": MODULE.SMALL_DIFF_PROMPT},
    {"role": "assistant", "content": "I'll inspect the diff."},
    {"role": "user", "content": MODULE.COMMIT_PROMPT},
]) == "commit"
assert MODULE.classify_benchmark_phase([
    {"role": "user", "content": "an unseeded owner request"},
]) == "other"
assert MODULE.classify_benchmark_phase(None) == "other"
assert MODULE.run_call_timing(10.0, 12.0, []) == {
    "wrapper_elapsed_ms": 2000.0,
    "original_run_call_count": 0,
    "original_run_elapsed_ms": None,
    "overlay_pre_ms": None,
    "overlay_post_ms": None,
    "interstitial_ms": None,
    "overlay_outside_original_ms": None,
}
timing = MODULE.run_call_timing(10.0, 12.0, [(10.2, 11.7)])
assert timing == {
    "wrapper_elapsed_ms": 2000.0,
    "original_run_call_count": 1,
    "original_run_elapsed_ms": 1500.0,
    "overlay_pre_ms": 200.0,
    "overlay_post_ms": 300.0,
    "interstitial_ms": 0.0,
    "overlay_outside_original_ms": 500.0,
}
timing = MODULE.run_call_timing(10.0, 13.0, [(10.2, 10.7), (11.0, 11.4)])
assert timing["original_run_call_count"] == 2
assert timing["interstitial_ms"] == 300.0
assert timing["wrapper_elapsed_ms"] == (
    timing["original_run_elapsed_ms"]
    + timing["overlay_outside_original_ms"]
)
assert MODULE.workspace_diff_evidence_markers([
    {"role": "system", "content": "<workspace_diff>secret source text"},
]) == {
    "workspace_diff_evidence_present": True,
    "workspace_diff_evidence_truncated": False,
    "workspace_diff_evidence_unavailable": False,
}
assert MODULE.workspace_diff_evidence_markers([
    {"role": "system", "content": "stable workspace review policy"},
    {"role": "user", "content": "<workspace_diff>secret source text"},
]) == {
    "workspace_diff_evidence_present": True,
    "workspace_diff_evidence_truncated": False,
    "workspace_diff_evidence_unavailable": False,
}
assert MODULE.workspace_diff_evidence_markers([
    {"role": "system", "content": "The diff evidence below is truncated."},
]) == {
    "workspace_diff_evidence_present": False,
    "workspace_diff_evidence_truncated": True,
    "workspace_diff_evidence_unavailable": False,
}
assert MODULE.workspace_diff_evidence_markers([
    {"role": "system", "content": "Diff evidence is unavailable."},
]) == {
    "workspace_diff_evidence_present": False,
    "workspace_diff_evidence_truncated": False,
    "workspace_diff_evidence_unavailable": True,
}
def sample_route(value):
    return value


value, return_line = MODULE.call_with_return_line(sample_route, "ok")
assert value == "ok"
assert return_line == sample_route.__code__.co_firstlineno + 1
MODULE.require_provider_capture(0, [])
MODULE.require_provider_capture(2, [{"elapsed_ms": 100}])
try:
    MODULE.require_provider_capture(1, [])
except RuntimeError as exc:
    assert "refusing to publish an unprofiled workspace comparison" in str(exc)
else:
    raise AssertionError("missing provider telemetry must fail closed")
agent.tools = None
assert MODULE.workspace_catalog_snapshot(agent) == {
    "valid_workspace_tools": ["read_file", "terminal"],
    "present_workspace_tool_schemas": [],
}
print("PASS validation diagnostics distinguish executable workspace tools from present schemas")
