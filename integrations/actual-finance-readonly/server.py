"""Read-only MCP boundary for a locally hosted Actual Budget instance.

The adapter intentionally exposes only finance reads.  It delegates the
official Actual Node client to a small helper because Actual does not publish a
REST API for budget data.  No arbitrary client method or mutation is reachable
through MCP.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


HELPER = os.environ.get("ACTUAL_READONLY_HELPER", "actual_client.js")
TIMEOUT_SECONDS = float(os.environ.get("ACTUAL_READONLY_TIMEOUT_SECONDS", "30"))
MAX_TRANSACTIONS = int(os.environ.get("ACTUAL_READONLY_MAX_TRANSACTIONS", "250"))

TOOLS = [
    Tool(
        name="finance_accounts",
        description="List canonical Actual Budget accounts and current balances.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="finance_transactions",
        description="Read canonical transactions for an ISO date range.",
        inputSchema={
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "account": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_TRANSACTIONS},
            },
            "required": ["start_date", "end_date"],
        },
    ),
    Tool(
        name="finance_status",
        description="Report Actual Budget version and read freshness metadata.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


def _call(action: str, **kwargs: Any) -> dict[str, Any]:
    request = {"action": action, **kwargs}
    try:
        completed = subprocess.run(
            ["node", HELPER],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "error": "Actual Budget read request timed out or could not start."}

    if completed.returncode != 0:
        return {"ok": False, "error": "Actual Budget read request failed."}
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Actual Budget returned invalid read data."}
    return result if isinstance(result, dict) else {"ok": False, "error": "Invalid read result."}


def finance_accounts() -> dict[str, Any]:
    """List canonical Actual Budget accounts and their current balances."""
    return _call("accounts")


def finance_transactions(
    start_date: str,
    end_date: str,
    account: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    """Read canonical transactions for an ISO date range; never mutates data."""
    bounded_limit = max(1, min(int(limit), MAX_TRANSACTIONS))
    return _call(
        "transactions",
        startDate=str(start_date),
        endDate=str(end_date),
        account=str(account or ""),
        limit=bounded_limit,
    )


def finance_status() -> dict[str, Any]:
    """Report the selected budget, server version, and read freshness metadata."""
    return _call("status")


async def list_tools(_ctx, _params):
    return ListToolsResult(tools=TOOLS)


async def call_tool(_ctx, params):
    args = params.arguments or {}
    if params.name == "finance_accounts":
        result = finance_accounts()
    elif params.name == "finance_transactions":
        result = finance_transactions(
            args.get("start_date", ""), args.get("end_date", ""),
            args.get("account", ""), args.get("limit", 100),
        )
    elif params.name == "finance_status":
        result = finance_status()
    else:
        raise ValueError(f"unknown tool: {params.name}")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def main():
    server = Server("hades-actual-finance-readonly", on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
