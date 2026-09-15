"""Narrow MCP adapter for the Grocy recipe serving-count field.

The selected upstream Grocy MCP exposes recipe name/description updates but
omits Grocy's ``base_servings`` field.  This adapter adds only the missing
canonical operation; it does not keep recipe state locally or expose generic
Grocy object mutation.
"""

from __future__ import annotations

import json
import os
from typing import Any

import anyio
import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


BASE_URL = os.environ.get("GROCY_URL", "http://127.0.0.1:7003").rstrip("/")
API_KEY = os.environ.get("GROCY_API_KEY", "")
TIMEOUT_SECONDS = float(os.environ.get("GROCY_RECIPE_TIMEOUT_SECONDS", "15"))
MAX_SERVINGS = int(os.environ.get("GROCY_MAX_SERVINGS", "1000"))
TOOL_NAME = "recipe_set_servings"


def _result(outcome: str, **fields: Any) -> dict[str, Any]:
    return {"ok": outcome == "SUCCEEDED", "outcome": outcome, **fields}


async def _get_recipe(client: httpx.AsyncClient, recipe: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve one recipe by numeric ID or an exact unique name."""
    if str(recipe).strip().isdigit():
        response = await client.get(f"{BASE_URL}/api/objects/recipes/{int(str(recipe).strip())}")
        if response.status_code == 404:
            return None, _result("FAILED", error="Recipe was not found.")
        response.raise_for_status()
        value = response.json()
        return (value if isinstance(value, dict) else None), None

    response = await client.get(f"{BASE_URL}/api/objects/recipes")
    response.raise_for_status()
    recipes = response.json()
    matches = [r for r in recipes if isinstance(r, dict) and r.get("name") == str(recipe).strip()]
    if not matches:
        return None, _result("FAILED", error="Recipe was not found.")
    if len(matches) > 1:
        return None, _result("FAILED", error="Recipe name is ambiguous; use its numeric ID.")
    return matches[0], None


async def set_servings(recipe: str, servings: int) -> dict[str, Any]:
    """Set and canonically verify a recipe's base serving count."""
    if not API_KEY:
        return _result("FAILED", error="Grocy recipe authoring is not configured.")
    recipe_text = str(recipe or "").strip()
    if not recipe_text:
        return _result("FAILED", error="A recipe name or numeric ID is required.")
    if isinstance(servings, bool) or not isinstance(servings, int):
        return _result("FAILED", error="Servings must be a positive integer.")
    value = servings
    if value < 1 or value > MAX_SERVINGS:
        return _result("FAILED", error=f"Servings must be between 1 and {MAX_SERVINGS}.")

    headers = {"GROCY-API-KEY": API_KEY}
    mutation_attempted = False
    mutation_response_received = False
    try:
        async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT_SECONDS) as client:
            found, error = await _get_recipe(client, recipe_text)
            if error:
                return error
            recipe_id = int(found["id"])
            # Once the PUT is attempted, a later transport or decode failure
            # cannot prove that Grocy rejected the mutation.
            mutation_attempted = True
            response = await client.put(
                f"{BASE_URL}/api/objects/recipes/{recipe_id}",
                json={"base_servings": value},
            )
            mutation_response_received = True
            response.raise_for_status()
            verified = await client.get(f"{BASE_URL}/api/objects/recipes/{recipe_id}")
            verified.raise_for_status()
            current = verified.json()
            if not isinstance(current, dict) or int(current.get("base_servings", 0)) != value:
                return _result("OUTCOME UNKNOWN", error="Grocy did not confirm the requested serving count.")
            return _result("SUCCEEDED", recipe_id=recipe_id, base_servings=value)
    except httpx.TimeoutException:
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update timed out; canonical outcome is unknown.")
        return _result("FAILED", error="Grocy could not be reached before the serving update.")
    except httpx.HTTPError as exc:
        # A connection failure cannot have sent the PUT request. Keep this
        # distinguishable from a timeout or response failure after mutation
        # was attempted, whose canonical outcome must be reconciled.
        if mutation_attempted and not mutation_response_received and exc.__class__.__name__ == "ConnectError":
            return _result("FAILED", error="Grocy could not be reached before the serving update.")
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update was attempted but canonical outcome is unknown.")
        return _result("FAILED", error="Grocy serving update failed.")
    except (ValueError, KeyError, TypeError):
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update was attempted but canonical outcome is unknown.")
        return _result("FAILED", error="Grocy serving update failed.")


async def list_tools():
    return ListToolsResult(tools=[Tool(
        name=TOOL_NAME,
        description=(
            "Set the canonical Grocy recipe serving count. Use only after a "
            "recipe has been identified; this updates Grocy directly and "
            "verifies the resulting base_servings value."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "recipe": {"type": "string"},
                "servings": {"type": "integer", "minimum": 1, "maximum": MAX_SERVINGS},
            },
            "required": ["recipe", "servings"],
        },
    )])


async def call_tool(tool_name, args):
    if tool_name != TOOL_NAME:
        raise ValueError(f"unknown tool: {tool_name}")
    args = args or {}
    result = await set_servings(args.get("recipe", ""), args.get("servings"))
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(result, sort_keys=True))])


async def main():
    server = Server("hades-grocy-recipe-authoring")
    server.list_tools()(list_tools)
    server.call_tool()(call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
