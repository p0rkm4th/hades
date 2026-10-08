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
    {"model": "same-model"},
    {"max_tokens": 512, "temperature": 1.0, "seed": 23},
)
controls = MODULE.capture_request_controls(controlled)
from benchmark_child_environment import benchmark_child_environment

child_env = benchmark_child_environment({
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "TMPDIR": "/private-temp",
    "GROCY_API_KEY": "do-not-inherit",
    "HADES_GROCY_API_KEY_FILE": "/private/grocy-key",
    "HADES_OWNER_SUBJECT_IDS": "real-owner",
    "HADES_STAGE_ROOT": "/private/stage",
    "HERMES_HOME": "/private/hermes",
    "PYTHONPATH": "/private/python",
    "HTTPS_PROXY": "http://proxy.invalid",
    "LD_PRELOAD": "/private/inject.so",
})

assert "prompt" not in public
assert "answer" not in public
assert public["stack"] == "hades"
assert public["case"] == "core-08"
assert public["status"] == 200
assert public["provider_metrics"] == [{"message_bytes": 123}]
assert controls["max_tokens"] == 512
assert controls["temperature"] == 1.0
assert controls["seed"] == 23
assert child_env == {
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "TMPDIR": "/private-temp",
    "NO_PROXY": "127.0.0.1,localhost,::1",
    "no_proxy": "127.0.0.1,localhost,::1",
}
print("PASS owner-subset artifacts redact turns and enforce captured generation controls")
print("PASS benchmark child environments exclude credentials, service config, proxies, and injection paths")
