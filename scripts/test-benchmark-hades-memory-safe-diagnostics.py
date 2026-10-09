#!/usr/bin/env python3
"""Contract for privacy-safe HADES memory benchmark log parsing."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "benchmark_hades_memory_pair",
    ROOT / "scripts/benchmark-hades-memory-pair.py",
)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("could not load paired memory benchmark")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

with tempfile.TemporaryDirectory(prefix="hades-memory-log-contract-") as directory:
    log_path = Path(directory) / "gateway.log"
    log_path.write_text(
        "2026-10-09 INFO Explicit Hindsight list diagnostics "
        "items=2 lexical_matches=1 candidates=1 error=none "
        "query=private-user-fact\n"
        "2026-10-09 INFO Explicit Hindsight list diagnostics "
        "items=oops lexical_matches=1 candidates=1 error=none\n"
        "2026-10-09 INFO Explicit Hindsight list diagnostics "
        "items=1 lexical_matches=1 candidates=1 error=/tmp/private\n",
        encoding="utf-8",
    )
    rows, offset = MODULE.read_safe_explicit_list_diagnostics(log_path)
    assert rows == [
        {"items": 2, "lexical_matches": 1, "candidates": 1, "error": "none"},
        {"items": 1, "lexical_matches": 1, "candidates": 1, "error": "unknown"},
    ], rows
    assert offset == log_path.stat().st_size

print("PASS explicit-memory list diagnostics retain only validated aggregate fields")
