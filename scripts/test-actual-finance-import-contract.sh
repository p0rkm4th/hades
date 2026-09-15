#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util
from pathlib import Path

path = Path("integrations/actual-finance-import/import_csv.py")
spec = importlib.util.spec_from_file_location("actual_import", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

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

repeat = module.build_preview(csv_data, mapping, existing_transactions=preview["transactions"])
assert repeat["duplicate_count"] == 2
assert repeat["new_count"] == 0

for bad in (
    b"Date,Payee,Amount\n2026-09-01,Store,0\n",
    b"Date,Payee,Amount\n2026-09-01,Store,not-money\n",
    b"Date,Payee,Amount\n2026-09-01,,3.00\n",
):
    try:
        module.build_preview(bad, {"date": "Date", "payee": "Payee", "amount": "Amount"})
    except module.ImportFormatError:
        pass
    else:
        raise AssertionError("invalid finance import accepted")

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
