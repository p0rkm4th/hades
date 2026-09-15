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
MAX_INTAKE_QUANTITY = Decimal("1000000")


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


def build_intake_preview(
    evidence: dict[str, Any],
    matches: list[dict[str, Any]],
    *,
    existing_fingerprints: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a Grocy intake preview; never apply it.

    Fingerprints are supplied by the caller because this module deliberately
    has no receipt database. A known fingerprint is a duplicate-review signal,
    not permission to replay or overwrite a canonical intake.
    """
    if evidence.get("status") == "FAILED":
        return {"status": "FAILED", "error": evidence.get("error", "OCR failed.")}
    fingerprint = evidence.get("receipt_fingerprint") or evidence.get("fingerprint")
    if fingerprint is not None and not isinstance(fingerprint, str):
        return {"status": "FAILED", "error": "Receipt fingerprint must be text."}
    duplicate = bool(fingerprint and fingerprint in set(existing_fingerprints))
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
    warnings = list(evidence.get("warnings", []))
    if duplicate:
        warnings.append("This receipt fingerprint was already submitted; canonical intake must be reconciled before retry.")
    return {
        "status": "PREVIEW",
        "merchant": evidence.get("merchant"),
        "date": evidence.get("date"),
        "items": rows,
        "totals": evidence.get("totals", {}),
        "warnings": list(dict.fromkeys(warnings)),
        "requires_review": True,
        "duplicate": duplicate,
        "receipt_fingerprint": fingerprint,
        "canonical_target": "Grocy stock intake",
    }


def build_intake_apply_plan(
    preview: dict[str, Any],
    *,
    reviewed: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Build, but never execute, an owner-confirmed Grocy intake request.

    OCR provides line prices, not reliable stock quantities. Quantities and
    quantity-unit IDs must therefore be supplied by the reviewed caller. The
    eventual Grocy adapter must reconcile its canonical stock response after
    applying this plan and classify an uncertain response separately.
    """
    if not reviewed:
        return {"status": "FAILED", "error": "Owner review is required before intake planning."}
    if not confirm:
        return {"status": "FAILED", "error": "Explicit intake confirmation is required."}
    if not isinstance(preview, dict) or preview.get("status") != "PREVIEW":
        return {"status": "FAILED", "error": "Only a complete intake preview can be applied."}
    if preview.get("duplicate"):
        return {"status": "FAILED", "error": "Duplicate receipt requires canonical reconciliation before retry."}
    rows: list[dict[str, Any]] = []
    product_ids: set[int] = set()
    for item in preview.get("items", []):
        if not isinstance(item, dict) or item.get("resolution") != "EXACT" or not item.get("product_id"):
            return {"status": "FAILED", "error": "Every receipt item needs an exact Grocy product match."}
        quantity = item.get("quantity")
        quantity_unit_id = item.get("quantity_unit_id")
        if quantity is None or quantity_unit_id is None:
            return {"status": "FAILED", "error": "Each reviewed item needs a stock quantity and quantity unit."}
        try:
            quantity_value = Decimal(str(quantity))
            unit_id = int(quantity_unit_id)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Reviewed intake quantity and unit must be valid.") from exc
        product_id = int(item["product_id"])
        if not quantity_value.is_finite() or quantity_value <= 0 or quantity_value > MAX_INTAKE_QUANTITY or unit_id < 1:
            return {"status": "FAILED", "error": "Reviewed intake quantity and unit must be positive and bounded."}
        if product_id in product_ids:
            return {"status": "FAILED", "error": "Duplicate product rows require review before intake."}
        product_ids.add(product_id)
        rows.append({
            "product_id": product_id,
            "amount": format(quantity_value, "f"),
            "qu_id": unit_id,
        })
    if not rows:
        return {"status": "FAILED", "error": "Intake preview has no items."}
    return {
        "status": "READY_TO_APPLY",
        "requires_confirmation": True,
        "receipt_fingerprint": preview.get("receipt_fingerprint"),
        "items": rows,
        "canonical_target": "Grocy stock intake",
        "writes_performed": False,
        "reconcile_before_retry": True,
    }
