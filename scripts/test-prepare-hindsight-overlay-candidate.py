#!/usr/bin/env python3
"""Verify Hindsight overlay composition preserves unrelated deployment code."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hermes/sitecustomize.py"
PREPARER = ROOT / "scripts/prepare-hindsight-overlay-candidate.py"
FUNCTION = "_hades_direct_memory_response"


def get_function(source: str):
    found = [
        node for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name == FUNCTION
    ]
    assert len(found) == 1
    return found[0]


source = SOURCE.read_text(encoding="utf-8")
# Model an installed overlay with one stale Hindsight function and unrelated
# deployment-local code before and after it.
target = source.replace(
    "The generic capability explainer must not swallow a real",
    "The old fixture baseline must not swallow a real",
    1,
)
assert target != source
marker = "\n# deployment-local fixture retained by composition\n"
target += marker
with tempfile.TemporaryDirectory(prefix="hades-overlay-candidate-test-") as temporary:
    root = Path(temporary)
    active = root / "active.py"
    output = root / "candidate.py"
    active.write_text(target, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(PREPARER), "--active-overlay", str(active), "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    candidate = output.read_text(encoding="utf-8")
    source_node = get_function(source)
    candidate_node = get_function(candidate)
    assert ast.get_source_segment(source, source_node) == ast.get_source_segment(candidate, candidate_node)
    assert candidate.endswith(marker)
    assert candidate == source + marker
    assert output.stat().st_mode & 0o777 == 0o600
    before = output.read_bytes()
    rejected = subprocess.run(
        [sys.executable, str(PREPARER), "--active-overlay", str(active), "--output", str(output)],
        capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    assert output.read_bytes() == before
    compile(candidate, str(output), "exec")
print("PASS candidate replaces only the direct-memory function, preserves deployment-local code, and refuses overwrite")
