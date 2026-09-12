"""Small stdio MCP adapter for bounded Agent Zero delegation.

Agent Zero remains a subordinate operator. This adapter exposes one explicit
delegation tool and forwards only a bounded text task to Agent Zero's
documented external API.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


BASE_URL = os.environ.get("AGENT_ZERO_URL", "http://127.0.0.1:7002").rstrip("/")
API_KEY = os.environ.get("AGENT_ZERO_API_KEY", "")
MAX_TASK_CHARS = int(os.environ.get("AGENT_ZERO_MAX_TASK_CHARS", "2000"))
TIMEOUT_SECONDS = float(os.environ.get("AGENT_ZERO_TIMEOUT_SECONDS", "90"))

mcp = FastMCP("hades-agent-zero")


@mcp.tool()
async def agent_zero_delegate(task: str, context_id: str = "") -> dict[str, Any]:
    """Run one harmless, bounded task through the private Agent Zero operator."""
    if not API_KEY:
        return {"ok": False, "error": "Agent Zero delegation is not configured."}
    task = str(task or "").strip()
    if not task:
        return {"ok": False, "error": "A non-empty task is required."}
    if len(task) > MAX_TASK_CHARS:
        return {
            "ok": False,
            "error": f"Task exceeds the {MAX_TASK_CHARS}-character delegation limit.",
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
    if context_id.strip():
        payload["context_id"] = context_id.strip()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{BASE_URL}/api/api_message",
                headers={"X-API-KEY": API_KEY},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Agent Zero request failed: {exc}"}
    except ValueError:
        return {"ok": False, "error": "Agent Zero returned invalid JSON."}

    return {
        "ok": True,
        "context_id": result.get("context_id", ""),
        "response": result.get("response", ""),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
