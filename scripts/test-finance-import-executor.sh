#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/actual-finance-import" && pwd)" python3 - <<'PY'
from executor import ImportRejected, execute_import

rows = [{"date": "2026-09-15", "payee": "Market", "amount": "-42.50", "imported_id": "row-1"}]


class ActualFixture:
    def __init__(self):
        self.rows = []
        self.fail_after_write = False
        self.reject = False

    def read_imported(self, account_id, imported_ids):
        return [row for row in self.rows if row["account_id"] == account_id and row["imported_id"] in imported_ids]

    def import_transactions(self, account_id, incoming, options):
        assert options == {"reimportDeleted": False, "defaultCleared": False}
        if self.reject:
            raise ImportRejected("synthetic Actual rejection")
        self.rows.extend(dict(row, account_id=account_id) for row in incoming)
        if self.fail_after_write:
            raise TimeoutError("synthetic response loss")
        return {"added": [row["imported_id"] for row in incoming], "updated": [], "errors": []}


fixture = ActualFixture()
success = execute_import(fixture, "account-checking", rows)
assert success["status"] == "SUCCEEDED" and success["reconciled"] is True
assert success["writes_performed"] is True
assert execute_import(fixture, "account-checking", rows)["status"] == "NOOP_DUPLICATES"

fixture.fail_after_write = True
unknown_rows = [{"date": "2026-09-16", "payee": "Pharmacy", "amount": "-12.00", "imported_id": "row-2"}]
unknown = execute_import(fixture, "account-checking", unknown_rows)
assert unknown["status"] == "SUCCEEDED" and unknown["reconciled"] is True

fixture.reject = True
rejected = execute_import(fixture, "account-checking", [{"date": "2026-09-17", "payee": "Denied", "amount": "-1.00", "imported_id": "row-3"}])
assert rejected["status"] == "FAILED" and rejected["writes_performed"] is False
assert execute_import(fixture, "", rows)["status"] == "FAILED"
assert execute_import(fixture, "account-checking", [{"imported_id": "row-4"}])["status"] == "FAILED"
assert execute_import(fixture, "account-checking", [dict(rows[0]), dict(rows[0])])["status"] == "FAILED"

print("PASS Actual executor preflights duplicates and verifies canonical read-back")
print("PASS timeout after canonical write reconciles to success without replay")
print("PASS definitive rejection, missing target, and malformed/duplicate rows fail closed")
PY
