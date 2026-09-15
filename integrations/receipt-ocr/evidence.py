"""Normalize OCR output into reviewable receipt evidence.

This is deliberately not an OCR engine and does not own receipts, groceries,
or finance state. It consumes text/line confidence from PaddleOCR (or another
upstream engine) and emits evidence for a later reviewed intake workflow.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any


MONEY = r"(?:\$\s*)?\d+(?:[,.]\d{3})*(?:\.\d{2})"
MONEY_RE = re.compile(rf"(?P<amount>{MONEY})\s*$")
TOTAL_RE = re.compile(rf"^\s*(?P<label>subtotal|tax|total|amount due)\s*:?[ \t]+(?P<amount>{MONEY})\s*$", re.I)
ITEM_RE = re.compile(rf"^(?P<name>.+?)\s+(?P<amount>{MONEY})\s*$")


def _money(value: str) -> str:
    text = value.replace("$", "").replace(",", "").strip()
    try:
        return f"{Decimal(text):.2f}"
    except InvalidOperation as exc:
        raise ValueError(f"invalid monetary value: {value}") from exc


def receipt_fingerprint(image_bytes: bytes) -> str:
    """Return a stable identity for duplicate-review detection."""
    return hashlib.sha256(image_bytes).hexdigest()


def normalize_ocr_lines(lines: list[dict[str, Any]], *, source_ref: str | None = None) -> dict[str, Any]:
    """Convert OCR lines to evidence without pretending uncertain parses are facts.

    Each input line should contain ``text`` and may contain ``confidence``.
    The parser only recognizes explicit labeled totals and trailing prices;
    everything else remains raw/unparsed for review.
    """
    if not isinstance(lines, list) or not lines:
        return {"status": "FAILED", "error": "OCR returned no text lines.", "source_ref": source_ref}
    merchant: str | None = None
    date: str | None = None
    totals: dict[str, str] = {}
    items: list[dict[str, Any]] = []
    raw_lines: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, line in enumerate(lines):
        if not isinstance(line, dict) or not str(line.get("text", "")).strip():
            warnings.append(f"OCR line {index + 1} was empty or malformed.")
            continue
        text = " ".join(str(line["text"]).split())
        confidence = line.get("confidence")
        evidence = {"text": text, "confidence": confidence, "line": index + 1}
        raw_lines.append(evidence)
        total_match = TOTAL_RE.match(text)
        if total_match:
            totals[total_match.group("label").lower()] = _money(total_match.group("amount"))
            continue
        if merchant is None and index == 0:
            merchant = text
            continue
        if re.search(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", text):
            date = text
        item_match = ITEM_RE.match(text)
        if item_match and not re.search(r"\b(?:subtotal|tax|total|amount due)\b", text, re.I):
            amount = _money(item_match.group("amount"))
            name = item_match.group("name").strip()
            item = {"raw": text, "name": name, "line_total": amount, "confidence": confidence}
            if confidence is None or (isinstance(confidence, (int, float)) and confidence < 0.85):
                item["needs_review"] = True
                warnings.append(f"Receipt line needs review: {name}")
            items.append(item)
        else:
            evidence["unparsed"] = True
    if not items:
        warnings.append("No line items were confidently structured.")
    if "total" in totals and "subtotal" in totals and "tax" in totals:
        expected = Decimal(totals["subtotal"]) + Decimal(totals["tax"])
        if expected != Decimal(totals["total"]):
            warnings.append("Subtotal plus tax does not match the printed total.")
    if any(item.get("needs_review") for item in items):
        warnings.append("One or more item matches require review before household intake.")
    return {
        "status": "PARTIAL" if warnings else "SUCCEEDED",
        "merchant": merchant,
        "date": date,
        "totals": totals,
        "items": items,
        "raw_lines": raw_lines,
        "source_ref": source_ref,
        "warnings": list(dict.fromkeys(warnings)),
        "requires_review": True,
    }


def build_intake_preview(evidence: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a Grocy intake preview; never apply it."""
    if evidence.get("status") == "FAILED":
        return {"status": "FAILED", "error": evidence.get("error", "OCR failed.")}
    by_index = {int(match["item_index"]): match for match in matches if isinstance(match, dict) and "item_index" in match}
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(evidence.get("items", [])):
        match = by_index.get(index)
        row = {"raw": item.get("raw"), "name": item.get("name"), "line_total": item.get("line_total")}
        if match and match.get("product_id") and match.get("resolution") == "EXACT":
            row.update({"product_id": int(match["product_id"]), "resolution": "EXACT"})
        else:
            row.update({"resolution": "REVIEW_REQUIRED", "candidates": (match or {}).get("candidates", [])})
        rows.append(row)
    return {
        "status": "PREVIEW",
        "merchant": evidence.get("merchant"),
        "date": evidence.get("date"),
        "items": rows,
        "totals": evidence.get("totals", {}),
        "warnings": evidence.get("warnings", []),
        "requires_review": True,
        "canonical_target": "Grocy stock intake",
    }
