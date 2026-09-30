"""MCP surface for owner-confirmed, bounded Proxmox control."""

from __future__ import annotations

import json

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from control import inspect_templates, list_managed_guests, manage_guest, provision_guest


TOOLS = [
    Tool(
        name="homelab_control_templates",
        description=(
            "List the explicitly approved server templates and target nodes. "
            "This is informational and performs no writes. Never invent a "
            "template that is not returned here."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="homelab_provision_guest",
        description=(
            "Owner-only operation: clone an approved server template to an "
            "exact Proxmox node/VMID, apply bounded CPU/RAM/disk settings, "
            "start it, and read Proxmox back. The caller must obtain explicit "
            "confirmation immediately before using owner_confirmed=true. "
            "This is not a shell and cannot execute arbitrary commands."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "template": {"type": "string"},
                "target": {
                    "type": "object",
                    "properties": {"node": {"type": "string"}, "vmid": {"type": "integer"}},
                    "required": ["node"],
                    "additionalProperties": False,
                },
                "name": {"type": "string"},
                "cores": {"type": "integer", "minimum": 1, "maximum": 16},
                "memory_mib": {"type": "integer", "minimum": 512, "maximum": 32768},
                "disk_gib": {"type": "integer", "minimum": 0, "maximum": 500},
                "owner_confirmed": {"type": "boolean"},
            },
            "required": ["template", "target", "name", "owner_confirmed"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="homelab_managed_guests",
        description=(
            "Owner-only informational view of HADES-managed self-service guests. "
            "Returns only guests in the approved pool and VMID range; no writes."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="homelab_manage_guest",
        description=(
            "Owner-only bounded action on an HADES-managed self-service guest. "
            "Allowed actions are status, start, stop, restart, and delete. "
            "The target must be an approved node plus a managed VMID; this is "
            "not raw Proxmox administration. Stop, restart, and delete require "
            "explicit confirmation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "type": "object",
                    "properties": {"node": {"type": "string"}, "vmid": {"type": "integer"}},
                    "required": ["node", "vmid"],
                    "additionalProperties": False,
                },
                "action": {"type": "string", "enum": ["status", "start", "stop", "restart", "delete"]},
                "owner_confirmed": {"type": "boolean"},
            },
            "required": ["target", "action", "owner_confirmed"],
            "additionalProperties": False,
        },
    ),
]


async def list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        if name == "homelab_control_templates":
            result = inspect_templates()
        elif name == "homelab_managed_guests":
            result = list_managed_guests()
        elif name == "homelab_provision_guest":
            result = provision_guest(
                arguments.get("template", ""),
                arguments.get("target", {}),
                name=arguments.get("name", ""),
                cores=arguments.get("cores", 4),
                memory_mib=arguments.get("memory_mib", 8192),
                disk_gib=arguments.get("disk_gib", 0),
                owner_confirmed=arguments.get("owner_confirmed") is True,
            )
        elif name == "homelab_manage_guest":
            result = manage_guest(
                arguments.get("target", {}),
                arguments.get("action", ""),
                owner_confirmed=arguments.get("owner_confirmed") is True,
            )
        else:
            result = {"status": "FAILED", "error": "unknown control tool"}
    except Exception as exc:
        result = {"status": "FAILED", "error": str(exc), "writes_performed": False}
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def _list_tools(_context, _params):
    return await list_tools()


async def _call_tool(_context, params):
    return await call_tool(params.name, params.arguments)


async def main() -> None:
    server = Server("hades-homelab-control", on_list_tools=_list_tools, on_call_tool=_call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
