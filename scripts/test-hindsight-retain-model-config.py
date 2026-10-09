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
assert module.hindsight_ollama_context_environment(None) == []
assert module.hindsight_ollama_context_environment(8192) == [
    "-e", "HINDSIGHT_API_LLM_OLLAMA_NUM_CTX=8192"
]
for invalid in (0, -1, True, "8192"):
    try:
        module.hindsight_ollama_context_environment(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"accepted invalid Hindsight num_ctx: {invalid!r}")
print("PASS retain-only model and native Ollama context overrides preserve operation scope")
