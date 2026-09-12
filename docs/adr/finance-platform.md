# ADR: Synthetic finance-platform bakeoff

**Status:** SELECT WITH CONDITIONS  
**Date:** 2026-09-12  
**Decision scope:** disposable synthetic staging only; no owner finance data,
provider links, or financial writes

## Decision

Select **Actual Budget** as the provisional canonical finance platform for
HADES, subject to a read-only integration proof and a complete synthetic import
acceptance. Keep **Firefly III** as the fallback. Keep **Finlynq** and **Ledgr**
on the watchlist until their material acceptance and security gaps are resolved.
This is not authorization for production finance deployment.

## Candidates and tested releases

| Candidate | Tested release/path | Runtime result | Decision result |
|---|---|---|---|
| Actual Budget | official `actualbudget/actual-server:sha-d5d0b66-alpine`, UI reported v26.9.0 | Healthy, password bootstrap/login worked, native data archive restored into a second disposable instance; normal UI imports Actual budget files, not generic CSV | SELECT WITH CONDITIONS |
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

## Backup / restore

Disposable native artifacts were created for all four candidates. Actual's
data archive was started as a second server and returned HTTP 200. Finlynq's
PostgreSQL dump restored into a clean disposable PostgreSQL instance with 69
public tables. Firefly and Ledgr logical dumps were successfully created; a
full row-level restore acceptance remains part of the conditions below.

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
prove candidate behavior, not HADES integration. The selected integration must
support only account/balance/transaction/category/recurring/budget reads plus
freshness metadata. It must not expose transaction edits, account edits,
provider linking, reconciliation writes, or money movement.

## Conditions before promotion

1. Resolve the Actual client/server migration mismatch, then import the same
   fixture through an Actual-compatible path, including repeat import and
   transfer semantics.
2. Implement or configure a small read-only Hermes adapter over the official
   Actual API, with failure and stale-state responses.
3. Prove the read path through the HADES owner UI against synthetic canonical
   Actual state, then reload and restart.
4. Complete row-level restore verification for the selected state and record
   backup credential/key dependencies separately.
5. Re-evaluate Firefly if Actual's import/API path cannot meet these contracts.

## Production gates

Explicit owner authorization is required before importing real historical
files, connecting SimpleFIN/Plaid, storing provider credentials, or enabling
any finance write. Real owner finance remains `BLOCKED BY OWNER AUTHORIZATION`.

## Re-evaluation triggers

Re-evaluate on an Actual major-version migration, a material API-client
breaking change, inability to enforce read-only semantics, failed restore, or
evidence that Firefly's importer/API provides materially safer canonical
behavior.
