#!/usr/bin/env bash
set -euo pipefail

# Credential-free end-to-end receipt workflow. OCR is represented by a
# deterministic upstream-shaped result; the canonical stock below is a small
# Grocy-shaped fixture, not a second household store.
python3 - <<'PY'
import importlib.util
import sys

path = "integrations/receipt-ocr/evidence.py"
spec = importlib.util.spec_from_file_location("receipt_evidence", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

lines = [
    {"text": "Synthetic Market", "confidence": 0.99},
    {"text": "2026-09-15", "confidence": 0.98},
    {"text": "Whole Milk $4.29", "confidence": 0.97},
    {"text": "Bananas $2.10", "confidence": 0.96},
    {"text": "Subtotal $6.39", "confidence": 0.99},
    {"text": "Tax $0.64", "confidence": 0.99},
    {"text": "Total $7.03", "confidence": 0.99},
]
evidence = module.normalize_ocr_lines(lines, source_ref="synthetic://receipt/clean")
assert evidence["status"] == "SUCCEEDED"
assert evidence["merchant"] == "Synthetic Market"
assert evidence["totals"]["total"] == "7.03"
assert [item["name"] for item in evidence["items"]] == ["Whole Milk", "Bananas"]

matches = [
    {"item_index": 0, "product_id": 10, "resolution": "EXACT"},
    {"item_index": 1, "product_id": 11, "resolution": "EXACT"},
]
preview = module.build_intake_preview(evidence, matches)
assert preview["status"] == "PREVIEW"
assert preview["requires_review"] is True
assert all(item["resolution"] == "EXACT" for item in preview["items"])

# OCR line prices are not stock quantities. A reviewed caller supplies the
# quantity/unit explicitly before an apply plan can exist.
reviewed = dict(preview)
reviewed["items"] = [
    dict(preview["items"][0], quantity="1", quantity_unit_id=1),
    dict(preview["items"][1], quantity="2", quantity_unit_id=1),
]
assert module.build_intake_apply_plan(reviewed)["status"] == "FAILED"
plan = module.build_intake_apply_plan(reviewed, reviewed=True, confirm=True)
assert plan["status"] == "READY_TO_APPLY"
assert plan["writes_performed"] is False
assert plan["reconcile_before_retry"] is True

# Minimal canonical Grocy-shaped fixture: only the reviewed apply layer may
# update it. This deliberately is not part of the OCR module.
stock = {10: 3, 11: 4}
submitted = set()
fingerprint = module.receipt_fingerprint(b"synthetic clean receipt")

def apply_once(request):
    if request["receipt_fingerprint"] in submitted:
        return {"status": "FAILED", "error": "duplicate requires reconciliation"}
    submitted.add(request["receipt_fingerprint"])
    for row in request["items"]:
        stock[row["product_id"]] += int(row["amount"])
    return {"status": "SUCCEEDED", "stock": dict(stock)}

plan["receipt_fingerprint"] = fingerprint
first = apply_once(plan)
assert first["status"] == "SUCCEEDED"
assert stock == {10: 4, 11: 6}

# A lost response after a completed canonical mutation is reconciled by
# observing the receipt fingerprint/stock before any retry; no blind replay.
uncertain = apply_once(plan)
assert uncertain["status"] == "FAILED"
assert stock == {10: 4, 11: 6}
reconciled = fingerprint in submitted and stock == {10: 4, 11: 6}
assert reconciled

# Low-confidence OCR remains review-only and cannot produce an exact intake
# row merely because a plausible product name exists.
partial = module.normalize_ocr_lines([
    {"text": "Synthetic Market", "confidence": 0.99},
    {"text": "BAN ORG $2.10", "confidence": 0.61},
])
partial_preview = module.build_intake_preview(partial, [{"item_index": 0, "product_id": 11, "resolution": "CANDIDATE"}])
assert partial_preview["status"] == "PREVIEW"
assert partial_preview["items"][0]["resolution"] == "REVIEW_REQUIRED"
assert module.build_intake_apply_plan(partial_preview, reviewed=True, confirm=True)["status"] == "FAILED"

print("PASS receipt OCR evidence -> review -> Grocy intake preview")
print("PASS explicit reviewed quantities and confirmation gate intake plan")
print("PASS canonical synthetic intake and duplicate reconciliation")
print("PASS low-confidence OCR cannot become an exact household intake")
PY
