# Open WebUI 0.12.0 Candidate Qualification

Status: **in progress; production remains pinned to 0.11.4**.

## Pinned candidate

- Upstream release: `0.12.0`
- Upstream source: `15818d88fd7bde1b73de33590f50d15d21e8d7c1`
- OCI index: `sha256:1565038903151ced924b5a3226f73f40f16963df4b910441f6391f10144afdaa`
- Candidate platform: `linux/amd64`
- Platform manifest: `sha256:208e824dd445548da7bd655a5e24718bf88112a7f60a807b5adb09096f2fd10b`
- Candidate-only pin file: `config/openwebui-0.12.0-qualification.pins`

The production version manifest remains unchanged. Build with
`scripts/build-openwebui-012-qualification.sh`; it requires a clean worktree
and labels the image with the HADES source commit and exact upstream inputs.

## Material changes reviewed

The upstream range is 584 commits from the exact 0.11.4 source (`8bd8b4fa`)
to the 0.12.0 source above. Material areas include SQL-backed session stamps
and optional MFA; nested groups and group model defaults; shared-chat replies
and chat forking; tool/model/skill version history; experimental Tool Search;
Realtime voice; chat/tool streaming and persistence changes; and additional
database migrations. Realtime voice, MFA policy, and Tool Search remain
unconfigured in this candidate. Shared-chat permissions and nested-group
revocation require explicit acceptance below.

## HADES compatibility disposition

| Adapter | Candidate disposition | Evidence |
| --- | --- | --- |
| Fail-closed JWT/session revocation | Retain, adapted | Preserves upstream session-stamp/MFA code while failing closed when Redis is unavailable or revocation metadata is malformed. Candidate HTTP/session tests pass. |
| Authority revocation routes | Retain, adapted | 0.12 route shapes differ; role changes, account deletion, group hierarchy, and LDAP reconciliation need HADES revocation before authority changes. |
| LDAP empty-group reconciliation | Retain | 0.12 still skips native reconciliation when the LDAP group list is empty. Empty/final-group removal is exercised by candidate tests. |
| Socket disconnect fail-closed | Retain, adapted | Upstream still suppresses disconnect failures; candidate wrapper propagates failures to authority-changing callers. |
| Channels response consumption | Remove from candidate | The same authenticated synthetic model-stream test passes on the exact upstream 0.12 image without the HADES patch. The 0.11.4 production image is unchanged. |
| Finance/receipt/task routes, HADES branding, client stream recovery | Retain | Product capabilities or existing HADES-specific behavior; not replaced by 0.12 features in this qualification. |

## Qualification evidence so far

- Candidate-only Docker wrapper built locally from the pinned amd64 image.
- Repeating the candidate build with the same committed inputs yielded the
  same local image ID.
- Synthetic owner/household populated 0.11.4 state migrated on the HADES 0.12
  wrapper; users, private chat/file isolation, shared-channel membership,
  uploaded DOCX bytes, and SQLite integrity survived.
- Rollback rehearsal restored the pre-upgrade application-data snapshot and
  persistent Valkey revocation state on the 0.11.4 HADES baseline. Pre-cutover
  sessions remained rejected; fresh login and state survived restart.
- A malformed disposable SQLite database made the candidate exit visibly;
  the separately preserved source snapshot remained unchanged.
- Synthetic candidate tests pass for LDAP identity/group synchronization,
  group grant/revocation and LDAP outage; HTTP/session revocation, role change,
  password change, account deletion; private chat isolation and restart
  persistence; shared Channels permission and restart; and streamed Channels
  model responses. The disabled-role session boundary also passes.
- The upstream-only 0.12 image passes the synthetic Channels model-response
  test without the HADES Channels compatibility patch.
- The final candidate artifact passes the browser-based DOCX preview security
  regression, including cross-user file isolation and explicit shared-chat
  ACL behavior.
- Production was not changed and remains on qualified 0.11.4.

## Remaining qualification gates

- Complete bounded owner-regression smoke through a production-like candidate
  path with synthetic domain fixtures; do not expose real owner data.
- Record comparable startup/login/chat/stream/history timing and resource use.
- Run hosted Public CI and review any failure.
- Finalize the promotion recommendation after those remaining gates.

No production promotion is authorized by this qualification.
