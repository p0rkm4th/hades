#!/usr/bin/env python3
"""Keep the fixed HADES health reader explicit and fail-closed."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch


os.environ.pop("HADES_EPSILON_HEALTH_URL", None)
spec = importlib.util.spec_from_file_location(
    "epsilon_source_health_contract",
    Path(__file__).resolve().parents[1] / "integrations/epsilon-source/server.py",
)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.HEALTH_URL == ""
with patch("urllib.request.urlopen", side_effect=AssertionError("implicit health request")) as open_url:
    missing = module._phase3_health_read({})
assert missing["hades_state"] == "SOURCE_UNAVAILABLE"
assert missing["hades_reason"] == "canonical HADES health source is not configured"
open_url.assert_not_called()


class Response:
    def __init__(self, payload: dict[str, object]):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int = -1):
        return self.payload


module.HEALTH_URL = "https://hades-health.example/health"
with patch("urllib.request.urlopen", return_value=Response({"status": True})) as open_url:
    up = module._phase3_health_read({})
assert up["hades_state"] == "UP"
assert open_url.call_args.kwargs["timeout"] == 5

with patch("urllib.request.urlopen", return_value=Response({"status": False})):
    down = module._phase3_health_read({})
assert down["hades_state"] == "DOWN"

with patch("urllib.request.urlopen", return_value=Response({"status": "ok"})):
    unknown = module._phase3_health_read({})
assert unknown["hades_state"] == "UNKNOWN"

print("PASS Phase 3 health source requires an explicit canonical endpoint and fails closed")
