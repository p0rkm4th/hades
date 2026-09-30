"""Narrow MCP adapter for the Grocy recipe serving-count field.

The selected upstream Grocy MCP exposes recipe name/description updates but
omits Grocy's ``base_servings`` field.  This adapter adds only the missing
canonical operation; it does not keep recipe state locally or expose generic
Grocy object mutation.
"""

from __future__ import annotations

import json
import os
import stat
from typing import Any
from pathlib import Path

import anyio
import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool


BASE_URL = os.environ.get("GROCY_URL", "http://127.0.0.1:7003").rstrip("/")


def _load_api_key() -> str:
    """Read the canonical file-backed key, retaining a protected-env fallback."""
    key_file = os.environ.get("GROCY_API_KEY_FILE", "").strip()
    if not key_file:
        value = os.environ.get("GROCY_API_KEY", "").strip()
        return value if value and "\n" not in value and "\r" not in value else ""
    path = Path(key_file)
    try:
        if not path.is_absolute() or path.is_symlink():
            return ""
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) not in {0o600, 0o640}:
            return ""
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    return value if value and "\n" not in value and "\r" not in value else ""


API_KEY = _load_api_key()
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
    write_response_received = False
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
            write_response_received = True
            response.raise_for_status()
            verified = await client.get(f"{BASE_URL}/api/objects/recipes/{recipe_id}")
            verified.raise_for_status()
            current = verified.json()
            canonical_servings = current.get("base_servings") if isinstance(current, dict) else None
            # Do not coerce malformed read-back values: a verification response
            # must be canonical before a mutation can be reported successful.
            if (
                isinstance(canonical_servings, bool)
                or not isinstance(canonical_servings, int)
                or canonical_servings != value
            ):
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
        if mutation_attempted and not write_response_received and exc.__class__.__name__ == "ConnectError":
            return _result("FAILED", error="Grocy could not be reached before the serving update.")
        if mutation_attempted and write_response_received:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if isinstance(status_code, int) and 400 <= status_code < 500:
                return _result("FAILED", error="Grocy rejected the serving update.")
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update was attempted but canonical outcome is unknown.")
    return _result("FAILED", error="Grocy serving update failed.")


async def preview_servings(recipe: str, servings: int) -> dict[str, Any]:
    """Read a canonical recipe and return a write-free serving preview."""
    if not API_KEY:
        return _result("FAILED", error="Grocy recipe authoring is not configured.")
    recipe_text = str(recipe or "").strip()
    if not recipe_text:
        return _result("FAILED", error="A recipe name or numeric ID is required.")
    if isinstance(servings, bool) or not isinstance(servings, int) or not 1 <= servings <= MAX_SERVINGS:
        return _result("FAILED", error=f"Servings must be an integer between 1 and {MAX_SERVINGS}.")
    try:
        async with httpx.AsyncClient(headers={"GROCY-API-KEY": API_KEY}, timeout=TIMEOUT_SECONDS) as client:
            found, error = await _get_recipe(client, recipe_text)
            if error:
                return error
            current = found.get("base_servings") if isinstance(found, dict) else None
            if isinstance(current, bool) or not isinstance(current, int) or current < 1:
                return _result("FAILED", error="Grocy did not return a valid current serving count.")
            return _result(
                "PREVIEW", recipe_id=int(found["id"]), recipe=str(found.get("name") or recipe_text),
                current_servings=current, requested_servings=servings,
            )
    except httpx.TimeoutException:
        return _result("FAILED", error="Grocy could not be reached to preview the serving change.")
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return _result("FAILED", error="Grocy could not verify the recipe serving count.")


async def apply_servings_preview(recipe_id: int, expected_current: int, servings: int) -> dict[str, Any]:
    """Apply a confirmed preview only if canonical servings are unchanged."""
    if not API_KEY:
        return _result("FAILED", error="Grocy recipe authoring is not configured.")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (recipe_id, expected_current, servings)):
        return _result("FAILED", error="The serving preview is invalid.")
    if recipe_id < 1 or not 1 <= expected_current <= MAX_SERVINGS or not 1 <= servings <= MAX_SERVINGS:
        return _result("FAILED", error="The serving preview is outside the supported range.")
    headers = {"GROCY-API-KEY": API_KEY}
    mutation_attempted = False
    write_response_received = False
    try:
        async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT_SECONDS) as client:
            current_response = await client.get(f"{BASE_URL}/api/objects/recipes/{recipe_id}")
            if current_response.status_code == 404:
                return _result("FAILED", error="Recipe was not found; nothing changed.")
            current_response.raise_for_status()
            current = current_response.json()
            current_servings = current.get("base_servings") if isinstance(current, dict) else None
            if isinstance(current_servings, bool) or not isinstance(current_servings, int):
                return _result("FAILED", error="Grocy did not return a valid current serving count; nothing changed.")
            if current_servings == servings:
                return _result("SUCCEEDED", recipe_id=recipe_id, base_servings=servings)
            if current_servings != expected_current:
                return _result(
                    "STALE PREVIEW", recipe_id=recipe_id, current_servings=current_servings,
                    error="The recipe changed after preview; no serving update was made.",
                )
            mutation_attempted = True
            response = await client.put(
                f"{BASE_URL}/api/objects/recipes/{recipe_id}",
                json={"base_servings": servings},
            )
            write_response_received = True
            response.raise_for_status()
            verified = await client.get(f"{BASE_URL}/api/objects/recipes/{recipe_id}")
            verified.raise_for_status()
            result = verified.json()
            canonical = result.get("base_servings") if isinstance(result, dict) else None
            if isinstance(canonical, bool) or not isinstance(canonical, int) or canonical != servings:
                return _result("OUTCOME UNKNOWN", error="Grocy did not confirm the requested serving count.")
            return _result("SUCCEEDED", recipe_id=recipe_id, base_servings=canonical)
    except httpx.TimeoutException:
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update timed out; check its current value before retrying.")
        return _result("FAILED", error="Grocy could not be reached; nothing changed.")
    except httpx.HTTPError as exc:
        if mutation_attempted and write_response_received:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if isinstance(status_code, int) and 400 <= status_code < 500:
                return _result("FAILED", error="Grocy rejected the serving update; nothing changed.")
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update was attempted but its result is unknown.")
        return _result("FAILED", error="Grocy could not verify the current serving count; nothing changed.")
    except (ValueError, KeyError, TypeError):
        if mutation_attempted:
            return _result("OUTCOME UNKNOWN", error="Grocy serving update was attempted but its result is unknown.")
        return _result("FAILED", error="Grocy could not verify the current serving count; nothing changed.")
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


async def _list_tools(_context, _params):
    return await list_tools()


async def _call_tool(_context, params):
    return await call_tool(params.name, params.arguments)


async def main():
    server = Server("hades-grocy-recipe-authoring", on_list_tools=_list_tools, on_call_tool=_call_tool)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
