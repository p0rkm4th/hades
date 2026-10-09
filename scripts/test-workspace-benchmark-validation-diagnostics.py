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
assert MODULE.workspace_diff_evidence_markers([
    {"role": "system", "content": "<workspace_diff>secret source text"},
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
agent.tools = None
assert MODULE.workspace_catalog_snapshot(agent) == {
    "valid_workspace_tools": ["read_file", "terminal"],
    "present_workspace_tool_schemas": [],
}
print("PASS validation diagnostics distinguish executable workspace tools from present schemas")
