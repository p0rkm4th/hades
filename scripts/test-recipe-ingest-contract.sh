#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("integrations/recipe-ingest/recipe_ingest.py")
spec = importlib.util.spec_from_file_location("recipe_ingest", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

html = '''<html><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
 {"@type":"BreadcrumbList","name":"not a recipe"},
 {"@type":"Recipe","name":"Weeknight Tacos","recipeYield":"4 servings",
  "recipeIngredient":["1 lb ground beef","2 cups shredded cheese","salt to taste","½ cup salsa"],
  "recipeInstructions":[{"@type":"HowToStep","text":"Brown the beef."},{"@type":"HowToStep","text":"Assemble tacos."}],
  "description":"A synthetic recipe for contract testing."}
]}
</script></html>'''

result = module.extract_from_html(html, "https://recipes.example.test/tacos")
assert result["title"] == "Weeknight Tacos"
assert result["source_url"] == "https://recipes.example.test/tacos"
assert result["servings"] == "4 servings"
assert result["instructions"] == ["Brown the beef.", "Assemble tacos."]
assert result["ingredients"][0]["name"] == "ground beef"
assert result["ingredients"][0]["quantity"] == "1"
assert result["ingredients"][0]["unit"] == "lb"
assert result["ingredients"][3]["quantity"] == "½"
assert result["requires_review"] is True
assert any("review" in warning.lower() for warning in result["warnings"])

resolved = module.resolve_products(result, [
    {"id": 10, "name": "Ground Beef"},
    {"id": 11, "name": "Shredded Cheese"},
    {"id": 12, "name": "Salsa"},
])
assert resolved["ingredients"][0]["product_id"] == 10
assert resolved["ingredients"][0]["resolution"] == "EXACT"
assert resolved["ingredients"][2]["resolution"] == "UNRESOLVED"
assert resolved["requires_review"] is True

ambiguous = module.resolve_products(result, [
    {"id": 20, "name": "Ground Beef"},
    {"id": 21, "name": "ground beef"},
])
assert ambiguous["ingredients"][0]["resolution"] == "AMBIGUOUS"

ready = dict(result)
ready["requires_review"] = False
ready["warnings"] = []
ready["ingredients"] = [
    {"raw": "1 lb ground beef", "name": "ground beef", "quantity": "1", "unit": "lb", "product_id": 10, "resolution": "EXACT"},
    {"raw": "½ cup salsa", "name": "salsa", "quantity": "½", "unit": "cup", "product_id": 12, "resolution": "EXACT"},
]
plan = module.build_apply_plan(ready, [{"id": 1, "name": "lb"}, {"id": 2, "name": "cup"}])
assert plan["recipe"]["name"] == "Weeknight Tacos"
assert plan["recipe"]["base_servings"] == 4
assert plan["ingredients"][1]["amount"] == "1/2"
assert plan["ingredients"][1]["recipe_id"] == "<created_recipe_id>"

try:
    module.build_apply_plan(result, [{"id": 1, "name": "lb"}])
except ValueError as exc:
    assert "review" in str(exc).lower()
else:
    raise AssertionError("unreviewed recipe produced an apply plan")

import_recipe = dict(result)
import_recipe["requires_review"] = False
import_recipe["warnings"] = []
import_recipe["ingredients"] = [
    {"raw": "1 lb ground beef", "name": "ground beef", "quantity": "1", "unit": "lb"},
    {"raw": "½ cup salsa", "name": "salsa", "quantity": "½", "unit": "cup"},
]

state = {"recipes": [], "positions": []}
def request(method, path, payload=None):
    if method == "GET" and path == "/api/objects/products":
        return [{"id": 10, "name": "ground beef"}, {"id": 12, "name": "salsa"}]
    if method == "GET" and path == "/api/objects/quantity_units":
        return [{"id": 1, "name": "lb"}, {"id": 2, "name": "cup"}]
    if method == "GET" and path == "/api/objects/recipes":
        return state["recipes"]
    if method == "GET" and path.startswith("/api/objects/recipes/"):
        return state["recipes"][0]
    if method == "GET" and path == "/api/objects/recipes_pos":
        return state["positions"]
    if method == "POST" and path == "/api/objects/recipes":
        state["recipes"].append({"id": 40, **payload})
        return {"created_object_id": 40}
    if method == "POST" and path == "/api/objects/recipes_pos":
        state["positions"].append(payload)
        return {}
    raise AssertionError((method, path, payload))

importer = module.GrocyRecipeImporter(request)
preview = importer.preview(import_recipe)
assert preview["outcome"] == "PREVIEW" and preview["plan"]
assert importer.apply(preview)["outcome"] == "FAILED"
applied = importer.apply(preview, confirm=True)
assert applied["outcome"] == "SUCCEEDED" and applied["recipe_id"] == 40
duplicate = importer.preview(import_recipe)
assert duplicate["duplicate"] is True and duplicate["plan"] is None

def post_write_failure(method, path, payload=None):
    if method == "GET":
        return request(method, path, payload)
    if path == "/api/objects/recipes":
        return {"created_object_id": 41}
    raise module.GrocyRequestError("connection lost after mutation", after_mutation=True)
unknown = module.GrocyRecipeImporter(post_write_failure).apply(
    {"plan": {"recipe": {"name": "Other"}, "ingredients": [{"product_id": 10, "amount": "1", "qu_id": 1}]}, "duplicate": False},
    confirm=True,
)
assert unknown["outcome"] == "OUTCOME UNKNOWN"

try:
    module.extract_from_html('<script type="application/ld+json">{"@type":"Recipe"}</script>')
except ValueError as exc:
    assert "title" in str(exc)
else:
    raise AssertionError("missing recipe title was accepted")

for invalid in ("file:///tmp/recipe.html", "ftp://example.test/recipe", "http://127.0.0.1/recipe"):
    try:
        module._safe_url(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"unsafe URL accepted: {invalid}")

print("PASS recipe JSON-LD graph extraction")
print("PASS recipe normalization preserves raw evidence and review state")
print("PASS recipe URL fetch boundary rejects unsupported/private targets")
PY
