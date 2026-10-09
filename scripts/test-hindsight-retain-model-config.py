#!/usr/bin/env python3
"""Contract for the benchmark-only Hindsight retain-model override."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "hades_memory_pair_benchmark",
    ROOT / "scripts/benchmark-hades-memory-pair.py",
)
if spec is None or spec.loader is None:
    raise SystemExit("could not load paired benchmark helpers")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.hindsight_retain_environment("qwen3:14b", "qwen3:14b") == []
assert module.hindsight_retain_environment("qwen3:14b", "qwen3:8b") == [
    "-e", "HINDSIGHT_API_RETAIN_LLM_MODEL=qwen3:8b"
]
print("PASS retain-only model override leaves other Hindsight operations unchanged")
