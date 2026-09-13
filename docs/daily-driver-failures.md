# Daily-driver failure log

This public-safe log records sanitized failure classes only. Owner prompts,
account identifiers, URLs, private runtime details, and personal data remain
outside the repository.

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
