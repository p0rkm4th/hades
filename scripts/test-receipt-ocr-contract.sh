#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path("integrations/receipt-ocr/evidence.py")
spec = importlib.util.spec_from_file_location("receipt_evidence", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

lines = [
    {"text": "Synthetic Market", "confidence": 0.99},
    {"text": "2026-09-14", "confidence": 0.98},
    {"text": "Whole Milk $4.29", "confidence": 0.98},
    {"text": "BAN ORG $2.10", "confidence": 0.61},
    {"text": "Subtotal $6.39", "confidence": 0.99},
    {"text": "Tax $0.64", "confidence": 0.99},
    {"text": "Total $7.03", "confidence": 0.99},
]
evidence = module.normalize_ocr_lines(lines, source_ref="synthetic://receipt/1")
assert evidence["status"] == "PARTIAL"
assert evidence["merchant"] == "Synthetic Market"
assert evidence["totals"] == {"subtotal": "6.39", "tax": "0.64", "total": "7.03"}
assert evidence["items"][0]["name"] == "Whole Milk"
assert evidence["items"][1]["needs_review"] is True
assert any("review" in warning.lower() for warning in evidence["warnings"])

preview = module.build_intake_preview(evidence, [
    {"item_index": 0, "product_id": 5, "resolution": "EXACT"},
    {"item_index": 1, "candidates": ["Bananas"]},
])
assert preview["status"] == "PREVIEW"
assert preview["items"][0]["product_id"] == 5
assert preview["items"][1]["resolution"] == "REVIEW_REQUIRED"
assert preview["requires_review"] is True
fingerprint = module.receipt_fingerprint(b"synthetic receipt image")
duplicate_preview = module.build_intake_preview(
    dict(evidence, receipt_fingerprint=fingerprint),
    [{"item_index": 0, "product_id": 5, "resolution": "EXACT"}],
    existing_fingerprints=[fingerprint],
)
assert duplicate_preview["status"] == "PREVIEW"
assert duplicate_preview["duplicate"] is True
assert any("already submitted" in warning for warning in duplicate_preview["warnings"])
assert duplicate_preview["receipt_fingerprint"] == fingerprint
assert module.build_intake_preview(dict(evidence, receipt_fingerprint=object()), [])["status"] == "FAILED"

reviewed_preview = dict(preview)
reviewed_preview["requires_review"] = False
reviewed_preview["items"] = [dict(preview["items"][0], quantity="2", quantity_unit_id=7)]
assert module.build_intake_apply_plan(reviewed_preview)["status"] == "FAILED"
ready_plan = module.build_intake_apply_plan(reviewed_preview, reviewed=True, confirm=True)
assert ready_plan["status"] == "READY_TO_APPLY"
assert ready_plan["writes_performed"] is False
assert ready_plan["items"] == [{"product_id": 5, "amount": "2", "qu_id": 7}]
assert module.build_intake_apply_plan(duplicate_preview, reviewed=True, confirm=True)["status"] == "FAILED"
missing_quantity = dict(reviewed_preview, items=[dict(preview["items"][0])])
assert module.build_intake_apply_plan(missing_quantity, reviewed=True, confirm=True)["status"] == "FAILED"
for bad_review in (
    dict(reviewed_preview, items=[dict(reviewed_preview["items"][0], quantity="not-a-number")]),
    dict(reviewed_preview, items=[dict(reviewed_preview["items"][0], quantity_unit_id="not-an-id")]),
    dict(reviewed_preview, items=[dict(reviewed_preview["items"][0], product_id="not-an-id")]),
):
    assert module.build_intake_apply_plan(bad_review, reviewed=True, confirm=True)["status"] == "FAILED"

bad_total = module.normalize_ocr_lines([
    {"text": "Shop", "confidence": 0.99},
    {"text": "Coffee $3.00", "confidence": 0.99},
    {"text": "Subtotal $3.00", "confidence": 0.99},
    {"text": "Tax $0.30", "confidence": 0.99},
    {"text": "Total $4.00", "confidence": 0.99},
])
assert any("does not match" in warning for warning in bad_total["warnings"])
assert module.normalize_ocr_lines([])["status"] == "FAILED"
assert len(module.receipt_fingerprint(b"same image")) == 64
print("PASS OCR line evidence normalization")
print("PASS uncertain receipt lines remain review-required")
print("PASS receipt Grocy intake is preview-only")
print("PASS duplicate receipt fingerprints remain review-only")
print("PASS reviewed OCR intake produces a write-free Grocy apply plan")
print("PASS OCR failure and total mismatch are explicit")
PY
