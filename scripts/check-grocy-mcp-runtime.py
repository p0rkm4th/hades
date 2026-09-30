#!/usr/bin/env python3
"""Read-only readiness probe for the installed Grocy MCP child and API."""

from __future__ import annotations

import asyncio
import os
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


EXPECTED_TOOLS = {
    "stock_overview_tool",
    "stock_product_info_tool",
    "stock_consume_tool",
    "shopping_list_view_tool",
    "shopping_list_add_tool",
    "shopping_list_remove_tool",
    "workflow_match_products_preview_tool",
    "workflow_stock_intake_preview_tool",
    "workflow_stock_intake_apply_tool",
    "recipe_fulfillment_tool",
    "recipe_add_to_shopping_tool",
    "recipes_list_tool",
    "recipe_details_tool",
    "recipe_create_by_name_tool",
    "recipe_update_tool",
    "recipe_add_ingredient_tool",
    "recipe_remove_ingredient_tool",
}


async def check() -> int:
    launcher = os.environ["HADES_GROCY_MCP_LAUNCHER"]
    env = os.environ.copy()
    env["GROCY_API_KEY_FILE"] = os.environ["HADES_GROCY_RUNTIME_API_KEY_FILE"]
    env["GROCY_URL"] = os.environ["HADES_GROCY_URL"]
    transport = StdioTransport(command=sys.executable, args=[launcher], env=env)
    async with Client(transport) as client:
        result = await asyncio.wait_for(client.list_tools(), timeout=10)
        found = {tool.name for tool in result}
        if not EXPECTED_TOOLS.issubset(found):
            print("FAIL Grocy MCP is missing a required canonical household tool")
            return 1
        # A real read catches an invalid API key, an uninitialized Grocy
        # database, and broken API connectivity. Never print household data.
        stock = await asyncio.wait_for(
            client.call_tool("stock_overview_tool", {}, raise_on_error=False),
            timeout=15,
        )
        if stock.is_error:
            print("FAIL Grocy MCP read-only stock check returned an error")
            return 1
    print(f"PASS Grocy MCP initialize/list-tools/read ({len(found)} upstream tools; HADES allowlist is separate)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(check()))
    except Exception as error:
        print(f"FAIL Grocy MCP initialize/list-tools/read ({type(error).__name__})", file=sys.stderr)
        raise SystemExit(1)
