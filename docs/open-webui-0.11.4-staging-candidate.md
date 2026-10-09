# Open WebUI 0.11.4 staging candidate

## Decision

Update only the staging candidate pin to Open WebUI 0.11.4. Keep production
pinned to 0.11.1 until a separately reviewed backup, cutover, and rollback plan
and direct owner dogfood pass. No production state was changed for this
candidate.

## Upstream and artifact provenance

The official [release page](https://github.com/open-webui/open-webui/releases/tag/v0.11.4)
marks 0.11.4 as the latest stable release checked on 2026-10-08. Its signed tag
points to source commit `8bd8b4fac5e059578ac0c74b3c18d11139f88b7d`. The immutable
GHCR `linux/amd64` image manifest digest is
`sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f`;
it was independently resolved from the official GHCR registry on 2026-10-08.

The current manifest-bound HADES candidate is
`hades-open-webui:0.11.4-p0-candidate`, image ID
`sha256:d4c7e8aa08b35ddb81c2098db1fcbb7a6703f774d3000d2c088632b7053564a5`.
It was built from HADES commit `725b7991e4f776ed074758820d81a59ee916ef80`,
using the candidate upstream digest above. Image labels bind the source commit,
base digest, and security adapter set. The earlier image ID
`sha256:110d8c280b165eeb26bc5c5bad0dce675b376399f18e04954f71e6338f596469`
is historical DOCX-preview evidence only; it is not the current P0 candidate.

## Security and product changes relevant to HADES

The official [DOCX-preview advisory](https://github.com/open-webui/open-webui/security/advisories/GHSA-f9xp-mfmq-x6cg)
describes same-origin script execution and session-token theft on 0.11.1–0.11.3;
it is fixed in 0.11.4. The official
[terminal-proxy advisory](https://github.com/open-webui/open-webui/security/advisories/GHSA-q46m-r89w-j74p),
[community-stats token advisory](https://github.com/open-webui/open-webui/security/advisories/GHSA-vpq8-f445-hcq7),
and [OAuth role-policy advisory](https://github.com/open-webui/open-webui/security/advisories/GHSA-2rr4-q6pg-m5g3)
also list fixes in 0.11.4. The release additionally includes chat-branch,
streaming, terminal skill discovery, and file-handling fixes that matter to
conversation continuity and workspace escalation.

The tracked production pin remains in the DOCX advisory's affected range. A
read-only production check on 2026-10-08 found chat uploads enabled, so this is
an active P0 exposure. No exploitation was observed. The staged fix does not
close that exposure until production is safely upgraded.

## Staging evidence

The candidate acceptance sequence passed against the exact manifest-bound
image ID:

- `scripts/test-open-webui-candidate.sh` passed private-chat isolation and
  persistence, Channels membership and authorization persistence, streamed
  model responses, upload isolation, and LLDAP bootstrap in both account
  creation orders.
- `scripts/test-open-webui-populated-migration.sh` passed upgrade and rollback
  using a synthetic 0.11.1 database. It preserved synthetic owner and
  household local signup accounts, private chats and uploaded DOCX bytes, shared-channel state, and
  SQLite integrity; the household account remained unable to read the private
  upload. It also seeded permanent per-user revocation markers from a
  read-only pre-upgrade database copy before candidate startup and verified
  both pre-upgrade owner and household JWTs were rejected while fresh logins,
  existing chats, and uploads remained usable.
- The acceptance wrapper ran `scripts/test-openwebui-disabled-role-session.sh`
  with candidate image ID
  `sha256:110d8c280b165eeb26bc5c5bad0dce675b376399f18e04954f71e6338f596469`;
  the runner verified that manifest-bound identity, then confirmed an existing
  session is denied after role revocation and the chat endpoint returns 401.
- `scripts/test-openwebui-docx-preview-security.sh` created separate owner and
  household accounts, shared the malicious DOCX chat to the household user,
  cloned that shared chat in the household workspace, and previewed the DOCX
  there. On the vulnerable 0.11.1 control, same-origin script execution read
  the household session token and fetched that user's separately owned private
  canary file; an unsafe `javascript:` link also remained. The exact pinned
  0.11.4 candidate rendered the preview without executing script, exposing the
  link, stealing the token, or reading the canary.

LDAP identities are not covered by the populated-database migration check;
LDAP bootstrap behavior is covered separately by the synthetic LLDAP test.

These are synthetic staging checks. The cross-user replay directly exercises
the documented session-token theft chain, but it does not prove production
backup integrity, external secret custody, live cutover/restore, or owner
preference.

The current candidate passes
`scripts/test-open-webui-auth-revocation-candidate.py` against its exact image
ID. This runtime test verifies authenticated cross-container Socket.IO session
registration and disconnection after sign-out, role demotion, and account
deletion; token rejection; fail-closed behavior during auth-state store outage;
retry after store recovery; Valkey AOF restart persistence; isolated RDB
validation/restore; password-change revocation; and JWT issue-time behavior at
the revocation timestamp edge. The LDAP empty-group, populated migration and
rollback, private-chat, Channels, LDAP bootstrap, disabled-role, upload
isolation, and DOCX replay gates have also passed against this exact candidate
image ID `sha256:d4c7e8aa08b35ddb81c2098db1fcbb7a6703f774d3000d2c088632b7053564a5`.
These remain synthetic staging evidence, not live production acceptance.

### Legacy-session cutover invariant

Production currently has no revocation store. The new Valkey store therefore
starts empty and cannot by itself revoke JWTs issued by 0.11.1. Do not rotate
`WEBUI_SECRET_KEY` as a shortcut: Open WebUI also derives OAuth and other
encrypted configuration keys from it unless separately configured. The
cutover must quiesce ingress and stop the old app, take and verify the final
pre-upgrade database copy, seed permanent `open-webui:auth:user:<id>:revoked_at`
markers with `scripts/seed-open-webui-session-revocations.py`, then start the
exact candidate. The helper reads only user IDs from an integrity-checked,
read-only SQLite copy, requires an explicit `--confirm-quiesced` assertion,
and gives existing integer-second JWT issue times a five-second cutoff. New
logins wait until their JWT issue time is newer than that cutoff. Preserve the
same signing key and keep the seeded Valkey markers in the production backup.

The populated synthetic 0.11.1 → 0.11.4 migration now verifies this behavior
against candidate image ID
`sha256:d4c7e8aa08b35ddb81c2098db1fcbb7a6703f774d3000d2c088632b7053564a5`.
It does not yet prove that production ingress is quiesced, that a production
copy contains every real account, or that live production session revocation
passes. Those remain cutover gates.

Run revisions, exact candidate and positive-control image IDs, cross-user
results, and source-hash bindings are recorded in the
[cross-user DOCX evidence record](evidence/openwebui-0.11.4-cross-user-docx-2026-10-08.json).
Before production promotion, rehearse the exact pinned artifact with the
production database, uploads, vector store, HADES assets, and signing secret
covered by a verified backup and rollback plan, then complete direct owner
dogfood. Follow upstream's
[migration guidance](https://docs.openwebui.com/troubleshooting/manual-database-migration/)
and [database backup guidance](https://docs.openwebui.com/tutorials/maintenance/database/);
database-only copies omit uploaded files and the vector store.
