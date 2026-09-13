# Daily-driver failure log

This public-safe log records sanitized failure classes only. Owner prompts,
account identifiers, URLs, private runtime details, and personal data remain
outside the repository.

## 2026-09-13 — Shared household turns polluted private memory

- Actor: synthetic household account
- Surface: Hermes automatic Hindsight retention around Grocy workflows
- Expected: Grocy remains canonical shared state; ordinary grocery/pantry
  conversations do not become private semantic memories
- Observed: automatic turn retention stored shared grocery/tool-result text in
  the authenticated user's private bank, which could also pollute unrelated
  personal-memory recall
- Failure layer: Hermes Hindsight provider `sync_turn` overlay boundary
- Repair/evidence: the deployed overlay now skips automatic retention for
  shared-state turns while preserving explicit memory requests. A real
  production synthetic grocery-list request completed with no new private
  Hindsight document; an explicit synthetic memory marker was retained and
  recovered from that user's bank afterward.
- Status: REPAIRED — synthetic fixture memories remain cleanup-only test data

## 2026-09-13 — Concurrent shared Grocy mutations are slow to acknowledge

- Actor: synthetic household accounts
- Surface: two simultaneous HADES grocery mutations for the same existing
  synthetic product
- Expected: both requests converge safely on shared canonical Grocy state and
  return a usable completion result
- Observed: canonical Grocy contained exactly one unfinished shopping-list row
  after the concurrent requests, but the client-side model responses exceeded
  the bounded observation window
- Failure layer: owner-facing request latency/observability; canonical
  duplicate prevention held
- Repair/evidence: a controlled Grocy outage now suppresses personal-memory
  prefetch for ordinary live household-state questions. A synthetic outage
  retest returned only a clear Grocy connection failure, with no stale
  inventory or personal-memory claim; Grocy was restored and healthy.
- Status: REPAIRED for stale-fallback behavior; concurrent response latency
  remains a separate performance investigation

## 2026-09-13 — Built-in theme selection resurrects an old HADES preset

- Actor: owner account
- Surface: Open WebUI theme settings and reload
- Expected: choosing a native Open WebUI theme clears any HADES preset for
  that account and remains selected after refresh
- Observed: an account-level Odysseus preset returned after refresh because
  the native-theme branch removed only browser state and never cleared the
  stored HADES preference
- Failure layer: HADES theme preference persistence
- Repair/evidence: the native-theme branch now clears both browser and
  account-scoped HADES preference; a valid account response with no HADES
  preset also removes stale browser state. Preference fallback storage is now
  namespaced by the authenticated Open WebUI subject, preventing one account
  from inheriting another account's local preset. Legacy unscoped keys are
  removed when the authenticated subject is established. The deployed asset
  cache version was advanced so existing browsers fetch the repair.
- Status: REPAIRED — owner should select the desired native theme once after
  a hard refresh; no owner preference was changed automatically

## 2026-09-13 — Directory revocation does not revoke WebUI bearer sessions

- Actor: synthetic household account
- Surface: staged LLDAP + Open WebUI authentication
- Expected: removing a directory identity prevents both new and existing
  application sessions from authenticating
- Observed: new LDAP login failed after directory deletion, but a previously
  issued Open WebUI token still authorized requests
- Failure layer: application session lifecycle; Open WebUI validates token
  signature and local user existence, not live directory membership
- Repair/evidence: supported Open WebUI user deletion invalidated the old token
  with HTTP 401. Automatic directory-to-application revocation remains open.
- Status: PARTIAL — architecture decision and restart/recovery rehearsal needed
