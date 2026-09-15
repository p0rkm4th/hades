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
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


MAX_HTML_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 15
_NUMBER = r"(?:\d+(?:\.\d+)?|\d+\s*/\s*\d+|[¼½¾⅓⅔⅛⅜⅝⅞])"
_UNIT = r"(?:tsp|teaspoons?|tbsp|tablespoons?|cups?|ounces?|oz|pounds?|lbs?|lb|grams?|g|kilograms?|kg|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l|pinch(?:es)?|cloves?|cans?|packages?|sticks?)"
_QUANTITY = re.compile(rf"^\s*(?P<quantity>{_NUMBER})(?:\s*[-–]\s*(?P<maximum>{_NUMBER}))?\s*(?P<unit>{_UNIT})?\b\s*(?P<name>.*)$", re.I)


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


def extract_from_url(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    safe = _safe_url(url)
    request = Request(safe, headers={"User-Agent": "HADES recipe preview/1.0"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError(f"Recipe source returned unsupported content type: {content_type}")
        body = response.read(MAX_HTML_BYTES + 1)
    if len(body) > MAX_HTML_BYTES:
        raise ValueError("Recipe source exceeds the bounded preview size.")
    return extract_from_html(body.decode("utf-8", errors="replace"), safe)


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
