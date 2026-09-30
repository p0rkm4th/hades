# HADES Epsilon Phase 2 Limited Production Dogfood — Checkpoint

Date: 2026-09-23

This is an engineering checkpoint, not a Phase 2 closure verdict.

## Live capabilities

- Backup Verification: owner-created, fixed HADES/Infrastructure targets, private n8n runner, HADES-local results.
- Low Grocery Summary: owner-created, current Grocy read, fixed weekly graph, read-only.
- Weekly Household Summary: owner-created, fixed sources limited to Grocy/Low Inventory, Server Health Watch, and Backup Verification.

No arbitrary n8n graph, arbitrary HTTP, Code/shell/SSH, external notification, mutation, remediation, finance, Home Assistant, or Agent Zero automation was enabled.

## Evidence completed

- Real authenticated Owner DOM creation, confirmation, inspection, run-now, pause, resume, bounded edit, history, and deletion for Backup Verification.
- Real authenticated mobile DOM run for Backup Verification at 390x844 and 320x568 for Weekly Summary.
- Backup fixtures: HEALTHY, MISSING, FAILED/checksum mismatch, STALE, and SOURCE_UNAVAILABLE.
- Fixed custody restored after every reversible fixture; final source verification is HEALTHY.
- Grocy current-state run, source-unavailable run, recovery run, and no-minimum metadata semantics.
- Weekly partial result after Grocy outage: groceries unavailable while server and backup sections remained available.
- Household A shared Grocery/Weekly access; Household B denied without protected-data disclosure.
- Runtime server-health revocation removed the Server section from Household A's next Weekly Summary.
- Workflow-share revocation removed Household A's Grocery access.
- n8n restart preserved typed workflow IDs, schedules, and lifecycle mappings.
- n8n outage returned an uncertain/unavailable automation result while direct Grocy remained available.
- Open WebUI background title/tag/follow-up task prompts are excluded from typed lifecycle routing; real confirmations no longer get misclassified as task prompts.
- Commit `1a1afc4` binds typed pending confirmations to the conversation's first authenticated user turn rather than the user-scoped gateway key. The real two-tab DOM race now resolves independently: the resume tab enabled Backup Check and the pause tab paused it.
- Commit `9497445` adds a current-state check before applying a pending mutation; an old confirmation now refuses to act on an automation deleted or changed in another tab.
- Commit `30427dd` adds persisted pending-action inspection and prevents stale confirmations from being consumed by the managed-server route; `9ae43ef` reconciles a deletion that completed in n8n even if the HADES-side mutation response became uncertain.
- A controlled authenticated stale-tab run now produced: deletion in the other tab, followed by `That Backup Check no longer exists in the current HADES state, so I did not apply the old confirmation.` The fixture also exposed follow-up restoration ambiguity, so it remains regression evidence rather than closure evidence.
- The runner failure-locality checks were repeated live: n8n stopped produced an uncertain Backup Check result while Grocy remained available; Grocy stopped produced `source unavailable` for Low Grocery Summary; both dependencies were restored successfully.
- Mixed runner load accepted nine concurrent executions across Backup Verification, Low Inventory, and Weekly Summary. n8n remained healthy at approximately 434 MiB of its 768 MiB limit.
- The authenticated discovery matrix completed for Owner, Household A, and Household B at desktop, 768x1024, 390x844, and 320x568. Owner sees the active Infrastructure Backup Check; unshared household accounts see no protected Backup Check.
- Backup discovery now lists all active approved targets and excludes deleted historical records. Sequential double-confirmation through the authenticated DOM applied the first pause once and rejected the second confirmation without another mutation; the two-tab race still resolves independently.
- Backup HADES-local transition persistence is now wired through the bounded verification service. Live checksum-mismatch and recovery runs recorded FAILED and HEALTHY transition notifications without duplicate same-state rows; UI notification-history phrasing still needs final regression coverage.
- Stable DOM harness diagnostics are now opt-in (`HADES_DOM_DEBUG=1`); normal runs wait for chat requests and background task activity to settle before asserting results.

## Remaining before closure

- Complete the full Owner/Household A/Household B DOM matrix across desktop, tablet, 390x844, and 320x568.
- Complete stale-conversation and double-confirmation evidence; the multi-tab race and one stale-tab deletion/rejection run are repaired/verified, with repeated restoration and regression coverage still required.
- Complete Backup notification transition/dedup evidence through HADES-local delivery.
- Complete Weekly history/provenance and recipient-specific section audit.
- Complete controlled mixed long soak with resource/Core measurements and crash recovery.
- Restore/record final explicit sharing policy and produce the required closure report.

## Current verdict

```text
PHASE 2 ENGINEERING    IN PROGRESS
LIVE PROMOTION         ACTIVE FOR APPROVED TEMPLATES
PHASE 2 VERDICT        NOT YET GREEN
```
