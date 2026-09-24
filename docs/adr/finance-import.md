# ADR: Local finance import preview

Status: **STAGED**

Actual Budget remains the canonical finance system. HADES may normalize a
local CSV into a deterministic preview and identify likely duplicates, but it
must not maintain a shadow ledger or write until a future adapter receives
explicit confirmation and delegates reconciliation to Actual's official
`importTransactions` path.

The preview requires an explicit mapping for date, payee, and either amount or
inflow/outflow. Ambiguous debit/credit rows, malformed amounts, empty required
fields, and empty files fail closed. Every row receives a stable file-bound
identity and retains its source row number. Existing canonical transaction
data is used only for duplicate classification.

Evidence: [`scripts/test-actual-finance-import-contract.sh`](../../scripts/test-actual-finance-import-contract.sh)
passes deterministic preview, duplicate detection, malformed-input rejection,
write-free confirmation-boundary checks, and a confirmation-gated
`importTransactions` request plan that skips known duplicates and requires
canonical reconciliation. A real Actual import and owner acceptance remain
authorization-gated.

The future authorized writer has a bounded reconciliation contract in
`integrations/actual-finance-import/executor.py`. It accepts an injected
canonical client, preflights existing `imported_id` values, passes
`reimportDeleted: false`, and always performs canonical read-back after an
attempt. Results are `SUCCEEDED`, `FAILED`, or `OUTCOME UNKNOWN`; the latter
requires reconciliation before any retry. `ImportRejected` is treated as a
definitive pre-write failure. This contract is synthetic-only until an owner
authorizes and supplies the real Actual client.
