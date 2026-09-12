# ADR: Synthetic finance-platform bakeoff

**Status:** SELECTED FOR SYNTHETIC HADES INTEGRATION; PRODUCTION GATED
**Date:** 2026-09-12  
**Decision scope:** disposable synthetic staging only; no owner finance data,
provider links, or financial writes

## Decision

Select **Actual Budget** as HADES's canonical finance platform for synthetic
integration. The constrained read-only adapter and owner-path proof are now
complete. Keep **Firefly III** as the fallback and **Finlynq**/**Ledgr** on the
watchlist. This is not authorization for production finance deployment.

## Candidates and tested releases

| Candidate | Tested release/path | Runtime result | Decision result |
|---|---|---|---|
| Actual Budget | official `actualbudget/actual-server:26.9.0`, digest pinned; matched `@actual-app/api` 26.9.0 | Healthy, synthetic import/repeat/reload and transfer-payee linking passed; native archive and selected-state restore passed; HADES read-only MCP owner path returned the canonical balance and survived reload | SELECTED |
| Firefly III | `fireflyiii/core:latest`, UI reported v6.6.6; `fireflyiii/data-importer:latest` reported v2.3.4 | Core healthy; separate importer healthy; registration and manual onboarding worked; API unauthenticated access correctly redirected | FALLBACK |
| Finlynq | `ghcr.io/finlynq/finlynq:latest`, source tag v3.4.1 | Fresh PostgreSQL migrations, registration, manual accounts, staged import, approval, persistence, and backup restore worked | WATCHLIST |
| Ledgr | `ghcr.io/kentaniguchi-r/ledgr:latest`, source tag v0.3.1 | Fresh PostgreSQL migrations and health worked; empty-state UI offers bank linking but no manual account route, blocking synthetic CSV import without provider credentials; MCP requires auth | WATCHLIST |

## Synthetic fixture

`test-data/finance-bakeoff/` contains 24 rows across three deterministic
batches, 17 unique external IDs, three transfer pairs, repeated imports, a
nearby same-merchant/same-amount transaction, a refund, recurring charges,
and corrections. It is not owner data.

## Runtime findings

- Finlynq accepted Batch A as a visible 12-row manual-review import. On a
  repeated import, the UI reported nine duplicate Checking rows skipped while
  the three rows belonging to other accounts were routed to those accounts.
  Batch B reported five duplicates out of seven rows: four fixture overlaps
  plus the intentional nearby Copper Diner transaction, yielding a likely
  false-positive deduplication. Its interface exposes a two-gate
  staging/reconciliation workflow.
- Finlynq's first-party MCP is broad and includes writes; its documented
  bearer API key is unscoped. A future HADES adapter would need a technically
  enforced read-only boundary rather than exposing that key directly.
- Ledgr's documented OAuth scopes (`ledgr:read`, `ledgr:write`, `ledgr:sync`)
  are promising, but the current empty-state path requires Plaid/SimpleFIN to
  create the first account. No provider credentials were used.
- Firefly requires a separate Data Importer service for the evaluated file
  workflow, increasing operational footprint but preserving a mature REST
  surface.
- Actual is the smallest and most local-first candidate, but its official
  programmatic access is the `@actual-app/api` Node client rather than an HTTP
  REST API. The HADES read-only surface therefore needs a small adapter and
  must not expose the full client as a generic mutation tool. A staging probe
  using the published 26.9.0 client authenticated and enumerated budgets, but
  loading a downloaded synthetic budget failed with `out-of-sync-migrations`:
  the staged server budget contains migration IDs absent from the client
  bundle. This is an open client/server compatibility gate.
- A same-day `@actual-app/api` nightly build (`26.10.0-nightly.20260912`)
  included the missing migration. Against the same disposable server it
  downloaded and loaded the synthetic budget, created a Synthetic Checking
  account, synced it, and a fresh client runtime re-downloaded the budget and
  recovered the account. This proves the supported API shape is viable, but
  production must pin a matching, supported server/client pair rather than
  adopt a moving nightly channel.
- The stable `26.9.0` image and client then passed the matching-pair probe in a
  fresh disposable server. Batch A imported 12 rows with zero errors across
  Checking, Rainy Day Savings, and Synthetic Card; repeating the import added
  zero rows and returned three reconciliation updates. Sync and a fresh
  runtime download recovered all 12 rows. Actual's import identity is global
  enough that the fixture's intentionally shared external IDs for transfer
  pairs collapse counterpart rows; the correct supported transfer path is to
  use Actual's transfer payee with `addTransactions`, which created and linked
  the synthetic Checking-to-Savings counterpart in a separate proof budget.

## Backup / restore

Disposable native artifacts were created for all four candidates. Actual's
data archive was started as a second server and returned HTTP 200. The selected
Actual synthetic budget also exported to a 26,771-byte archive and restored
into a clean offline client with identical per-account transaction counts.
Finlynq's PostgreSQL dump restored into a clean disposable PostgreSQL instance
with 69 public tables. Firefly and Ledgr logical dumps were successfully
created; their full row-level restore acceptance remains open.

## Operational footprint

Approximate idle container memory at measurement time:

| Candidate | Services | Approximate memory |
|---|---:|---:|
| Actual | 1 | 48 MiB |
| Finlynq | 2 | 148 MiB |
| Ledgr | 2 | 138 MiB |
| Firefly + importer | 4 | 245 MiB |

These measurements are directional, not a selection criterion by themselves.

## HADES integration/security result

No finance tool is enabled in production HADES. The synthetic owner-UI tests
prove the isolated HADES integration against canonical Actual state. The
selected integration must
support only account/balance/transaction/category/recurring/budget reads plus
freshness metadata. It must not expose transaction edits, account edits,
provider linking, reconciliation writes, or money movement.

## Conditions before production promotion

1. Keep the matched supported Actual 26.9.0 server/client revision pinned.
2. Keep the small adapter read-only and outside production until owner approval.
3. Obtain explicit authorization for real historical imports and any provider
   connection; none is authorized by this bakeoff.
4. Record backup credential/key dependencies in the private deployment record.
5. Re-evaluate Firefly if Actual's import/API path cannot meet future contracts.

## Production gates

Explicit owner authorization is required before importing real historical
files, connecting SimpleFIN/Plaid, storing provider credentials, or enabling
any finance write. Real owner finance remains `BLOCKED BY OWNER AUTHORIZATION`.

## Re-evaluation triggers

Re-evaluate on an Actual major-version migration, a material API-client
breaking change, inability to enforce read-only semantics, failed restore, or
evidence that Firefly's importer/API provides materially safer canonical
behavior.
