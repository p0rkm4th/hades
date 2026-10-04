#!/usr/bin/env python3
"""Verify direct homelab reads dispatch through the MCP child environment."""
from __future__ import annotations

import ast
import json
import sys
import time
import types
from pathlib import Path

source = Path('hermes/sitecustomize.py').read_text(encoding='utf-8')
tree = ast.parse(source)
node = next(
    item for item in tree.body
    if isinstance(item, ast.FunctionDef) and item.name == '_hades_direct_homelab_tool_result'
)

class Registry:
    def __init__(self):
        self.ready = False
        self.dispatched = []

    def get_entry(self, name):
        return object() if self.ready and name == 'mcp__homelab_readonly__homelab_gpu_telemetry' else None

    def dispatch(self, name, arguments):
        self.dispatched.append((name, arguments))
        payload = json.dumps({'status': 'READABLE', 'retrieved_at': 'synthetic', 'endpoints': []})
        return json.dumps({'result': payload})

registry = Registry()
package = types.ModuleType('tools')
package.__path__ = []
registry_module = types.ModuleType('tools.registry')
registry_module.registry = registry
discovery_module = types.ModuleType('tools.mcp_tool_discovery')

def discover(toolsets):
    assert toolsets == ['homelab-readonly']
    registry.ready = True

discovery_module.discover_mcp_tools = discover
sys.modules['tools'] = package
sys.modules['tools.registry'] = registry_module
sys.modules['tools.mcp_tool_discovery'] = discovery_module

class Logger:
    def info(self, *_args, **_kwargs):
        pass
    def warning(self, *_args, **_kwargs):
        pass

namespace = {'json': json, 'time': time, '_hades_logger': Logger()}
exec(compile(ast.Module(body=[node], type_ignores=[]), 'sitecustomize.py', 'exec'), namespace)
result = namespace['_hades_direct_homelab_tool_result']('homelab_gpu_telemetry')
assert result == {'status': 'READABLE', 'retrieved_at': 'synthetic', 'endpoints': []}, result
assert registry.dispatched == [('mcp__homelab_readonly__homelab_gpu_telemetry', {})], registry.dispatched
assert namespace['_hades_direct_homelab_tool_result']('unknown') == {
    'status': 'UNKNOWN', 'errors': ['Unsupported homelab read request.']
}
print('PASS direct homelab reads preserve MCP child configuration and bounded result decoding')
