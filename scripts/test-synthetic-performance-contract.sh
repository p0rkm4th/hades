#!/usr/bin/env bash
set -euo pipefail

# Dependency-free contract for the timing harness. It validates attribution
# fields with a model stub; it is not a latency or model-quality claim.
python3 - <<'PY'
import importlib.util
from pathlib import Path

path = Path("scripts/test-synthetic-performance.py")
spec = importlib.util.spec_from_file_location("synthetic_performance", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fake_model_call(messages):
    if any(message.get("role") == "tool" for message in messages):
        return {"message": {"content": "done"}}, 1.2
    prompt = str(messages[-1].get("content", ""))
    if "online" in prompt:
        return {"message": {"tool_calls": [{
            "id": "synthetic-call",
            "function": {"name": "web_search", "arguments": '{"query":"pasta"}'},
        }]}}, 1.5
    return {"message": {"content": "hello"}}, 0.5

module.model_call = fake_model_call
plain = module.run("contract_plain", "Say hello.", [])
assert plain["time_to_tool_ms"] is None
assert plain["tool_timings"] == []
assert plain["total_ms"] >= 0

tool = module.run("contract_tool", "Find a recipe online.", ["web_search"])
assert tool["time_to_tool_ms"] == 1.5
assert tool["tool_timings"] == [{"tool": "web_search", "tool_ms": 0.0}]
assert tool["continuation_ms"] == 1.2
assert tool["total_ms"] >= 0
print("PASS synthetic performance attribution contract")
PY
