"""Small stdio MCP adapter for bounded Agent Zero delegation.

Agent Zero remains a subordinate operator. This adapter exposes one explicit
delegation tool and forwards only a bounded text task to Agent Zero's
documented external API.
"""

from __future__ import annotations

import os
import json
import re
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
UNSAFE_TASK_PATTERN = re.compile(
    r"(?:\b(?:sudo|ssh|shell|exec(?:ute)?|restart|reboot|shutdown|power\s*off|poweroff|"
    r"stop|start|kill|delete|remove|destroy|modify|write|deploy|install|uninstall|upgrade|"
    r"configure|command|terminal|nmap|curl|wget|chmod|chown|iptables|mount|"
    r"proxmox|netbox|finance|credential|password|secret|token|docker)\b|"
    r"\bupdate\s+(?:the\s+)?(?:host|system|service|config(?:uration)?|package|container|database|network)\b|"
    r"\b(?:network|port)\s+scan\b|/var/run/docker\.sock)",
    re.IGNORECASE,
)


async def _delegate(task: str, context_id: str = "") -> dict[str, Any]:
    """Run one harmless, bounded task through the private Agent Zero operator."""
    if not API_KEY:
        return {"ok": False, "outcome": "FAILED", "error": "Agent Zero delegation is not configured."}
    if not isinstance(task, str):
        return {"ok": False, "outcome": "FAILED", "error": "Task must be a string."}
    task = task.strip()
    if not task:
        return {"ok": False, "outcome": "FAILED", "error": "A non-empty task is required."}
    if len(task) > MAX_TASK_CHARS:
        return {"ok": False, "outcome": "FAILED", "error": f"Task exceeds the {MAX_TASK_CHARS}-character delegation limit."}
    if UNSAFE_TASK_PATTERN.search(task):
        return {
            "ok": False,
            "outcome": "FAILED",
            "error": "Task requests infrastructure, credentials, or a write-capable operation outside the bounded operator surface.",
        }

    payload: dict[str, Any] = {
        "message": (
            "You are a bounded subordinate operator for HADES. "
            "Perform only this harmless task and report evidence; do not "
            "modify host systems, infrastructure, finance, credentials, or "
            "HADES administration. Task: " + task
        ),
        "lifetime_hours": 1,
    }
    if not isinstance(context_id, str):
        return {"ok": False, "outcome": "FAILED", "error": "Context ID must be a string."}
    context_id = context_id.strip()
    if len(context_id) > MAX_CONTEXT_ID_CHARS:
        return {
            "ok": False,
            "outcome": "FAILED",
            "error": f"Context ID exceeds the {MAX_CONTEXT_ID_CHARS}-character delegation limit.",
        }
    if context_id:
        payload["context_id"] = context_id

    request_attempted = False
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            request_attempted = True
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
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if isinstance(status_code, int) and 400 <= status_code < 500:
            return {
                "ok": False,
                "outcome": "FAILED",
                "error": "Agent Zero rejected the bounded delegation request.",
            }
        if request_attempted and exc.__class__.__name__ != "ConnectError":
            return {
                "ok": False,
                "outcome": "OUTCOME UNKNOWN",
                "error": "Agent Zero request was attempted but its outcome is unknown.",
            }
        return {"ok": False, "outcome": "FAILED", "error": "Agent Zero could not be reached before delegation."}
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
    returned_context_id = result.get("context_id", "")
    if returned_context_id is None:
        returned_context_id = ""
    if not isinstance(returned_context_id, str) or len(returned_context_id) > MAX_CONTEXT_ID_CHARS:
        return {
            "ok": False,
            "outcome": "OUTCOME UNKNOWN",
            "error": "Agent Zero returned an invalid or oversized context ID; task outcome is unknown.",
        }

    return {
        "ok": True,
        "outcome": "SUCCEEDED",
        "context_id": returned_context_id,
        "response": response_text,
    }


async def list_tools():
    return ListToolsResult(tools=[Tool(
        name=TOOL_NAME,
        description=(
            "Delegate one harmless, bounded, read-only task to the private "
            "Agent Zero operator. Never include credentials, secrets, or a "
            "request to modify hosts, infrastructure, finance, or HADES. "
            "A timeout or invalid result is OUTCOME UNKNOWN, not success."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_TASK_CHARS,
                    "description": "Harmless read-only task; do not request writes or secrets.",
                },
                "context_id": {
                    "type": "string",
                    "maxLength": MAX_CONTEXT_ID_CHARS,
                    "description": "Optional bounded continuation identifier.",
                },
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
