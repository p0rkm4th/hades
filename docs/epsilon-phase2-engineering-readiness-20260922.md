# HADES Epsilon Phase 2 — Engineering Readiness

Date: 2026-09-22

## Authority gate

Backup Verification, Low Inventory Summary, and Weekly Household Summary are
implemented as typed read-only templates, but production promotion is disabled.
No Phase 2 production schedule was created or enabled. Household creation,
external notifications, mutations, remediation, Agent Zero, finance, and Home
Assistant remain outside this work.

## Engineering evidence

- Backup evidence uses fixed operator-owned HADES and `hades-infra` Git bundle
  targets. Real protected artifacts passed SHA-256 and local `git bundle verify`.
- Backup states cover valid, stale, missing, checksum mismatch, invalid bundle,
  and unavailable custody.
- Grocy remains the inventory authority. The live canonical `/api/stock` probe
  returned HTTP 200; minimum-stock semantics use Grocy product fields.
- Weekly composition performs an authorization check per source and retains
  bounded summary history only.
- Shared lifecycle supports intent/preview/confirmation, owner-only creation,
  staging, idempotency, edit/delete/pause/resume/run controls, and
  reconcile-before-retry after unknown mutations.

## Disabled acceptance harness

`scripts/dom-epsilon-phase2-staged.js --plan` describes the authenticated matrix:
Owner, Household A, Household B; desktop, 768x1024, 390x844, and 320x568;
preview, confirmation, inventory, inspect, run-now, pause, resume, edit,
delete, history, sharing, and revocation. The default harness mode asserts
that production enablement remains false and that unauthorized capabilities are
not advertised.

Canonical fixture catalog: `config/epsilon-phase2-fixtures.json`.

## Verification

Passing suites:

- `scripts/test-automation-abstraction.sh`
- `scripts/test-health-watch-contract.sh`
- `scripts/test-epsilon-workflow-contract.sh`
- `scripts/test-epsilon-workflow-artifact.sh`
- `scripts/test-epsilon-phase2-contracts.sh`

## Revisions

- Starting HADES revision: `11ec2eb` (accepted Server Health Watch canary)
- Starting `hades-infra` revision: `bf648f5`
- Ending HADES revision: recorded by the commit containing this report
- Ending `hades-infra` revision: unchanged, `bf648f5`

## Readiness

```text
PHASE 2 ENGINEERING
    READY

LIVE PROMOTION
    AWAITING MANNY / ORC AUTHORIZATION
```

Upon approval, enable one typed template at a time and run its real
authenticated DOM/failure campaign before enabling the next.
