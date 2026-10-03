#!/usr/bin/env python3
"""Verify deterministic homelab answers call the configured Hermes MCP tool."""
from __future__ import annotations

import ast
import json
import logging
import os
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source_path = Path(os.environ.get(
    "HADES_SITE_CUSTOMIZE_SOURCE", str(ROOT / "hermes/sitecustomize.py"),
)).resolve()
source = source_path.read_text(encoding="utf-8")
tree = ast.parse(source)
helper = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_direct_homelab_tool_result"
)
direct_read = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_direct_homelab_read"
)
direct_read_source = ast.unparse(direct_read)
assert "module.resolve_inference_node_labels" not in direct_read_source
assert "homelab_owner_snapshot" in ast.unparse(helper)
assert any(
    isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "_hades_direct_homelab_tool_result"
    and len(node.args) == 1
    and isinstance(node.args[0], ast.Constant)
    and node.args[0].value == "homelab_summary"
    for node in ast.walk(direct_read)
)


class FakeRegistry:
    def __init__(self, response, *, tool_name="homelab_summary", registered=True):
        self.response = response
        self.registered = registered
        self.registered_name = f"mcp__homelab_readonly__{tool_name}"
        self.calls = []

    def get_entry(self, name):
        return object() if self.registered and name == self.registered_name else None

    def dispatch(self, name, arguments):
        self.calls.append((name, arguments))
        return self.response


def invoke(response, *, tool_name="homelab_summary", arguments=None, registered=True, discovery_register=False):
    fake = FakeRegistry(response, tool_name=tool_name, registered=registered)
    discovery_calls = []
    tools = types.ModuleType("tools")
    tools.__path__ = []
    registry_module = types.ModuleType("tools.registry")
    registry_module.registry = fake
    discovery_module = types.ModuleType("tools.mcp_tool_discovery")

    def discover_mcp_tools(allowed):
        discovery_calls.append(list(allowed))
        if discovery_register:
            fake.registered = True
        return [fake.registered_name] if discovery_register else []

    discovery_module.discover_mcp_tools = discover_mcp_tools
    previous = {
        name: sys.modules.get(name)
        for name in ("tools", "tools.registry", "tools.mcp_tool_discovery")
    }
    sys.modules["tools"] = tools
    sys.modules["tools.registry"] = registry_module
    sys.modules["tools.mcp_tool_discovery"] = discovery_module
    namespace = {"json": json, "time": time, "_hades_logger": logging.getLogger("test.homelab")}
    try:
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
        result = namespace[helper.name](tool_name, arguments)
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return result, fake, discovery_calls


payload = {"status": "OK", "source_counts": {"proxmox_runtime_rows": 2}, "resources": []}
snapshot_payload = {"status": "PARTIAL", "summary": payload, "compute": {"status": "OK", "machines": []}}
snapshot, registry, _ = invoke(
    json.dumps({"result": json.dumps(snapshot_payload)}),
    tool_name="homelab_owner_snapshot",
)
assert snapshot == snapshot_payload
assert registry.calls == [("mcp__homelab_readonly__homelab_owner_snapshot", {})]
result, registry, discovery_calls = invoke(json.dumps({"result": json.dumps(payload)}))
assert result == payload, result
assert registry.calls == [("mcp__homelab_readonly__homelab_summary", {})]
assert discovery_calls == []

activity_payload = {"status": "READABLE", "endpoints": [{"events": []}]}
activity, registry, discovery_calls = invoke(
    json.dumps({"result": json.dumps(activity_payload)}),
    tool_name="homelab_recent_activity",
    arguments={"window_hours": 168},
)
assert activity == activity_payload
assert registry.calls == [(
    "mcp__homelab_readonly__homelab_recent_activity", {"window_hours": 168}
)]
assert discovery_calls == []

result, _, _ = invoke(json.dumps({"error": "permission denied: /private/token.path"}))
assert result["status"] == "SOURCE_UNAVAILABLE"
assert "/private" not in json.dumps(result) and "token.path" not in json.dumps(result)

result, _, _ = invoke(json.dumps({"result": json.dumps({"status": "PARTIAL", "errors": ["Permission denied: /private/token"]})}))
assert result["errors"] == ["A configured homelab source could not be read."]

result, registry, discovery_calls = invoke(
    json.dumps({"result": json.dumps(payload)}), registered=False, discovery_register=True,
)
assert result == payload
assert registry.calls == [("mcp__homelab_readonly__homelab_summary", {})]
assert discovery_calls == [["homelab-readonly"]]

result, registry, discovery_calls = invoke(None, registered=False)
assert result["status"] == "NOT_CONFIGURED"
assert result["sources"][0]["status"] == "NOT_CONFIGURED"
assert discovery_calls == [["homelab-readonly"]]
assert registry.calls == []

print("PASS deterministic homelab reads discover only the configured MCP when needed, dispatch bounded results, and fail closed")
