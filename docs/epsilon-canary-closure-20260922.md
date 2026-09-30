# Epsilon Server Health Watch closure — 2026-09-22

Status: `DOGFOOD GREEN`.

The approved scope is implemented and live on VM 802: typed Server Health
Watch only, private localhost n8n, HADES-local notifications, owner-only
creation/control, explicit household sharing, view-only household access,
operation-time authorization checks, and no remediation or external
notification path.

Evidence:

- HADES contract, idempotency, transitions, deduplication, source failure,
  authorization loss, sharing, and deletion tests pass.
- n8n artifact validation and bounded adapter tests pass.
- Live n8n webhook execution returns success; the allowlisted projection
  reports `UP` without nodes, credentials, or raw payloads.
- Live owner preview/confirm/create, inventory, run-now, share, household
  view-only inventory, and revocation paths were exercised in rendered
  desktop, mobile, and tablet HADES sessions. The browser task queue exposed
  and led to fixing process-boundary pending confirmations and stale action
  previews.
- n8n restart persistence and the writable-cache deployment repair were
  verified; runner remains healthy and localhost-only.
- A controlled unreachable-source execution projected `SOURCE_UNAVAILABLE`,
  then a restored-source execution projected `UP`; HADES recorded both local
  notifications and suppressed a repeated `UP` notification. A bounded
  20-request/4-worker run held the runner at 2.86% CPU, 427.4 MiB of 768 MiB,
  and 27 PIDs.

The limited-production dogfood gate is saturated for this typed capability:
fresh authenticated DOM evidence covers desktop creation/confirmation,
mobile and tablet inventory, household view-only access, sharing/revocation,
process-boundary confirmation, controlled source failure/recovery, restart
persistence, and bounded load. No broader capability is implied by this
status.

## Next-capability review

Do not expand to arbitrary n8n, remediation, external notifications, or
additional resource families yet. Manny/Orc decisions still required before
the next capability:

1. accept or reject the browser dogfood evidence and retention window;
2. choose whether the next typed family is another read-only health source or
   a separate notification surface; and
3. explicitly re-authorize any new credential scopes, recipients, or mutation
   semantics.
