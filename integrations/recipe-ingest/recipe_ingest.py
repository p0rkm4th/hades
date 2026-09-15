"""Source-agnostic recipe extraction and normalization.

This module deliberately stops at a reviewable recipe object.  It does not
write Grocy, create products, or treat an unparsed ingredient as canonical
state.  A future MCP/apply layer can consume the normalized object after an
explicit preview and product-resolution decision.
"""

from __future__ import annotations

import html as html_module
import json
import re
import socket
from fractions import Fraction
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_HTML_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 15
MAX_RECIPE_SERVINGS = 1000
MAX_INGREDIENT_QUANTITY = Fraction(1_000_000)
_NUMBER = r"(?:\d+(?:\.\d+)?|\d+\s*/\s*\d+|[¼½¾⅓⅔⅛⅜⅝⅞])"
_UNIT = r"(?:tsp|teaspoons?|tbsp|tablespoons?|cups?|ounces?|oz|pounds?|lbs?|lb|grams?|g|kilograms?|kg|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l|pinch(?:es)?|cloves?|cans?|packages?|sticks?)"
_QUANTITY = re.compile(rf"^\s*(?P<quantity>{_NUMBER})(?:\s*[-–]\s*(?P<maximum>{_NUMBER}))?\s*(?P<unit>{_UNIT})?\b\s*(?P<name>.*)$", re.I)
_UNIT_ALIASES = {
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "cup": "cup", "cups": "cup",
    "ounce": "oz", "ounces": "oz", "oz": "oz",
    "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb",
    "gram": "g", "grams": "g", "g": "g",
    "kilogram": "kg", "kilograms": "kg", "kg": "kg",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml", "ml": "ml",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l", "l": "l",
    "pinch": "pinch", "pinches": "pinch", "clove": "clove", "cloves": "clove",
    "can": "can", "cans": "can", "package": "package", "packages": "package",
    "stick": "stick", "sticks": "stick",
}


@dataclass(frozen=True)
class Ingredient:
    raw: str
    name: str
    quantity: str | None = None
    maximum: str | None = None
    unit: str | None = None
    confidence: str = "LOW"


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_json_ld = False
        self._buffer: list[str] = []
        self.documents: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        if values.get("type", "").lower().split(";")[0].strip() == "application/ld+json":
            self._in_json_ld = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "script" or not self._in_json_ld:
            return
        self._in_json_ld = False
        raw = "".join(self._buffer).strip()
        self._buffer = []
        if not raw:
            return
        try:
            self.documents.append(json.loads(html_module.unescape(raw)))
        except json.JSONDecodeError:
            # A malformed JSON-LD block is evidence of an incomplete source,
            # not permission to invent fields from page prose.
            return


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _is_recipe(value: dict[str, Any]) -> bool:
    kind = value.get("@type", value.get("type", ""))
    kinds = kind if isinstance(kind, list) else [kind]
    return any(str(item).lower().rsplit("/", 1)[-1] == "recipe" for item in kinds)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, dict):
        return _text(value.get("text", value.get("name", value.get("value", ""))))
    return ""


def _instructions(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_instructions(item))
        return result
    if isinstance(value, dict):
        return _instructions(value.get("text", value.get("itemListElement", "")))
    return []


def parse_ingredient(raw: str) -> Ingredient:
    clean = " ".join(str(raw).split()).strip()
    match = _QUANTITY.match(clean)
    if not match:
        return Ingredient(raw=clean, name=clean, confidence="LOW")
    name = match.group("name").strip(" ,;:")
    if not name:
        return Ingredient(raw=clean, name=clean, confidence="LOW")
    return Ingredient(
        raw=clean,
        name=name,
        quantity=match.group("quantity").replace(" ", ""),
        maximum=(match.group("maximum") or None),
        unit=(match.group("unit") or None),
        confidence="MEDIUM" if match.group("unit") else "LOW",
    )


def extract_from_html(source_html: str, source_url: str | None = None) -> dict[str, Any]:
    parser = _JsonLdParser()
    parser.feed(source_html)
    recipes = [item for document in parser.documents for item in _walk(document) if isinstance(item, dict) and _is_recipe(item)]
    if not recipes:
        raise ValueError("No Schema.org Recipe JSON-LD was found; preview requires pasted recipe text or a supported fallback.")
    recipe = recipes[0]
    raw_ingredients = recipe.get("recipeIngredient", [])
    if isinstance(raw_ingredients, str):
        raw_ingredients = [raw_ingredients]
    ingredients = [parse_ingredient(_text(item)) for item in raw_ingredients if _text(item)]
    title = _text(recipe.get("name"))
    if not title:
        raise ValueError("Recipe JSON-LD did not provide a title.")
    yield_value = _text(recipe.get("recipeYield"))
    warnings: list[str] = []
    if not ingredients:
        warnings.append("No ingredients were supplied by the source.")
    if any(item.confidence == "LOW" for item in ingredients):
        warnings.append("One or more ingredient lines need review before Grocy resolution.")
    if not _instructions(recipe.get("recipeInstructions")):
        warnings.append("No instructions were supplied by the source.")
    return {
        "source": "schema.org/Recipe JSON-LD",
        "source_url": source_url,
        "title": title,
        "servings": yield_value or None,
        "ingredients": [asdict(item) for item in ingredients],
        "instructions": _instructions(recipe.get("recipeInstructions")),
        "notes": _text(recipe.get("description")) or None,
        "warnings": warnings,
        "requires_review": bool(warnings),
    }


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Recipe source must be an http(s) URL.")
    host = parsed.hostname
    try:
        addresses = {ip_address(host)}
    except ValueError:
        addresses = {ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)}
    if any(address.is_private or address.is_loopback or address.is_link_local or address.is_reserved for address in addresses):
        raise ValueError("Private or loopback recipe URLs are not allowed.")
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Re-apply the URL/SSRF boundary to every redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def extract_from_url(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    safe = _safe_url(url)
    request = Request(safe, headers={"User-Agent": "HADES recipe preview/1.0"})
    opener = build_opener(_SafeRedirectHandler)
    with opener.open(request, timeout=timeout) as response:
        final_url = _safe_url(response.geturl())
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Recipe source returned unsupported content type: {content_type}")
        body = response.read(MAX_HTML_BYTES + 1)
    if len(body) > MAX_HTML_BYTES:
        raise ValueError("Recipe source exceeds the bounded preview size.")
    return extract_from_html(body.decode("utf-8", errors="replace"), final_url)


def resolve_products(recipe: dict[str, Any], products: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach only exact, unique Grocy product matches to a preview.

    Fuzzy matching is intentionally not performed here.  A caller may show
    candidates to an owner, but this function must never turn a parser guess
    into a canonical product or silently create one.
    """
    by_name: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        if not isinstance(product, dict) or not product.get("name"):
            continue
        by_name.setdefault(str(product["name"]).casefold(), []).append(product)
    rows: list[dict[str, Any]] = []
    unresolved = False
    for ingredient in recipe.get("ingredients", []):
        name = str(ingredient.get("name", "")).strip()
        matches = by_name.get(name.casefold(), [])
        row = dict(ingredient)
        if len(matches) == 1:
            row["product_id"] = matches[0].get("id")
            row["product_name"] = matches[0].get("name")
            row["resolution"] = "EXACT"
        else:
            unresolved = True
            row["resolution"] = "UNRESOLVED" if not matches else "AMBIGUOUS"
            row["candidates"] = [item.get("name") for item in matches]
        rows.append(row)
    result = dict(recipe)
    result["ingredients"] = rows
    result["requires_review"] = bool(recipe.get("requires_review") or unresolved)
    if unresolved and "One or more ingredients need exact Grocy product review." not in result["warnings"]:
        result["warnings"] = list(result.get("warnings", [])) + [
            "One or more ingredients need exact Grocy product review."
        ]
    return result


def _serving_count(value: Any) -> int | None:
    """Parse an explicit integer serving count without truncating bad input."""
    text = " ".join(str(value or "").split())
    match = re.fullmatch(r"(\d+)(?:\s+[A-Za-z][A-Za-z -]*)?", text)
    return int(match.group(1)) if match else None


def _quantity(value: Any) -> str | None:
    text = str(value or "").strip().replace(" ", "")
    vulgar = {"¼": "1/4", "½": "1/2", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
    return vulgar.get(text, text) or None


def _unit_key(value: Any) -> str:
    text = " ".join(str(value or "").split()).casefold()
    return _UNIT_ALIASES.get(text, text)


def _validated_quantity(value: Any) -> str:
    amount = _quantity(value)
    if not amount:
        raise ValueError("Ingredient needs a numeric quantity.")
    try:
        parsed = Fraction(amount)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Ingredient quantity is not numeric: {amount}") from exc
    if parsed <= 0 or parsed > MAX_INGREDIENT_QUANTITY:
        raise ValueError("Ingredient quantity must be greater than zero and bounded.")
    return amount


def build_apply_plan(recipe: dict[str, Any], quantity_units: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a Grocy write plan without performing any write.

    All ingredient rows must already have an exact product resolution and a
    known quantity unit.  The plan is the review/confirmation boundary: its
    contents can be shown to the owner before the caller applies it.
    """
    if recipe.get("requires_review"):
        raise ValueError("Recipe requires review before it can be applied.")
    servings = _serving_count(recipe.get("servings"))
    if servings is None or servings < 1 or servings > MAX_RECIPE_SERVINGS:
        raise ValueError("Recipe servings must be between 1 and 1000.")
    units: dict[str, list[dict[str, Any]]] = {}
    for unit in quantity_units:
        if isinstance(unit, dict) and unit.get("name"):
            units.setdefault(_unit_key(unit["name"]), []).append(unit)
    rows: list[dict[str, Any]] = []
    product_ids: set[int] = set()
    for ingredient in recipe.get("ingredients", []):
        if ingredient.get("resolution") != "EXACT" or not ingredient.get("product_id"):
            raise ValueError(f"Ingredient is not exactly resolved: {ingredient.get('name', '')}")
        amount = _validated_quantity(ingredient.get("quantity"))
        unit_name = str(ingredient.get("unit") or "").strip()
        if not unit_name:
            raise ValueError(f"Ingredient needs a quantity unit: {ingredient.get('raw', '')}")
        matches = units.get(_unit_key(unit_name), [])
        if len(matches) != 1:
            raise ValueError(f"Quantity unit needs exact review: {unit_name}")
        product_id = int(ingredient["product_id"])
        if product_id in product_ids:
            raise ValueError(f"Duplicate ingredient product needs exact review: {ingredient.get('name', '')}")
        product_ids.add(product_id)
        rows.append({
            "recipe_id": "<created_recipe_id>",
            "product_id": product_id,
            "amount": amount,
            "qu_id": int(matches[0]["id"]),
            "note": ingredient.get("raw"),
        })
    if not rows:
        raise ValueError("Recipe has no ingredients.")
    description = recipe.get("notes") or ""
    if recipe.get("source_url"):
        description = f"{description}\nSource: {recipe['source_url']}".strip()
    return {
        "recipe": {
            "name": str(recipe.get("title", "")).strip(),
            "description": description,
            "base_servings": servings,
            "desired_servings": servings,
            "not_check_shoppinglist": False,
        },
        "ingredients": rows,
    }


class GrocyRequestError(RuntimeError):
    """Transport failure; ``after_mutation`` controls outcome semantics."""

    def __init__(self, message: str, *, after_mutation: bool = False):
        super().__init__(message)
        self.after_mutation = after_mutation


class GrocyRecipeImporter:
    """Preview/apply boundary over Grocy's supported generic object API.

    ``request`` is injected so the contract can be tested without a live
    household service. A production wrapper should provide a request function
    that sends the API key and raises ``GrocyRequestError`` on transport or
    HTTP failure.
    """

    def __init__(self, request):
        self.request = request

    def preview(self, recipe: dict[str, Any]) -> dict[str, Any]:
        products = self.request("GET", "/api/objects/products")
        units = self.request("GET", "/api/objects/quantity_units")
        resolved = resolve_products(recipe, products if isinstance(products, list) else [])
        try:
            plan = build_apply_plan(resolved, units if isinstance(units, list) else [])
        except ValueError as exc:
            plan = None
            resolved = dict(resolved)
            resolved["requires_review"] = True
            resolved["warnings"] = list(resolved.get("warnings", [])) + [str(exc)]
        existing = self.request("GET", "/api/objects/recipes")
        duplicate = any(
            isinstance(item, dict) and str(item.get("name", "")).casefold() == str(resolved.get("title", "")).casefold()
            for item in (existing if isinstance(existing, list) else [])
        )
        if duplicate:
            resolved["requires_review"] = True
            resolved["warnings"] = list(resolved.get("warnings", [])) + ["A Grocy recipe with this title already exists."]
            plan = None
        return {"outcome": "PREVIEW", "recipe": resolved, "plan": plan, "duplicate": duplicate}

    def reconcile(self, recipe_id: int, expected: dict[str, Any]) -> dict[str, Any]:
        recipe = self.request("GET", f"/api/objects/recipes/{recipe_id}")
        positions = self.request("GET", "/api/objects/recipes_pos")
        actual = [item for item in positions if isinstance(item, dict) and int(item.get("recipe_id", -1)) == recipe_id] if isinstance(positions, list) else []
        expected_rows = expected.get("ingredients", [])
        if not isinstance(recipe, dict) or int(recipe.get("id", recipe_id)) != recipe_id or len(actual) != len(expected_rows):
            return {"outcome": "OUTCOME UNKNOWN", "recipe_id": recipe_id}
        for row in expected_rows:
            if not any(
                int(item.get("product_id", -1)) == int(row["product_id"])
                and str(item.get("amount")) == str(row["amount"])
                and int(item.get("qu_id", -1)) == int(row["qu_id"])
                for item in actual
            ):
                return {"outcome": "OUTCOME UNKNOWN", "recipe_id": recipe_id}
        return {"outcome": "SUCCEEDED", "recipe_id": recipe_id, "recipe": recipe, "ingredients": actual}

    def apply(self, preview: dict[str, Any], *, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"outcome": "FAILED", "error": "Explicit confirmation is required."}
        plan = preview.get("plan") if isinstance(preview, dict) else None
        if not isinstance(plan, dict) or preview.get("duplicate"):
            return {"outcome": "FAILED", "error": "Only a complete non-duplicate preview can be applied."}
        mutation_attempted = False
        try:
            created = self.request("POST", "/api/objects/recipes", plan["recipe"])
            recipe_id = int(created["created_object_id"])
            mutation_attempted = True
            for ingredient in plan["ingredients"]:
                row = dict(ingredient)
                row["recipe_id"] = recipe_id
                self.request("POST", "/api/objects/recipes_pos", row)
            return self.reconcile(recipe_id, plan)
        except GrocyRequestError as exc:
            if mutation_attempted or exc.after_mutation:
                return {"outcome": "OUTCOME UNKNOWN", "error": "Grocy write was attempted; reconcile canonical state before retrying."}
            return {"outcome": "FAILED", "error": "Grocy write was not completed."}
        except (KeyError, TypeError, ValueError):
            if mutation_attempted:
                return {"outcome": "OUTCOME UNKNOWN", "error": "Grocy write was attempted; reconcile canonical state before retrying."}
            return {"outcome": "FAILED", "error": "Grocy rejected the recipe write."}
