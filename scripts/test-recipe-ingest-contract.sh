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

pasted = module.extract_from_paste("""# Weeknight Pasta
Serves: 4

Ingredients:
- 1 cup tomatoes
- 2 tbsp basil

Instructions:
1. Mix everything.
2. Serve.
""", "https://recipes.example.test/pasted")
assert pasted["source"] == "pasted recipe text"
assert pasted["title"] == "Weeknight Pasta"
assert pasted["servings"] == "4"
assert [item["name"] for item in pasted["ingredients"]] == ["tomatoes", "basil"]
assert pasted["instructions"] == ["1. Mix everything.", "2. Serve."]

json_blob = '{"@context":"https://schema.org","@type":"Recipe","name":"Blob Cake","recipeYield":"6 servings","recipeIngredient":["2 cups flour"],"recipeInstructions":"Bake it."}'
assert module.extract_from_paste(json_blob)["title"] == "Blob Cake"
assert module.extract_from_paste('<script type="application/ld+json">' + json_blob + '</script>')["title"] == "Blob Cake"
visible_html = """<article><h1>HTML Soup</h1><p>Serves: 2</p><h2>Ingredients</h2><ul><li>1 cup tomatoes</li><li>2 tbsp basil</li></ul><h2>Directions</h2><p>Stir and serve.</p></article>"""
html_paste = module.extract_from_paste(visible_html)
assert html_paste["source"] == "pasted recipe text"
assert html_paste["title"] == "HTML Soup"
assert [item["name"] for item in html_paste["ingredients"]] == ["tomatoes", "basil"]
assert html_paste["instructions"] == ["Stir and serve."]

class _Headers:
    def get_content_type(self):
        return "text/html"

class _Response:
    headers = _Headers()
    def geturl(self):
        return "https://recipes.example.test/fallback"
    def read(self, _limit):
        return visible_html.encode()
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return None

class _Opener:
    def open(self, _request, timeout):
        assert timeout == module.DEFAULT_TIMEOUT_SECONDS
        return _Response()

original_safe_url = module._safe_url
original_build_opener = module.build_opener
module._safe_url = lambda value: value
module.build_opener = lambda _handler: _Opener()
try:
    fetched_fallback = module.extract_from_url("https://recipes.example.test/fallback")
finally:
    module._safe_url = original_safe_url
    module.build_opener = original_build_opener
assert fetched_fallback["source"] == "public URL visible-text fallback"
assert fetched_fallback["requires_review"] is True
assert any("visible-text fallback" in warning for warning in fetched_fallback["warnings"])
assert fetched_fallback["source_url"] == "https://recipes.example.test/fallback"
for invalid_paste in ("Recipe without sections", "Ingredients:\n- 1 cup flour"):
    try:
        module.extract_from_paste(invalid_paste)
    except ValueError:
        pass
    else:
        raise AssertionError("underspecified pasted recipe accepted")

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
ready["ingredients"][1]["unit"] = "cups"
plan = module.build_apply_plan(ready, [{"id": 1, "name": "lb"}, {"id": 2, "name": "cup"}])
assert plan["recipe"]["name"] == "Weeknight Tacos"
assert plan["recipe"]["base_servings"] == 4
assert plan["ingredients"][1]["amount"] == "1/2"
assert plan["ingredients"][1]["recipe_id"] == "<created_recipe_id>"

for bad_servings in ("0 servings", "-1 servings", "2.5 servings", "two servings", None):
    invalid_servings = dict(ready, servings=bad_servings)
    try:
        module.build_apply_plan(invalid_servings, [{"id": 1, "name": "lb"}, {"id": 2, "name": "cup"}])
    except ValueError as exc:
        assert "servings" in str(exc).lower(), (bad_servings, exc)
    else:
        raise AssertionError(f"invalid servings accepted: {bad_servings!r}")

for bad_quantity in ("0", "-1", "1/0", "1000001"):
    invalid_quantity = dict(ready, ingredients=[dict(ready["ingredients"][0], quantity=bad_quantity), ready["ingredients"][1]])
    try:
        module.build_apply_plan(invalid_quantity, [{"id": 1, "name": "lb"}, {"id": 2, "name": "cup"}])
    except ValueError as exc:
        assert "quantity" in str(exc).lower(), (bad_quantity, exc)
    else:
        raise AssertionError(f"invalid quantity accepted: {bad_quantity!r}")

duplicate_ingredient = dict(ready, ingredients=[ready["ingredients"][0], dict(ready["ingredients"][0], name="ground beef")])
try:
    module.build_apply_plan(duplicate_ingredient, [{"id": 1, "name": "lb"}])
except ValueError as exc:
    assert "duplicate" in str(exc).lower()
else:
    raise AssertionError("duplicate ingredient accepted")

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
failure_importer = module.GrocyRecipeImporter(post_write_failure)
other_recipe = dict(import_recipe)
other_recipe["title"] = "Other"
failure_preview = failure_importer.preview(other_recipe)
assert failure_preview["plan"] and not failure_preview["duplicate"]
unknown = failure_importer.apply(failure_preview, confirm=True)
assert unknown["outcome"] == "OUTCOME UNKNOWN"

def malformed_create_response(method, path, payload=None):
    if method == "GET":
        return request(method, path, payload)
    if path == "/api/objects/recipes":
        state["recipes"].append({"id": 42, **payload})
        return {}
    raise AssertionError((method, path, payload))
malformed_importer = module.GrocyRecipeImporter(malformed_create_response)
malformed_recipe = dict(import_recipe)
malformed_recipe["title"] = "Malformed Response Recipe"
malformed_preview = malformed_importer.preview(malformed_recipe)
malformed_result = malformed_importer.apply(malformed_preview, confirm=True)
assert malformed_result["outcome"] == "OUTCOME UNKNOWN", malformed_result

try:
    module.extract_from_html('<script type="application/ld+json">{"@type":"Recipe"}</script>')
except ValueError as exc:
    assert "title" in str(exc)
else:
    raise AssertionError("missing recipe title was accepted")

for invalid in ("file:///tmp/recipe.html", "ftp://example.test/recipe", "http://127.0.0.1/recipe", "https://user:secret@example.test/recipe"):
    try:
        module._safe_url(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"unsafe URL accepted: {invalid}")

assert "class _SafeRedirectHandler" in path.read_text()
assert "_safe_url(newurl)" in path.read_text()
assert "final_url = _safe_url(response.geturl())" in path.read_text()

print("PASS recipe JSON-LD graph extraction")
print("PASS recipe pasted text, HTML, and JSON-LD converge on one normalized contract")
print("PASS recipe normalization preserves raw evidence and review state")
print("PASS recipe URL visible-text fallback remains review-required")
print("PASS recipe URL fetch boundary rejects unsupported/private targets")
print("PASS recipe URL redirects revalidate every destination")
PY
