# HADES PERSISTENT TASK / AUTONOMY SUBSTRATE ALPHA

## 1. Starting and ending revisions

- Starting runtime revision: `72a5dc0` provenance record; the prior live task surface stopped at proposal/create/wait/replan/cancel.
- Ending source HEAD: `6e8a97aa3d432186decaa688325ab569a17c81fe`.
- Ending runtime payload: `hermes/sitecustomize.py` SHA-256 `337e6f1a5ba1f5f652abf574d82f96af1ad0395f2b5d7acc08a03b3293678b35`; the reconciled tree and production overlay match this hash — `LIVE VERIFIED`.
- Infra HEAD: `bf648f52f5ab0e4da9ebd811f9ccc6866cf5341a` — `REPOSITORY VERIFIED` and present in the prior provenance record.
- Worktree: source code clean except this report and the advisor-report evidence delta, which are documentation-only changes at capture time — `REPOSITORY VERIFIED`.

## 2. Deployed provenance and trust closure

The Hermes unit is active on VM 802. The deployed file hash matches the ending runtime payload in both `$HADES_HOME/Hades-reconciled-b102dfd` and `$HADES_HOME/generated-full/config/overlay` — `LIVE VERIFIED`. The machine-readable provenance endpoint still reports the earlier code SHA `72a5dc0`; that field is stale relative to the independently matched deployed file hash and should be refreshed by the deployment recorder — `BROKEN` provenance freshness, not an execution failure.

Stale automation cleanup, fresh Hindsight recall, deployment hashing, and broad homelab composition were previously evidenced. Fresh Hindsight correctness is `LIVE VERIFIED`; freshness/latency remains an active concern because the retain worker experienced a long backlog. No production dependency was intentionally stopped for outage testing; source outage contracts and a bounded browser transport failure fixture are `REPOSITORY VERIFIED` / `LIVE VERIFIED` respectively.

## 3. Task substrate and lifecycle

The durable SQLite Task store provides schema versioning, revision-checked transitions, actor binding, event history, approval digests, execution ledger/idempotency keys, `OUTCOME_UNKNOWN` reconciliation, backup/restore, and isolation — `REPOSITORY VERIFIED` by `scripts/test-task-store.sh`.

The live owner-facing bounded goal is a harmless spaghetti-Friday planning task. Fresh authenticated DOM evidence and canonical SQLite read-back established:

`PROPOSED → READY → RUNNING → WAITING → AWAITING_APPROVAL → READY → RUNNING → COMPLETED`

The canonical row was `task-aa301d26585136f0f098`, status `COMPLETED`, revision `12`. Its event sequence included creation, plan acceptance, Grocy execution/result, wait request, fixed n8n wait scheduling, approval request/approval, and final Grocy execution/result. The final read was canonical Grocy `/api/stock`; no groceries were changed — `LIVE VERIFIED`.

Fresh-session inspection now reports the completed task and no further eligible action — `LIVE VERIFIED`. Replan invalidation and cancellation remain covered by the earlier authenticated DOM fixture — `LIVE VERIFIED`. The n8n graph is fixed and task-owned; arbitrary workflow creation is not exposed — `REPOSITORY VERIFIED` / `LIVE VERIFIED` for the bounded wait.

## 4. Authority and multi-user

Task visibility is actor-bound in the store; household sharing is not inferred. Approval is bound to task ID, revision, actor, action, resource, parameters, and digest. Replanning clears approval and execution target. Stale revisions fail closed — `REPOSITORY VERIFIED`.

Owner, Household A, and Household B persistent DOM coverage passed across desktop, 390×844, and 320×568. Private isolation, household Grocy read, Agent Zero denial, health-watch sharing/revocation, and stale-tab behavior are `LIVE VERIFIED` from the resumed soak. Finance, arbitrary n8n, remediation, external notification, HA mutation, and household workflow creation remain unauthorized — `OWNER-GATED` / `EXTERNAL-GATED` as applicable.

Important UX boundary: ambiguous bare `yes` and bare `resume` can be claimed by broader memory or Health Watch routes. Explicit task-scoped language is required for approval/continuation; no ambiguous phrase is treated as task authority — `LIVE VERIFIED` behavior, `PRODUCT LIMITATION` for natural-language ergonomics.

## 5. Reliability, restart, and failure locality

Idempotent execution, duplicate callback handling, unknown-outcome reconciliation, restart-safe SQLite persistence, backup/restore, revision conflicts, and failure locality are `REPOSITORY VERIFIED`. The live completed task survived a new authenticated browser conversation and was read back from canonical SQLite — `LIVE VERIFIED`.

Bounded browser transport abort produced a visible error, removed the stale Stop state, and accepted a fresh recovery turn — `LIVE VERIFIED`. Direct production dependency outage injection was not performed under the authority boundary — `UNVERIFIED` for live SearXNG/Grocy/inference/n8n outage behavior; corresponding bounded contracts are `REPOSITORY VERIFIED`.

## 6. Genuine dogfood verdict

The genuine persistent multi-system goal is `DOGFOOD GREEN` for the bounded Alpha shape: owner request, durable plan, canonical household read, typed n8n wait, revision-bound approval, explicit resume, canonical completion, fresh-session inspection, replan invalidation, and cancellation all have evidence. This does not authorize grocery mutation or proactive external action. Those remain outside Alpha’s authority — `LIVE VERIFIED` for the bounded read-only goal; `OWNER-GATED` for consequential household writes.

## 7. Alpha gates

| Gate | Classification | Evidence |
|---|---|---|
| Durable store/schema/backup/restore | REPOSITORY VERIFIED | `scripts/test-task-store.sh` |
| Create/plan/wait/resume/approve/replan/cancel/complete | LIVE VERIFIED | authenticated DOM plus SQLite event ledger |
| Actor binding/revision approval/isolation | REPOSITORY VERIFIED | Task store contracts and multi-user DOM |
| Idempotency/unknown outcome/restart recovery | REPOSITORY VERIFIED; live persistence LIVE VERIFIED | task-store contract and fresh-session read |
| Owner desktop/mobile DOM | LIVE VERIFIED | Alpha DOM and multiplayer soak |
| Genuine persistent multi-system goal | DOGFOOD GREEN | Grocy canonical read + bounded n8n wait |
| P0 | ZERO observed | targeted regressions and soak |
| P1 | ZERO observed in exercised scope | targeted regressions and soak |

## 8. Remaining blockers and authority changes

No new product-authority blocker prevents the bounded Alpha verdict. The deployment provenance recorder needs a refresh so its code SHA reflects the deployed task-lifecycle payload — `OWNER-EXTERNAL` only if the recorder is intentionally owner-gated; otherwise Luna can repair it autonomously. Hindsight freshness/latency remains the highest technical reliability concern. Live source-outage injection, finance, HA mutation, arbitrary n8n, Agent Zero automation, and external notifications remain out of scope and unauthorized.

## 9. Value and next milestone

Alpha now demonstrates durable, inspectable, bounded owner work rather than a synthetic task list. The next milestone is Beta: productize completed-task history and explicit task verbs in the UI, refresh machine provenance atomically on deployment, improve Hindsight queue latency, and add only owner-approved consequential executors after their authority contracts are specified.

## 10. Proof appendix

### CLAIM: deployed Hermes task runtime matches source payload
COMMAND: `sha256sum hermes/sitecustomize.py`; remote `sha256sum` of reconciled and overlay copies
RESULT: all three hashes `337e6f1a5ba1f5f652abf574d82f96af1ad0395f2b5d7acc08a03b3293678b35`; `hades-hermes.service` active
CLASSIFICATION: LIVE VERIFIED

### CLAIM: canonical Alpha task completed
COMMAND: remote SQLite read of task row and `task_events`
RESULT: task `task-aa301d26585136f0f098`, goal spaghetti Friday, status `COMPLETED`, revision `12`; event trail includes `N8N_WAIT_SCHEDULED`, `APPROVED`, final `EXECUTION_RESULT`
CLASSIFICATION: LIVE VERIFIED

### CLAIM: fresh owner DOM inspection works
COMMAND: authenticated browser prompt `What's happening with the spaghetti thing?` in a new context
RESULT: “The most recent task was … Status: completed; no further action is eligible.”
CLASSIFICATION: LIVE VERIFIED

### CLAIM: canonical active-task cleanup is complete
COMMAND: remote SQLite count of non-terminal rows
RESULT: `active 0` after synthetic fixture cleanup; historical completed/cancelled rows retained with backups
CLASSIFICATION: LIVE VERIFIED

### CLAIM: task contract remains green
COMMAND: `bash scripts/test-task-store.sh`
RESULT: lifecycle, revision-bound approval, idempotency, unknown reconciliation, isolation, backup, restore contract passes
CLASSIFICATION: REPOSITORY VERIFIED

### CLAIM: source worktree state
COMMAND: `git rev-parse HEAD`, `git status --short`
RESULT: HADES HEAD `6e8a97aa3d432186decaa688325ab569a17c81fe`; only documentation evidence delta remains unstaged at report capture
CLASSIFICATION: REPOSITORY VERIFIED
