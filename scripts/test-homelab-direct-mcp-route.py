#!/usr/bin/env python3
"""Verify deterministic homelab answers call the configured Hermes MCP tool."""
from __future__ import annotations

import ast
import json
import logging
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "hermes/sitecustomize.py").read_text(encoding="utf-8")
tree = ast.parse(source)
helper = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_hades_direct_homelab_tool_result"
)


class FakeRegistry:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_entry(self, name):
        return object() if name == "mcp__homelab_readonly__homelab_summary" else None

    def dispatch(self, name, arguments):
        self.calls.append((name, arguments))
        return self.response


def invoke(response):
    fake = FakeRegistry(response)
    tools = types.ModuleType("tools")
    tools.__path__ = []
    registry_module = types.ModuleType("tools.registry")
    registry_module.registry = fake
    previous = {name: sys.modules.get(name) for name in ("tools", "tools.registry")}
    sys.modules["tools"] = tools
    sys.modules["tools.registry"] = registry_module
    namespace = {"json": json, "_hades_logger": logging.getLogger("test.homelab")}
    try:
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "sitecustomize.py", "exec"), namespace)
        result = namespace[helper.name]("homelab_summary")
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return result, fake


payload = {"status": "OK", "source_counts": {"proxmox_runtime_rows": 2}, "resources": []}
result, registry = invoke(json.dumps({"result": json.dumps(payload)}))
assert result == payload, result
assert registry.calls == [("mcp__homelab_readonly__homelab_summary", {})]

result, _ = invoke(json.dumps({"error": "permission denied: /private/token.path"}))
assert result["status"] == "SOURCE_UNAVAILABLE"
assert "/private" not in json.dumps(result) and "token.path" not in json.dumps(result)

result, _ = invoke(json.dumps({"result": json.dumps({"status": "PARTIAL", "errors": ["Permission denied: /private/token"]})}))
assert result["errors"] == ["A configured homelab source could not be read."]

print("PASS deterministic homelab reads use the MCP registry, decode bounded results, and redact secret paths")
