# Daily-driver failure log

This public-safe log records sanitized failure classes only. Owner prompts,
account identifiers, URLs, private runtime details, and personal data remain
outside the repository.

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
  from inheriting another account's local preset. The deployed asset cache
  version was advanced so existing browsers fetch the repair.
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
