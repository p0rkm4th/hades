#!/usr/bin/env python3
"""Synthetic provider catalog and residency contracts for homelab reads."""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integrations/homelab-readonly"))
# The source contract is pure; replace transport and runtime dependencies with
# inert import-time doubles, as the broader adapter contract does.
anyio = types.ModuleType("anyio")
anyio.to_thread = types.SimpleNamespace(run_sync=lambda callback: callback())
anyio.run = lambda *_args, **_kwargs: None
yaml = types.ModuleType("yaml")
yaml.safe_load = json.loads
yaml.YAMLError = ValueError

class McpValue:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class McpServer:
    def __init__(self, *_args, **_kwargs):
        pass

mcp = types.ModuleType("mcp")
mcp_server = types.ModuleType("mcp.server")
mcp_lowlevel = types.ModuleType("mcp.server.lowlevel")
mcp_lowlevel.Server = McpServer
mcp_stdio = types.ModuleType("mcp.server.stdio")
mcp_stdio.stdio_server = lambda: None
mcp_types = types.ModuleType("mcp.types")
for class_name in ("CallToolResult", "ListToolsResult", "TextContent", "Tool"):
    setattr(mcp_types, class_name, type(class_name, (McpValue,), {}))
sys.modules.update({
    "anyio": anyio, "yaml": yaml, "mcp": mcp,
    "mcp.server": mcp_server, "mcp.server.lowlevel": mcp_lowlevel,
    "mcp.server.stdio": mcp_stdio, "mcp.types": mcp_types,
})
import config
import server


def expect_invalid(value: str) -> None:
    os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = value
    try:
        config.inference_endpoint_specs()
    except ValueError:
        return
    raise AssertionError("invalid inference endpoint config was accepted")


os.environ.pop("HADES_INFERENCE_ENDPOINTS_JSON", None)
assert config.inference_endpoint_specs() == ()
expect_invalid('{"id":"x"}')
expect_invalid(json.dumps([{"id": "x", "url": "http://user:pass@example.test"}]))
expect_invalid(json.dumps([{"id": "x", "url": "http://example.test", "token_file": "/secret"}]))
expect_invalid(json.dumps([
    {"id": "x", "url": "http://example.test"},
    {"id": "x", "url": "http://other.example.test"},
]))

os.environ["HADES_INFERENCE_ENDPOINTS_JSON"] = json.dumps([
    {"id": "fast-lane", "url": "http://inference.example.test:11434"},
])
endpoint, = config.inference_endpoint_specs()
assert endpoint["provider"] == "ollama"
calls = []


def fake_fetch(url, token_file="", ca_file="", proxmox_token_id="", **kwargs):
    calls.append(url)
    assert kwargs == {"timeout_seconds": 4, "max_response_bytes": 512 * 1024}
    if url.endswith("api/tags"):
        return {"models": [{"name": "model-a:8b", "size": 8000}]}
    if url.endswith("api/ps"):
        return {"models": [{"name": "model-a:8b", "size_vram": 7000}]}
    raise AssertionError(f"unexpected provider URL: {url}")


server._fetch = fake_fetch
row = server._read_inference_endpoint(endpoint, {"inference:fast-lane": 42})
assert row["status"] == "READABLE" and row["identity_status"] == "LINKED"
assert row["netbox_device_id"] == 42
assert row["models"][0]["name"] == "model-a:8b"
assert row["loaded_models"][0]["size_vram_bytes"] == 7000
assert row["read_only"] is True and len(calls) == 2

# The adapter publishes an explicit canonical identity and obtains the host
# label from the linked NetBox object, even when conversational resources are
# compacted and omit it. Provider ID/name and IP are not used as a join.
old_specs = server.inference_endpoint_specs
old_links = server._read_identity_links
old_reader = server._read_inference_endpoint
old_fetch = server._fetch
old_netbox_url = os.environ.get("HADES_NETBOX_URL")
server.inference_endpoint_specs = lambda: [endpoint]
server._read_identity_links = lambda: {"inference:fast-lane": 42}
server._read_inference_endpoint = lambda _endpoint, _links: {
    "id": "fast-lane", "source_identity": "inference:fast-lane",
    "netbox_device_id": 42, "identity_status": "LINKED",
    "status": "READABLE", "models": [{"name": "model-a:8b"}],
    "loaded_status": "CURRENT", "loaded_models": [],
}
os.environ["HADES_NETBOX_URL"] = "https://netbox.example.test"
server._fetch = lambda url, *args, **kwargs: (
    {"id": 42, "name": "Compute Alpha"}
    if url.endswith("/api/dcim/devices/42/") else
    (_ for _ in ()).throw(AssertionError("unexpected NetBox identity lookup"))
)
resolved_inventory = server.homelab_inference_inventory()
resolved_endpoint, = resolved_inventory["endpoints"]
assert resolved_endpoint["node_identity"] == "netbox:device:42"
assert resolved_endpoint["node_name"] == "Compute Alpha"
assert server.resolve_inference_node_target(
    "fast-lane", resolved_inventory, {"resources": []},
) == ("netbox:device:42", "Compute Alpha")
linked_without_compact_row = server.format_inference_inventory_response(
    "Where should I run another model?", resolved_inventory,
    {"resources": [], "capability_machines": [{"name": "Compute Alpha", "role": "deep inference"}]},
    {"status": "READABLE", "retrieved_at": "synthetic-check-time", "endpoints": [{
        "inference_id": "fast-lane", "status": "READABLE", "devices": [{
            "index": 0, "memory_free_mib": 8000, "memory_total_mib": 16000,
            "gpu_utilization_percent": 10,
        }],
    }]},
)
assert "Responding inference endpoints: Compute Alpha" in linked_without_compact_row
assert "The largest free-memory reading" in linked_without_compact_row
assert "can't confirm where a new model will fit" in linked_without_compact_row
server.inference_endpoint_specs = old_specs
server._read_identity_links = old_links
server._read_inference_endpoint = old_reader
server._fetch = old_fetch
if old_netbox_url is None:
    os.environ.pop("HADES_NETBOX_URL", None)
else:
    os.environ["HADES_NETBOX_URL"] = old_netbox_url

server._fetch = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("synthetic unavailable"))
unavailable = server._read_inference_endpoint(endpoint, {})
assert unavailable["status"] == "UNAVAILABLE"
assert unavailable["models"] == [] and unavailable["read_only"] is True

readers = {
    "homelab_summary": lambda: {"status": "PARTIAL", "resources": []},
    "homelab_compute_capabilities": lambda: {"status": "OK", "machines": []},
    "homelab_inference_inventory": lambda: {"status": "READABLE", "endpoints": []},
    "homelab_gpu_telemetry": lambda: {"status": "UNAVAILABLE", "endpoints": []},
}
for name, reader in readers.items():
    setattr(server, name, reader)
snapshot = server.homelab_inference_capacity()
assert snapshot["status"] == "PARTIAL"
assert snapshot["summary"]["status"] == "PARTIAL"
assert snapshot["gpu_telemetry"]["status"] == "UNAVAILABLE"
assert snapshot["answer_contract"]["model_fit"].startswith("not calculated")
assert snapshot["read_only"] is True

# Owner-facing summaries use only explicit stable identity links. Provider
# labels do not become host names unless the read model links them.
inventory = {
    "status": "READABLE",
    "retrieved_at": "2026-10-04T12:00:00Z",
    "endpoints": [{
        "id": "fast-lane", "source_identity": "inference:fast-lane",
        "node_identity": "netbox:device:42", "identity_status": "LINKED",
        "status": "READABLE", "models": [{"name": "model-a:8b"}],
        "loaded_status": "CURRENT", "loaded_models": [{"name": "model-a:8b"}],
    }],
}
summary = {"resources": [{
    "identity": {"canonical_id": "netbox:device:42", "source_identities": {
        "netbox": ["netbox:device:42"],
    }},
    "inventory": {"name": "Compute Alpha"},
    "name": "Compute Alpha",
}]}
summary["capability_machines"] = [{
    "name": "Compute Alpha", "role": "deep inference", "cpu": "Synthetic CPU",
    "ram_gib": 64, "gpus": ["Quadro P4000", "Quadro P4000"],
}]
summary["capability_observed_at"] = "synthetic-matrix-time"
assert server.resolve_inference_node_target("Compute Alpha", inventory, summary) == (
    "netbox:device:42", "Compute Alpha",
)
assert server.resolve_inference_node_target("fast-lane", inventory, summary) == (
    "netbox:device:42", "Compute Alpha",
)
reconciled_summary = server.summarize(
    {"data": [{
        "id": "node/alpha", "type": "node", "node": "alpha",
        "name": "Compute Alpha", "status": "online",
        "source_identity": "proxmox:alpha:node:alpha",
    }]},
    {"results": [{"id": 42, "name": "Compute Alpha"}]},
    {"monitors": []},
    identity_links={"proxmox:alpha:node:alpha": 42},
)
assert reconciled_summary["resources"][0]["identity"]["canonical_id"] == "netbox:device:42"
assert server.resolve_inference_node_target("fast-lane", inventory, reconciled_summary) == (
    "netbox:device:42", "Compute Alpha",
)
model_location = server.format_inference_inventory_response(
    "Where's model-a:8b?", inventory, summary,
)
assert "model-a:8b is listed by Compute Alpha" in model_location, model_location
assert "Provider reports it resident on Compute Alpha" in model_location, model_location
assert "Provider catalog and residency reads completed at 2026-10-04T12:00:00Z" in model_location, model_location
assert "192.168." not in model_location and "generation" in model_location
without_read_time = {**inventory}
without_read_time.pop("retrieved_at")
untimed_model_location = server.format_inference_inventory_response(
    "Where's model-a:8b?", without_read_time, summary,
)
assert "Provider catalog and residency read time is unavailable" in untimed_model_location, untimed_model_location
partial_inventory = {
    **inventory,
    "endpoints": [*inventory["endpoints"], {
        "id": "other-lane", "source_identity": "inference:other-lane",
        "identity_status": "UNLINKED", "status": "UNAVAILABLE",
    }],
}
partial_model_location = server.format_inference_inventory_response(
    "Where's model-a:8b?", partial_inventory, summary,
)
assert "1 configured inference provider could not be checked" in partial_model_location, partial_model_location
assert "other model locations may be missing" in partial_model_location, partial_model_location
gpu_answer = server.format_inference_inventory_response(
    "Which GPUs are free?", inventory, summary, {
        "status": "READABLE", "retrieved_at": "2026-10-04T12:00:00Z",
        "endpoints": [{"inference_id": "fast-lane", "status": "READABLE",
                       "devices": [{"index": 0, "memory_free_mib": 8000,
                                    "memory_total_mib": 16000,
                                    "gpu_utilization_percent": 25}]}],
    },
)
assert "Compute Alpha GPU 0: 8000 MiB free" in gpu_answer, gpu_answer
assert "doesn't guarantee a model will fit" in gpu_answer
linked_hardware = {
    "status": "READABLE", "endpoints": [{
        "id": "fast-lane", "source_identity": "inference:fast-lane",
        "node_identity": "netbox:device:42", "identity_status": "LINKED",
        "status": "READABLE", "checked_at": "synthetic-provider-time",
    }],
}
linked_telemetry = {
    "status": "READABLE", "retrieved_at": "synthetic-gpu-time",
    "endpoints": [{
        "inference_id": "fast-lane", "status": "READABLE",
        "retrieved_at": "synthetic-endpoint-time",
        "devices": [{
            "index": index, "name": "Quadro P4000", "memory_total_mib": 8192,
            "memory_free_mib": 4096, "gpu_utilization_percent": 0,
        } for index in range(4)],
    }],
}
p4000_answer = server.format_gpu_hardware_target_response(
    "Which server has the 4 P4000s?", linked_hardware, summary, linked_telemetry,
)
assert "Compute Alpha with 4 Quadro P4000 GPUs" in p4000_answer, p4000_answer
assert "synthetic-endpoint-time" in p4000_answer, p4000_answer
big_gpu_answer = server.format_gpu_hardware_target_response(
    "What's the big GPU box?", linked_hardware, summary, linked_telemetry,
)
assert "Compute Alpha: 4 GPUs" in big_gpu_answer, big_gpu_answer
assert "across separate devices, not one shared pool" in big_gpu_answer, big_gpu_answer
assert "not proof that a workload completed" in big_gpu_answer, big_gpu_answer
node_activity_answer = server.format_inference_inventory_response(
    "What's Compute Alpha doing?", linked_hardware, summary, linked_telemetry,
)
assert "Recorded hardware inventory (synthetic-matrix-time)" in node_activity_answer, node_activity_answer
assert "role: deep inference" in node_activity_answer and "RAM: 64 GiB" in node_activity_answer
assert "historical/observed context, not a live host measurement" in node_activity_answer
assert "Live host GPU sample (synthetic-endpoint-time)" in node_activity_answer, node_activity_answer
assert "Provider API read at synthetic-provider-time" in node_activity_answer
assert "does not establish overall host or service health" in node_activity_answer
assert "point-in-time per-device GPU utilization" in node_activity_answer
assert "host CPU load and sustained utilization are not measured" in node_activity_answer
assert "does not measure host CPU/GPU utilization" not in node_activity_answer
without_utilization = dict(linked_telemetry, endpoints=[dict(
    linked_telemetry["endpoints"][0], devices=[{
        "index": 0, "name": "Quadro P4000", "memory_total_mib": 8192,
        "memory_free_mib": 4096,
    }],
)])
no_utilization_answer = server.format_inference_inventory_response(
    "What's Compute Alpha doing?", linked_hardware, summary, without_utilization,
)
assert "does not include per-device GPU utilization" in no_utilization_answer
ambiguous_capabilities = dict(summary, capability_machines=[
    summary["capability_machines"][0], dict(summary["capability_machines"][0]),
])
ambiguous_node_answer = server.format_inference_inventory_response(
    "What's Compute Alpha doing?", linked_hardware, ambiguous_capabilities, linked_telemetry,
)
assert "Recorded hardware inventory" not in ambiguous_node_answer, ambiguous_node_answer
incomplete_gpu = dict(linked_telemetry, status="PARTIAL")
incomplete_answer = server.format_gpu_hardware_target_response(
    "Which server has a P4000?", linked_hardware, summary, incomplete_gpu,
)
assert "sources or identity links are incomplete" in incomplete_answer, incomplete_answer
unlinked = dict(inventory, endpoints=[dict(
    inventory["endpoints"][0], node_identity=None, identity_status="UNLINKED",
    source_identity="inference:provider-blue",
)])
unlinked_answer = server.format_inference_inventory_response(
    "Where's model-a:8b?", unlinked, {},
)
assert "can't verify which physical machine" in unlinked_answer, unlinked_answer
placement_answer = server.format_inference_inventory_response(
    "Can this handle a 20 GB model?", inventory, summary,
)
assert "can't rank a host" in placement_answer, placement_answer
assert "can't confirm capacity or fit" in placement_answer

print("PASS inference configuration, identity links, provider freshness boundary, and outages")
print("PASS model locations and GPU samples require stable host links and avoid fit claims")
