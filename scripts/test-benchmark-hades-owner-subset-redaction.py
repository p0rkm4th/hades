#!/usr/bin/env python3
"""Contract for metrics-only owner-subset benchmark artifacts."""

import importlib.util
import pathlib
import sys


SCRIPT = pathlib.Path(__file__).with_name("benchmark-hades-owner-subset.py")
SPEC = importlib.util.spec_from_file_location("owner_subset", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

source = {
    "stack": "hades",
    "case": "core-08",
    "prompt": "synthetic private prompt",
    "answer": "synthetic private answer",
    "status": 200,
    "prompt_bytes": 123,
    "provider_metrics": [{"message_bytes": 123}],
}
public = MODULE.public_turn_record(source)
controlled = MODULE.apply_request_overrides(
    {"model": "same-model", "temperature": 0}, {"max_tokens": 512}
)
controls = MODULE.capture_request_controls(controlled)

assert "prompt" not in public
assert "answer" not in public
assert public["stack"] == "hades"
assert public["case"] == "core-08"
assert public["status"] == 200
assert public["provider_metrics"] == [{"message_bytes": 123}]
assert controls["max_tokens"] == 512
assert controls["temperature"] == 0
print("PASS owner-subset artifacts redact turns and enforce captured generation controls")
