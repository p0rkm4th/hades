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

The manifest-bound HADES image is `hades-open-webui:0.11.4-candidate-bound`,
image ID `sha256:110d8c280b165eeb26bc5c5bad0dce675b376399f18e04954f71e6338f596469`.
It was built from HADES commit `e33b7d18c889775260e5ace804aac0ebf598d8d8`,
using the candidate upstream digest above. The image labels record both values.
Compared with the previously exercised image ID
`sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`,
all 38 filesystem layers and all non-label image configuration fields are
identical; only the two HADES provenance labels were added. The acceptance
results below apply to the manifest-bound artifact's identical filesystem and
runtime configuration.

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
  upload.
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
