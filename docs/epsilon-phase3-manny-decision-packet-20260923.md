# Epsilon Phase 3 Manny Decision Packet

**State:** `STAGED`; unrestricted household workflow creation remains disabled.

## Decision requested

Approve or reject promotion of the typed household self-service catalog from the current non-mutating staged UI into an explicitly bounded production adapter. Promotion is not implied by implementation or by the evidence below.

## Approved catalog in this packet

| Template | Sources | Schedule bound | Effect | Notification |
|---|---|---:|---|---|
| Server Health Watch | explicitly granted `hades-core.health` sources | 5 minutes–7 days; default 10 minutes | read-only health observation | HADES-local only |
| Low Inventory Summary | `grocy.household` | 5 minutes–7 days; default weekly | canonical Grocy read | HADES-local only |
| Weekly Household Summary | bounded composition of only the three approved result families | 5 minutes–7 days; default weekly | read-only composition | HADES-local only |
| Backup Verification | `backup.evidence` | 5 minutes–7 days; default daily | read-only backup evidence | HADES-local only |

No arbitrary n8n graph, URL, code, shell, SSH, external notification, finance, Home Assistant, remediation, or Agent Zero delegation is in this catalog.

## Authority model

- The owner may create and control records for currently granted resources.
- A household user may create only templates whose entire resource scope is in that user’s explicit current grant.
- A household user receiving a shared record may run it only; it may not pause, resume, edit, delete, re-share, or transfer authority.
- Sharing never grants the underlying resource. The recipient must already possess current authority.
- Removing a subject or resource disables owned records, clears shares, and blocks future control.
- Owner/admin oversight may disable a record, but cannot grant a resource that identity policy does not grant.
- UI filtering is informational; server-side subject/resource checks are authoritative.

Current configured example: Household A has Core health, Groceries, and Backup evidence; Household B has Groceries only. These are deployment-specific grants, not defaults for future households.

## Quotas and confirmation

- Owner active records: 10.
- Household active records: 5.
- One active record per template/resource pair.
- Manual runs: 2 per staged record before the next schedule window.
- Interval: 5 minutes through 7 days.
- Preview hash and actor binding are required for confirmation.
- Duplicate confirmation is idempotent/fail-closed; stale or mismatched previews are rejected.

## Evidence

- `SYNTHETIC VERIFIED`: local policy test covers catalog filtering, unauthorized resource rejection, bounded fields, duplicate prevention, request-key idempotency, quotas, manual-run admission, shared run-only behavior, identity/resource revocation, inactive identity rejection, concurrent quota admission, and admin disable.
- `LIVE VERIFIED`: authenticated DOM Owner/A/B discovery, creation, listing, sharing, bounded run, revocation, and mobile discovery were exercised against the staged gate.
- `LIVE VERIFIED`: after fixing the inherited Phase 2 default grant, B’s live catalog exposed only Low Grocery and Groceries-only Weekly Summary; B’s server-watch request created nothing.
- `LIVE VERIFIED`: A completed a Weekly Summary create/edit/pause/resume/delete journey; the owner inspected and disabled A’s staged workflow without changing its resource.
- `LIVE VERIFIED`: an old A browser session lost execution authority after a resource revoke; its run was denied and the staged record was disabled.
- `LIVE VERIFIED`: no Phase 3 n8n graph was created; staged records were cleared after testing.
- `OWNER-GATED`: production promotion and household-creation authorization.

## Risks and remaining gates

1. The current owner UI still has duplicate legacy/unknown health-watch records; reconcile those before broad promotion.
2. Exact LLDAP group-name resolution and a real removed-user propagation fixture remain owner-gated; synthetic removal behavior is covered.
3. Fresh full Hindsight new-fact recall is outside this self-service boundary and remains a separate product acceptance item.
4. Production n8n promotion requires a separate adapter review, live execution-load proof, rollback proof, and explicit decision.

## Recommendation

Keep the staged gate enabled for bounded dogfood only. Do not authorize unrestricted household production creation yet. Approve the typed policy shape for the next review once the duplicate health-watch state and the remaining identity/soak evidence are closed.

**Decision field:** `Manny: ____________________   Date: __________`  
**Promotion authorization:** `Not granted by this packet.`
