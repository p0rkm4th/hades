#!/usr/bin/env bash
set -euo pipefail

# Synthetic owner/household dogfood for the preview-only finance file MCP
# surface. The fake Actual authority is deliberately tiny and canonical; the
# HADES-side code never owns a transaction ledger.
PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}" )/../integrations/actual-finance-import" && pwd)" \
python3 - <<'PY'
import base64
import json

from service import preview_apply_request, preview_file


csv_data = (
    "Posted,Description,Debit,Credit\n"
    "2026-09-01,Market,42.50,\n"
    "2026-09-02,Refund,,5.00\n"
).encode()
mapping = {"date": "Posted", "payee": "Description", "inflow": "Credit", "outflow": "Debit"}


def request(user, action, **kwargs):
    if user != "alpha":
        return {"status": "FAILED", "error": "Finance import is owner-only."}
    if action == "preview":
        return preview_file(base64.b64encode(csv_data).decode(), "checking.csv", "account-checking", json.dumps(mapping))
    if action == "apply":
        return preview_apply_request(kwargs["preview_json"], confirm=kwargs.get("confirm", False))
    raise AssertionError(action)


class SyntheticActual:
    canonical_rows = []

    def __init__(self):
        self.timeout_after_write = False

    def import_transactions(self, rows):
        existing = {row["imported_id"] for row in self.canonical_rows}
        self.canonical_rows.extend(row for row in rows if row["imported_id"] not in existing)
        if self.timeout_after_write:
            raise TimeoutError("response lost after canonical write")
        return {"status": "SUCCEEDED", "canonical_source": "Actual Budget"}

    def read_by_imported_id(self, imported_ids):
        return [row for row in self.canonical_rows if row["imported_id"] in set(imported_ids)]


actual = SyntheticActual()
preview = request("alpha", "preview")
assert preview["status"] == "PREVIEW"
assert preview["requires_confirmation"] is True
assert preview["new_count"] == 2

assert request("beta", "preview")["status"] == "FAILED"
assert request("alpha", "apply", preview_json=json.dumps(preview), confirm=False)["status"] == "FAILED"
plan = request("alpha", "apply", preview_json=json.dumps(preview), confirm=True)
assert plan["status"] == "READY_TO_APPLY"
assert plan["writes_performed"] is False

first = actual.import_transactions(plan["transactions"])
assert first == {"status": "SUCCEEDED", "canonical_source": "Actual Budget"}
assert len(actual.canonical_rows) == 2

duplicate_preview = preview_file(
    base64.b64encode(csv_data).decode(), "checking.csv", "account-checking", json.dumps(mapping),
    json.dumps(actual.canonical_rows),
)
assert duplicate_preview["duplicate_count"] == 2
assert preview_apply_request(json.dumps(duplicate_preview), confirm=True)["status"] == "NOOP_DUPLICATES"

# A transport timeout after Actual accepted the rows is unknown, not failed.
second_data = b"Posted,Description,Amount\n2026-09-03,Pharmacy,-12.00\n"
second_preview = preview_file(
    base64.b64encode(second_data).decode(), "checking.csv",
    "account-checking",
    json.dumps({"date": "Posted", "payee": "Description", "amount": "Amount"}),
)
second_plan = preview_apply_request(json.dumps(second_preview), confirm=True)
actual.timeout_after_write = True
try:
    actual.import_transactions(second_plan["transactions"])
except TimeoutError:
    outcome = "OUTCOME UNKNOWN"
else:
    raise AssertionError("synthetic timeout did not occur")
assert outcome == "OUTCOME UNKNOWN"
reconciled = actual.read_by_imported_id(
    [row["imported_id"] for row in second_plan["transactions"]]
)
assert len(reconciled) == 1
assert len(actual.canonical_rows) == 3
assert actual.canonical_rows[-1]["payee"] == "Pharmacy"

print("PASS Alpha finance preview, confirmation, canonical Actual import shape")
print("PASS Beta finance import denied without owner scope")
print("PASS duplicate import becomes NOOP after canonical reconciliation")
print("PASS timeout-after-write is OUTCOME UNKNOWN and reconciles without replay")
PY
