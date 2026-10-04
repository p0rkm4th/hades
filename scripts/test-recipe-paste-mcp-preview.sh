#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
hermes_python=${HADES_HERMES_PYTHON:-}
if [[ -z "$hermes_python" ]]; then
  hermes_bin=$(readlink -f "$(command -v hermes || true)")
  [[ -z "$hermes_bin" ]] || hermes_python="$(dirname "$hermes_bin")/python3.11"
fi
[[ -x "$hermes_python" ]] || { echo 'FAIL Hermes Python 3.11 is unavailable' >&2; exit 2; }

PYTHONPATH="$repo_dir/integrations/recipe-ingest" \
  "$hermes_python" - "$repo_dir" <<'PY'
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1])
server_path = repo / "integrations/recipe-ingest/server.py"
spec = importlib.util.spec_from_file_location("hades_recipe_ingest_server", server_path)
server = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(server)

from recipe_ingest import GrocyRecipeImporter, extract_from_paste

calls = []


def synthetic_grocy(method, path, payload=None):
    calls.append((method, path, payload))
    if method != "GET":
        raise AssertionError(f"paste preview attempted canonical write: {method} {path}")
    if path.endswith("/products"):
        return [{"id": 91, "name": "HADES Synthetic Tomato"}]
    if path.endswith("/quantity_units"):
        return [{"id": 4, "name": "Cup"}]
    if path.endswith("/recipes"):
        return []
    raise AssertionError(f"unexpected synthetic endpoint: {method} {path}")


server._importer = GrocyRecipeImporter(
    synthetic_grocy, signing_key=b"synthetic-only-review-key"
)
tools = asyncio.run(server.list_tools()).tools
assert "recipe_paste_preview" in {tool.name for tool in tools}

recipe_text = """Synthetic Tomato Soup
Serves: 2

Ingredients:
- 1 cup HADES Synthetic Tomato

Instructions:
- Heat gently.
"""
result = asyncio.run(server.call_tool(
    "recipe_paste_preview",
    {
        "text": recipe_text,
        "source_url": "https://recipes.example.test/synthetic-soup?access_token=SYNTHETIC_SENTINEL#private",
    },
))
preview = json.loads(result.content[0].text)
assert preview["outcome"] == "PREVIEW", preview
assert preview["recipe"]["title"] == "Synthetic Tomato Soup", preview
assert preview["recipe"]["source"] == "pasted recipe text", preview
assert preview["recipe"]["requires_review"] is True, preview
assert preview["recipe"]["ingredients"][0]["resolution"] == "EXACT", preview
assert preview["plan"]["ingredients"][0]["product_id"] == 91, preview
assert preview["recipe"]["source_url"] == "https://recipes.example.test/synthetic-soup", preview
assert "SYNTHETIC_SENTINEL" not in json.dumps(preview), preview
assert "?" not in preview["plan"]["recipe"]["description"], preview
assert any("query and fragment were removed" in warning for warning in preview["recipe"]["warnings"]), preview
assert all(method == "GET" for method, _, _ in calls), calls
assert {path for _, path, _ in calls} == {
    "/api/objects/products",
    "/api/objects/quantity_units",
    "/api/objects/recipes",
}, calls

before = len(calls)
bad = asyncio.run(server.call_tool("recipe_paste_preview", {"text": ""}))
failure = json.loads(bad.content[0].text)
assert failure["outcome"] == "FAILED", failure
assert len(calls) == before, calls

for unsafe_url in (
    "https://user:password@recipes.example.test/soup",
    "http://127.0.0.1/soup",
    "https://hades.example.invalid/soup",
    "https://recipes.example.test/soup\nSource: forged",
):
    rejected = asyncio.run(server.call_tool(
        "recipe_paste_preview", {"text": recipe_text, "source_url": unsafe_url}
    ))
    assert json.loads(rejected.content[0].text)["outcome"] == "FAILED"
assert len(calls) == before, calls

jsonld = json.dumps({
    "@type": "Recipe",
    "name": "Synthetic JSON-LD Soup",
    "recipeYield": "2",
    "recipeIngredient": ["1 cup HADES Synthetic Tomato"],
    "recipeInstructions": ["Heat gently."],
})
structured = extract_from_paste(
    jsonld,
    "https://recipes.example.test/structured-soup?key=STRUCTURED_SENTINEL#private",
)
assert structured["source_url"] == "https://recipes.example.test/structured-soup", structured
assert "STRUCTURED_SENTINEL" not in json.dumps(structured), structured
print("PASS registered recipe paste MCP returns an exact, review-required canonical preview")
print("PASS text and JSON-LD provenance removes query/fragment data and rejects credentials, local hosts, and controls")
print("PASS paste preview performs only bounded Grocy GETs; invalid input performs no request")
PY
