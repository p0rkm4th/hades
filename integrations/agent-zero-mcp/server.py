"""Small stdio MCP adapter for bounded Agent Zero delegation.

Agent Zero remains a subordinate operator. This adapter exposes one explicit
delegation tool and forwards only a bounded text task to Agent Zero's
documented external API.
"""

from __future__ import annotations

import os
import json
from typing import Any

import httpx
import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


BASE_URL = os.environ.get("AGENT_ZERO_URL", "http://127.0.0.1:7002").rstrip("/")
API_KEY = os.environ.get("AGENT_ZERO_API_KEY", "")
MAX_TASK_CHARS = int(os.environ.get("AGENT_ZERO_MAX_TASK_CHARS", "2000"))
MAX_RESPONSE_CHARS = int(os.environ.get("AGENT_ZERO_MAX_RESPONSE_CHARS", "4000"))
MAX_CONTEXT_ID_CHARS = int(os.environ.get("AGENT_ZERO_MAX_CONTEXT_ID_CHARS", "128"))
TIMEOUT_SECONDS = float(os.environ.get("AGENT_ZERO_TIMEOUT_SECONDS", "90"))

TOOL_NAME = "agent_zero_delegate"


async def _delegate(task: str, context_id: str = "") -> dict[str, Any]:
    """Run one harmless, bounded task through the private Agent Zero operator."""
    if not API_KEY:
        return {"ok": False, "outcome": "FAILED", "error": "Agent Zero delegation is not configured."}
    task = str(task or "").strip()
    if not task:
        return {"ok": False, "outcome": "FAILED", "error": "A non-empty task is required."}
    if len(task) > MAX_TASK_CHARS:
        return {"ok": False, "outcome": "FAILED", "error": f"Task exceeds the {MAX_TASK_CHARS}-character delegation limit."}

    payload: dict[str, Any] = {
        "message": (
            "You are a bounded subordinate operator for HADES. "
            "Perform only this harmless task and report evidence; do not "
            "modify host systems, infrastructure, finance, credentials, or "
            "HADES administration. Task: " + task
        ),
        "lifetime_hours": 1,
    }
    context_id = str(context_id or "").strip()
    if len(context_id) > MAX_CONTEXT_ID_CHARS:
        return {
            "ok": False,
            "outcome": "FAILED",
            "error": f"Context ID exceeds the {MAX_CONTEXT_ID_CHARS}-character delegation limit.",
        }
    if context_id:
        payload["context_id"] = context_id

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{BASE_URL}/api/api_message",
                headers={"X-API-KEY": API_KEY},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.TimeoutException:
        return {
            "ok": False,
            "outcome": "OUTCOME UNKNOWN",
            "error": "Agent Zero delegation timed out; task outcome is unknown.",
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "outcome": "FAILED", "error": f"Agent Zero request failed: {exc}"}
    except ValueError:
        return {
            "ok": False,
            "outcome": "OUTCOME UNKNOWN",
            "error": "Agent Zero returned invalid JSON; task outcome is unknown.",
        }

    if not isinstance(result, dict):
        return {
            "ok": False,
            "outcome": "OUTCOME UNKNOWN",
            "error": "Agent Zero returned an invalid result; task outcome is unknown.",
        }
    response_text = result.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        return {
            "ok": False,
            "outcome": "OUTCOME UNKNOWN",
            "error": "Agent Zero returned no usable result; task outcome is unknown.",
        }
    if len(response_text) > MAX_RESPONSE_CHARS:
        return {
            "ok": False,
            "outcome": "OUTCOME UNKNOWN",
            "error": f"Agent Zero result exceeds the {MAX_RESPONSE_CHARS}-character response limit.",
        }

    return {
        "ok": True,
        "outcome": "SUCCEEDED",
        "context_id": str(result.get("context_id", "") or ""),
        "response": response_text,
    }


async def list_tools():
    return ListToolsResult(tools=[Tool(
        name=TOOL_NAME,
        description="Run one harmless, bounded task through the private Agent Zero operator.",
        inputSchema={
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "context_id": {"type": "string"},
            },
            "required": ["task"],
        },
    )])


async def call_tool(tool_name, args):
    if tool_name != TOOL_NAME:
        raise ValueError(f"unknown tool: {tool_name}")
    args = args or {}
    result = await _delegate(
        args.get("task", ""),
        args.get("context_id", ""),
    )
    return CallToolResult(content=[TextContent(
        type="text", text=json.dumps(result, sort_keys=True)
    )])


async def main():
    server = Server("hades-agent-zero")
    server.list_tools()(list_tools)
    server.call_tool()(call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
