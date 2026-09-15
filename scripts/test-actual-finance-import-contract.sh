#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, "integrations/actual-finance-import")
path = Path("integrations/actual-finance-import/import_csv.py")
spec = importlib.util.spec_from_file_location("actual_import", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

service_spec = importlib.util.spec_from_file_location("finance_service", "integrations/actual-finance-import/service.py")
service = importlib.util.module_from_spec(service_spec)
sys.modules[service_spec.name] = service
service_spec.loader.exec_module(service)

csv_data = (
    "Posted,Description,Debit,Credit\n"
    "2026-09-01,Grocer,42.50,\n"
    "2026-09-02,Refund,,5.00\n"
).encode()
mapping = {"date": "Posted", "payee": "Description", "inflow": "Credit", "outflow": "Debit"}
preview = module.build_preview(csv_data, mapping)
assert preview["status"] == "PREVIEW"
assert preview["transaction_count"] == 2
assert [row["amount"] for row in preview["transactions"]] == ["-42.50", "5.00"]
assert preview["requires_confirmation"] is True
assert preview["writes_performed"] is False
assert len(preview["file_sha256"]) == 64
assert module.build_apply_request(preview)["status"] == "FAILED"
request = module.build_apply_request(preview, confirm=True)
assert request["status"] == "READY_TO_APPLY"
assert request["operation"] == "importTransactions"
assert request["writes_performed"] is False
assert request["reconcile_after_write"] is True
assert len(request["transactions"]) == 2

service_preview = service.preview_file(
    base64.b64encode(csv_data).decode(),
    "checking.csv",
    json.dumps(mapping),
)
assert service_preview["status"] == "PREVIEW"
service_request = service.preview_apply_request(json.dumps(service_preview), confirm=True)
assert service_request["status"] == "READY_TO_APPLY"
assert service_request["writes_performed"] is False
assert service.preview_file("not-base64", "checking.csv")["status"] == "FAILED"
assert service.preview_file(base64.b64encode(b"not a csv").decode(), "checking.csv", json.dumps(mapping))["status"] == "FAILED"
assert service.preview_file(base64.b64encode(b"!Type:Bank\nD09/01/2026\nT-3.00\nPStore\n^\n").decode(), "checking.qif")["native_import_required"] is True

repeat = module.build_preview(csv_data, mapping, existing_transactions=preview["transactions"])
assert repeat["duplicate_count"] == 2
assert repeat["new_count"] == 0
assert module.build_apply_request(repeat, confirm=True)["status"] == "NOOP_DUPLICATES"

for bad in (
    b"Date,Payee,Amount\n2026-09-01,Store,0\n",
    b"Date,Payee,Amount\n2026-09-01,Store,not-money\n",
    b"Date,Payee,Amount\n2026-09-01,Store,1e999999\n",
    b"Date,Payee,Amount\n2026-09-01,,3.00\n",
):
    try:
        module.build_preview(bad, {"date": "Date", "payee": "Payee", "amount": "Amount"})
    except module.ImportFormatError:
        pass
    else:
        raise AssertionError("invalid finance import accepted")

for bad_input, bad_mapping, bad_delimiter, bad_encoding in (
    ("not-bytes", {"date": "Date", "payee": "Payee", "amount": "Amount"}, ",", "utf-8"),
    (b"Date,Payee,Amount\n2026-09-01,Store,1.00\n", [], ",", "utf-8"),
    (b"Date,Payee,Amount\n2026-09-01,Store,1.00\n", {"date": "Date", "payee": "Payee", "amount": "Amount"}, "", "utf-8"),
    (b"Date,Payee,Amount\n2026-09-01,Store,1.00\n", {"date": "Date", "payee": "Payee", "amount": "Amount"}, ",", None),
):
    try:
        module.build_preview(bad_input, bad_mapping, delimiter=bad_delimiter, encoding=bad_encoding)
    except module.ImportFormatError:
        pass
    else:
        raise AssertionError("malformed finance preview input escaped")

for bad_mapping in (
    {"date": 1, "payee": "Payee", "amount": "Amount"},
    {"date": "Date", "payee": "Payee", "amount": None, "inflow": "Credit", "outflow": 2},
):
    try:
        module.build_preview(b"Date,Payee,Amount\n2026-09-01,Store,1.00\n", bad_mapping)
    except module.ImportFormatError:
        pass
    else:
        raise AssertionError("non-text finance mapping field escaped")

try:
    module.build_preview(
        b"Date,Payee,Debit,Credit\n2026-09-01,Store,1.00,2.00\n",
        mapping,
    )
except module.ImportFormatError:
    pass
else:
    raise AssertionError("ambiguous debit/credit row accepted")

print("PASS deterministic Actual CSV preview")
print("PASS duplicate import detection")
print("PASS finance import remains confirmation-gated and write-free")
print("PASS malformed and ambiguous rows fail closed")
PY
