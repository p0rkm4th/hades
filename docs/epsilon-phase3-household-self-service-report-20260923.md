# HADES EPSILON PHASE 3 — HOUSEHOLD SELF-SERVICE REPORT

**Evidence timestamp:** 2026-09-23, America/Chicago
**Boundary:** staged typed self-service only. No unrestricted household production creation was enabled. No Phase 3 n8n workflows were created.

> **Authorization status superseded (2026-09-25):** Scotty's Owner Away policy
> grants standing authorization for a bounded production canary using only
> Server Health Watch, Low Inventory Summary, Weekly Household Summary, and
> Backup Verification. The older Manny decision packet and approval gate below
> are historical. This does not mean the canary is implemented or running;
> current identity/resource checks, recovery behavior, authenticated
> acceptance, and rollback still need to pass before activation.

## Starting and ending revisions

| Repository | Starting revision | Ending revision | State |
|---|---|---|---|
| HADES | `e609fec` | `c3c8485` | `REPOSITORY VERIFIED`; local `main` remains ahead of public `origin/main`; current staged work is committed |
| hades-infra | `bf648f5` | `bf648f5` | `REPOSITORY VERIFIED`; clean `main`, no upstream configured |

The deployed HADES guest service runs from `$HADES_HOME/Hades-reconciled-b102dfd` plus the generated overlay. The exact deployed Git SHA remains `UNVERIFIED`; deployed file hashes were checked after the latest staged deployment. Hermes service is active after restart.

## Approved template catalog

- **Server Health Watch:** `LIVE VERIFIED` in staged DOM for authorized Core health; read-only, HADES-local notification, no restart/remediation.
- **Low Inventory Summary:** `LIVE VERIFIED` in staged DOM for Grocy-authorized users; read-only canonical Grocy source, no grocery mutation or threshold changes.
- **Weekly Household Summary:** `LIVE VERIFIED` preview for Household A; sections were exactly Server Health, Groceries, and Backup Verification for A’s explicit grants. Household B’s catalog exposed only Groceries — `LIVE VERIFIED`.
- **Backup Verification:** `LIVE VERIFIED` as an authority-filtered catalog option for A’s explicit `backup.evidence`; B did not receive it. This is deployment-specific authority, not a household default.

Arbitrary n8n graphs, workflow JSON, shell, credentials, arbitrary HTTP, external notifications, finance, Home Assistant, remediation, and Agent Zero remain excluded — `REPOSITORY VERIFIED` + `LIVE VERIFIED` staged response boundary.

## Ownership and control

- Records carry `creator_subject_id`, `owner_subject_id`, `template_type`, `resource_scope`, `shared_with`, bounded interval/configuration, timestamps, enabled/status, and manual-run count — `REPOSITORY VERIFIED`.
- Creator owns and can view, run, pause, resume, edit interval, share, revoke share, and delete while current resource authority remains valid — `SYNTHETIC VERIFIED` and `LIVE VERIFIED` for A’s Weekly lifecycle.
- Template identity and resource identity cannot be changed through edit; a different resource/template requires a new preview and confirmation — `SYNTHETIC VERIFIED`.
- Owner oversight is staged: owner DOM metadata inventory showed owner/template/schedule/status/resource class without protected result data; owner disabled an A-owned workflow after explicit confirmation — `LIVE VERIFIED`.
- Owner/admin disable changes only automation metadata; it does not mutate the underlying resource — `SYNTHETIC VERIFIED` + `LIVE VERIFIED`.

## Quotas and bounded configuration

| Limit | Value | Evidence |
|---|---:|---|
| Owner active records | 10 | `REPOSITORY VERIFIED`, unit-tested |
| Household active records | 5 | `REPOSITORY VERIFIED`, unit-tested |
| Template/resource duplicates | 1 active | `SYNTHETIC VERIFIED`; concurrent race test admitted one |
| Minimum interval | 5 minutes | `SYNTHETIC VERIFIED`; 2-minute edit rejected |
| Maximum interval | 7 days | `SYNTHETIC VERIFIED` |
| Manual run allowance | 2 per staged record before schedule window | `SYNTHETIC VERIFIED`; third run rejected |
| Concurrent quota race | one-record quota remained one record under two simultaneous admissions | `SYNTHETIC VERIFIED` |

Quota messages are human-readable. Unsupported fields such as n8n JSON and unapproved Weekly sections are rejected — `SYNTHETIC VERIFIED`.

## Authority

- **Creation:** approved template + current actor authority + bounded fields are required — `SYNTHETIC VERIFIED`; A/B DOM proof completed.
- **Resource checks:** explicit subject/resource grants only. A has Core health, Grocy, and backup evidence; B has Grocy only in the current staged deployment — `LIVE VERIFIED` from auth/config and DOM.
- **Execution:** resource authority is rechecked at control time; revoked records become disabled/authorization-lost — `SYNTHETIC VERIFIED` and stale-session DOM proof.
- **Delivery:** staged Phase 3 creates no n8n delivery and emits no external notification. Future promotion must recheck recipient authority — `DEFERRED` / `OWNER-GATED` by design.
- **Revocation:** resource revocation disables owned records; identity removal disables owned records, clears their shares, and preserves bounded metadata for cleanup — `SYNTHETIC VERIFIED`.
- **Removed user:** inactive authority cannot list or run; `revoke_actor` prevents immortal service-account behavior — `SYNTHETIC VERIFIED`. Real LLDAP removal was not performed against real identities.
- **Sharing:** A shared Low Grocery with B; B could list and run it; A revoked sharing; B then saw no staged automations — `LIVE VERIFIED`. B cannot edit/pause/delete/share — `SYNTHETIC VERIFIED`.
- **No authority transfer:** sharing recipient must already possess every resource in the automation scope. A server-watch share to B was rejected — `SYNTHETIC VERIFIED`.

## DOM acceptance

| Actor / surface | Evidence |
|---|---|
| Owner | `LIVE VERIFIED`: metadata inventory and explicit admin disable without resource mutation |
| Household A | `LIVE VERIFIED`: catalog, Server Health create/confirm, Low Grocery create/confirm/share/revoke, Weekly create/confirm, edit, pause, resume, delete |
| Household B | `LIVE VERIFIED`: filtered catalog, unauthorized server denial, shared Low Grocery run, post-revocation disappearance |
| Desktop | `LIVE VERIFIED` across the above journeys |
| 390×844 | `LIVE VERIFIED`: A catalog discovery |
| 320×568 | `LIVE VERIFIED`: B catalog discovery |
| Stale session | `LIVE VERIFIED`: A created a watch, resource authority was revoked out-of-band, same old tab’s run was denied and the record was disabled |
| Stale/cross-user confirmation | `SYNTHETIC VERIFIED`: preview actor binding/hash and unit test |
| Double submit / idempotency | `SYNTHETIC VERIFIED`: request-key retry reconciles to one record; duplicate admission rejected |

One route collision was found and fixed during acceptance: “delete my weekly household summary” had been intercepted by managed-server language because of the words “delete” and “my.” The Phase 3 language guard now routes typed automation lifecycle requests first. Fresh DOM delete proof passed after redeploy — `LIVE VERIFIED`.

## Races and load

- **Quota race:** two concurrent admissions against a one-record quota produced one record — `SYNTHETIC VERIFIED`.
- **Cross-user race/isolation:** ownership and shared run-only checks reject B’s control of A’s record — `SYNTHETIC VERIFIED`.
- **Owner admin race semantics:** admin disable is serialized in SQLite and leaves resource state untouched — `SYNTHETIC VERIFIED`; live owner disable completed.
- **Synthetic household load:** 11 staged records (Owner 5, A 3, B 3) admitted in a temporary SQLite store in 6.43 ms total / 0.58 ms average; no production state was used — `SYNTHETIC VERIFIED`.
- **Live runtime baseline:** HADES guest snapshot after acceptance showed n8n `0.06% / 438.7 MiB`, Open WebUI `0.21% / 770.4 MiB`, Hindsight `0.35% / 2.096 GiB`, Agent Zero `0.12% / 1.315 GiB`; Hermes process `7.2% CPU / 2.2% memory` at capture — `LIVE VERIFIED` baseline, not a Phase 3 production execution load test.
- **n8n load impact:** `DEFERRED` because Phase 3 remains staged and intentionally creates no n8n graphs. Production canary load requires Manny authorization.

## Natural-language coverage

Fresh DOM coverage included clear, casual, and lifecycle language: “tell me if my server goes down,” “give me a weekly low grocery summary,” “make me the weekly household summary,” “what can I automate?”, “what automations do I have?”, “share my low grocery summary with household-b,” “revoke sharing,” “change … every 15 minutes,” “pause,” “resume,” and “delete.” Ambiguous/technical or unsupported requests fail closed. Broader typo/correction saturation is inherited from accepted Phase 2 evidence plus the targeted Phase 3 contracts — `HISTORICAL EVIDENCE` where not rerun.

## P0/P1/P2 assessment

- **P0:** zero found in the staged acceptance scope — `SYNTHETIC VERIFIED` + `LIVE VERIFIED`. No unauthorized resource creation, authority transfer, cross-user takeover, arbitrary execution, credential exposure, or resource mutation was observed.
- **P1:** zero found in the staged acceptance scope — `SYNTHETIC VERIFIED` + `LIVE VERIFIED`. Quota race, stale authority, identity removal, duplicate admission, and owner-admin metadata safety are covered.
- **P2 repaired:** inherited Phase 2 default over-grant, low-inventory share matching, managed-server/automation route collision, stale authorization wording, unsupported configuration acceptance, and missing create retry idempotency.
- **P2 remaining outside the Phase 3 gate:** the pre-existing owner health-watch store still contains duplicate unknown legacy watches. Cleanup is intentionally not performed as an evidence-only production mutation; it remains a product-hygiene follow-up.

## Production gate

**Production household creation: NOT YET AUTHORIZED.** The deployed flag remains `HADES_EPSILON_PHASE3_HOUSEHOLD_CREATION=staged`; no Phase 3 n8n workflow was created.

The engineering/synthetic acceptance boundary is ready for decision review. The remaining Phase 3 product decision is:

> Should household users be allowed to instantiate these already-approved, read-only templates only for resources they already have permission to access?

Manny’s decision packet is [epsilon-phase3-manny-decision-packet-20260923.md](epsilon-phase3-manny-decision-packet-20260923.md). It recommends retaining staged dogfood until the duplicate legacy health-watch state is reconciled and then authorizing, if desired, a limited canary—not unrestricted workflow creation.

## Still unauthorized

Arbitrary n8n, mutations, remediation, external notifications, Agent Zero automation, finance automation, Home Assistant automation, generic webhooks, arbitrary HTTP, shell/SSH, credentials, and ownership transfer remain unauthorized.

## Next roadmap review

If Manny approves a canary, enable it reversibly for synthetic A/B first, then run the already-tested focused DOM matrix and n8n load proof. If not approved, continue only independent work: legacy health-watch cleanup under owner authority, exact identity-group removal fixture, and better owner metadata UX. The next feature family should be separately decided; Phase 3 does not authorize external notifications or mutations.
