# HADES finance bakeoff report

Date: 2026-09-12. Scope: disposable synthetic data only; no real accounts,
provider credentials, financial writes, or production finance enablement.

## Result

Actual Budget is selected as the canonical local-first finance application for
HADES synthetic integration. Firefly III is the runner-up. Finlynq and Ledgr
remain watchlisted. The decision is based on runtime behavior, not install
success alone.

## Candidates and evidence

| Candidate | Tested path | Result |
|---|---|---|
| Actual Budget | Server 26.9.0 with matched official `@actual-app/api` 26.9.0 | Imports, repeat reconciliation, reload, transfer-payee semantics, archive restore, and constrained HADES reads passed. |
| Firefly III | Core 6.6.6 plus Data Importer 2.3.4 | Mature REST-oriented fallback; importer and logical backup worked, but the four-service footprint is larger and full restore remained less exercised. |
| Finlynq | v3.4.1 | Fresh install, import, approval, persistence, and PostgreSQL restore worked; nearby same-merchant/same-amount data produced a likely false-positive duplicate and its broad MCP/API require a future read-only adapter. |
| Ledgr | v0.3.1 | Fresh PostgreSQL deployment and health worked; empty-state account creation required provider linking, so synthetic import was blocked without using prohibited provider credentials. |

## Semantic findings

The deterministic fixture covered 24 rows across three batches, repeats,
corrections, refunds, recurring charges, and transfer/card activity. Actual's
global import identity means transfer-pair rows must not share one external
ID; its supported transfer-payee path correctly creates linked counterparts
without treating the transfer as spending. This is documented as an import
adapter constraint. Recurring and category state remain canonical in Actual;
HADES creates no shadow ledger.

## HADES surface and security

The HADES adapter exposes only `finance_accounts`,
`finance_transactions`, and `finance_status` over stdio MCP. It delegates to
the official Actual client and exposes no transaction/account/budget/provider
mutation, reconciliation write, sync trigger, or money movement. The owner
DOM selected the isolated staged model, returned the synthetic Checking
balance `$3,395.36`, and a fresh reload retained the result. The canonical
Actual helper independently returned the same balance. An unavailable-server
probe produced an explicit failure and no fabricated success.

## Recovery and footprint

Actual's native archive and selected-state restore passed; Finlynq PostgreSQL
restore passed; Firefly and Ledgr logical dumps were created, with deeper
row-level restore still open. Directional idle memory was approximately Actual
48 MiB, Finlynq 148 MiB, Ledgr 138 MiB, and Firefly plus importer 245 MiB.

## Production architecture and gates

`statement files or a future provider → Actual Budget → small read-only
adapter → Hermes → HADES`. Actual remains independently usable. Production
requires explicit owner approval of Actual as canonical, real historical-file
import, and later any SimpleFIN/provider connection. Until those approvals,
finance remains synthetic-only and no production connector is enabled.

Reevaluate on an Actual major migration, client/server incompatibility,
read-only boundary failure, restore failure, or materially safer Firefly
import/API evidence.
