#!/usr/bin/env python3
"""Contract for privacy-safe HADES memory benchmark log parsing."""
from __future__ import annotations

import importlib.util
import io
import json
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
        "items=1 lexical_matches=1 candidates=1 error=/tmp/private\n"
        "2026-10-09 INFO HADES prefetch diagnostics "
        "status=completed results=1 types=world,experience reason=none error=none "
        "query=private-user-fact\n"
        "2026-10-09 INFO HADES prefetch diagnostics "
        "status=skipped results=0 types=none reason=explicit_memory_route error=none\n"
        "2026-10-09 INFO HADES prefetch diagnostics "
        "status=error results=0 types=none reason=none error=TimeoutError\n"
        "2026-10-09 INFO HADES queued prefetch diagnostics "
        "status=completed results=2 elapsed_ms=18.5 error=none query=private-fact\n"
        "2026-10-09 INFO HADES queued prefetch diagnostics "
        "status=error results=0 elapsed_ms=oops error=/private/path\n",
        encoding="utf-8",
    )
    rows, offset = MODULE.read_safe_explicit_list_diagnostics(log_path)
    assert rows == [
        {"items": 2, "lexical_matches": 1, "candidates": 1, "error": "none"},
        {"items": 1, "lexical_matches": 1, "candidates": 1, "error": "unknown"},
    ], rows
    assert offset == log_path.stat().st_size
    prefetch_rows, prefetch_offset = MODULE.read_safe_hades_prefetch_diagnostics(log_path)
    assert prefetch_rows == [
        {"status": "completed", "result_count": 1,
         "result_types": ["experience", "world"]},
        {"status": "skipped", "result_count": 0,
         "result_types": [], "skip_reason": "explicit_memory_route"},
        {"status": "error", "result_count": 0,
         "result_types": [], "error_type": "TimeoutError"},
    ], prefetch_rows
    assert prefetch_offset == log_path.stat().st_size
    queued_rows, queued_offset = MODULE.read_safe_hades_queued_prefetch_diagnostics(log_path)
    assert queued_rows == [
        {"status": "completed", "result_count": 2, "elapsed_ms": 18.5},
    ], queued_rows
    assert queued_offset == log_path.stat().st_size

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False

payload = {
    "results": [{"text": "private Denver fact", "type": "world", "id": "secret"}],
    "chunks": {"secret-id": {"text": "Denver", "chunk_index": 0}},
}
original_urlopen = MODULE.urllib.request.urlopen
captured = {}
def fake_urlopen(request, *, timeout):
    captured["url"] = request.full_url
    captured["body"] = json.loads(request.data)
    captured["timeout"] = timeout
    return FakeResponse(json.dumps(payload).encode())

MODULE.urllib.request.urlopen = fake_urlopen
try:
    summary = MODULE.hindsight_chunk_recall_diagnostic(
        "http://127.0.0.1:8888", "hades-synthetic",
        "Where did I say I moved?", "Denver",
    )
finally:
    MODULE.urllib.request.urlopen = original_urlopen
assert summary == {
    "result_count": 1,
    "result_type_counts": {"world": 1},
    "chunk_count": 1,
    "marker_in_result": True,
    "marker_in_chunk": True,
    "elapsed_ms": summary.get("elapsed_ms"),
}, summary
assert isinstance(summary["elapsed_ms"], (int, float)) and summary["elapsed_ms"] >= 0
assert captured["body"]["include_chunks"] is True
assert captured["body"]["types"] == ["world", "experience"]
assert captured["timeout"] == 30
assert "private Denver fact" not in repr(summary) and "secret" not in repr(summary)
serialized = MODULE.safe_repetitions([{
    "stacks": {"hades": {"hindsight_chunk_recall_after_turn": summary}},
}])
assert serialized[0]["stacks"]["hades"]["hindsight_chunk_recall_after_turn"] == summary

print("PASS explicit-memory list diagnostics retain only validated aggregate fields")
print("PASS Hindsight raw-chunk recall diagnostics retain only aggregate visibility")
