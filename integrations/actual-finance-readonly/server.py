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

from mcp.server.fastmcp import FastMCP


HELPER = os.environ.get("ACTUAL_READONLY_HELPER", "actual_client.js")
TIMEOUT_SECONDS = float(os.environ.get("ACTUAL_READONLY_TIMEOUT_SECONDS", "30"))
MAX_TRANSACTIONS = int(os.environ.get("ACTUAL_READONLY_MAX_TRANSACTIONS", "250"))

mcp = FastMCP("hades-actual-finance-readonly")


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


@mcp.tool()
def finance_accounts() -> dict[str, Any]:
    """List canonical Actual Budget accounts and their current balances."""
    return _call("accounts")


@mcp.tool()
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


@mcp.tool()
def finance_status() -> dict[str, Any]:
    """Report the selected budget, server version, and read freshness metadata."""
    return _call("status")


if __name__ == "__main__":
    mcp.run(transport="stdio")
