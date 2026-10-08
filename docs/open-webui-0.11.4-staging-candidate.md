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

The staged HADES image is being rebound to a clean HADES source commit using
the candidate's immutable upstream image as its base. The build records both
commits and the base digest in image labels; the candidate verifier binds the
resulting local image ID to the manifest. Existing behavior results below came
from image `sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`;
they qualify the rebound artifact only if its filesystem layers match exactly.

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

Previous staging checks against the exact image ID stated above:

- `scripts/test-open-webui-candidate.sh` passed private-chat isolation and
  persistence, Channels membership and authorization persistence, streamed
  model responses, upload isolation, and LLDAP bootstrap in both account
  creation orders.
- `scripts/test-open-webui-populated-migration.sh` passed upgrade and rollback
  using a synthetic 0.11.1 database. It preserved synthetic owner and
  household local signup accounts, private chats and uploaded DOCX bytes, shared-channel state, and
  SQLite integrity; the household account remained unable to read the private
  upload.
- `scripts/test-openwebui-disabled-role-session.sh`, run with the candidate
  image selected, confirmed that an already-issued session is denied after
  role revocation.
- `scripts/test-openwebui-docx-preview-security.sh` rendered a synthetic DOCX
  in the actual chat Preview view, did not execute its harmless script marker,
  and exposed no `javascript:` link. The 0.11.1 positive control reproduced
  marker execution and the unsafe link.

LDAP identities are not covered by the populated-database migration check;
LDAP bootstrap behavior is covered separately by the synthetic LLDAP test.

These are synthetic staging checks. They do not prove production backup
integrity, external secret custody, live cutover/restore, or owner preference.
Before production promotion, rehearse the exact pinned artifact with the
production database, uploads, vector store, HADES assets, and signing secret
covered by a verified backup and rollback plan, then complete direct owner
dogfood. Follow upstream's
[migration guidance](https://docs.openwebui.com/troubleshooting/manual-database-migration/)
and [database backup guidance](https://docs.openwebui.com/tutorials/maintenance/database/);
database-only copies omit uploaded files and the vector store.
