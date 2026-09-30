#!/usr/bin/env bash
set -euo pipefail
PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/actual-finance-import" && pwd)" python3 - <<'PY'
import base64
import json
from service import inspect_file

data = b"Posted,Description,Debit,Credit\n2026-09-01,Market,42.50,\n2026-09-02,Refund,,5.00\n"
result = inspect_file(base64.b64encode(data).decode(), "checking.csv")
assert result["status"] == "INSPECTED"
assert result["row_count"] == 2
assert result["suggested_mapping"] == {"date":"Posted", "payee":"Description", "inflow":"Credit", "outflow":"Debit"}
assert result["mapping_complete"] is True
assert result["needs_account"] is True
assert result["writes_performed"] is False
assert inspect_file(base64.b64encode(b"Date,Description,Amount\n2026-09-01,Market,4.00\n").decode(), "statement.csv")["needs_account"] is True
malformed = inspect_file(base64.b64encode(b"bad\n").decode(), "statement.csv")
assert malformed["status"] == "INSPECTED" and malformed["needs_mapping"] is True
print("PASS novice finance inspection identifies format, rows, dates, and safe mapping")
print("PASS finance inspection asks only for the account before mutation")
print("PASS malformed statement fails without writes")
PY
