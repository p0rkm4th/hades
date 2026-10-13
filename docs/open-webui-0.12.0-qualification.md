# Open WebUI 0.12.0 Candidate Qualification

Status: **candidate qualified with conditions; production remains pinned to 0.11.4**.

## Pinned candidate

- Upstream release: `0.12.0`
- Upstream source: `15818d88fd7bde1b73de33590f50d15d21e8d7c1`
- OCI index: `sha256:1565038903151ced924b5a3226f73f40f16963df4b910441f6391f10144afdaa`
- Candidate platform: `linux/amd64`
- Platform manifest: `sha256:208e824dd445548da7bd655a5e24718bf88112a7f60a807b5adb09096f2fd10b`
- Candidate-only pin file: `config/openwebui-0.12.0-qualification.pins`

The production version manifest remains unchanged. Build with
`scripts/build-openwebui-012-qualification.sh`; it requires a clean worktree,
Docker Buildx, and the pinned BuildKit image. The build exports a Docker archive
with commit-derived `SOURCE_DATE_EPOCH` and timestamp rewriting, then records
its SHA-256, loaded image ID, upstream inputs, Buildx/BuildKit identity, and
Dockerfile checksum in a deterministic manifest. Two no-cache exports for
HADES source commit `bd77b10c7cd06fb0e1d9fae6b0590bd4a0a1e0f4` produced
byte-identical 1,618,772,992-byte archives (SHA-256
`92eb3d13b937558c6b76dfc99eb16a585030de6b6865b9551da3b19dc5654c1d`) and the
same image config ID `sha256:358ccb2f35f9959638fe0a77ced1f37e6fb5a4927e71c372f49cd28fb7fbc3c2`.
Legacy `docker build` is not reproducible and is not the supported command.

## Material changes reviewed

The upstream range is 584 commits from the exact 0.11.4 source (`8bd8b4fa`)
to the 0.12.0 source above. The material HADES-facing changes reviewed were:

| Area | Relevant 0.12 change | Qualification disposition |
| --- | --- | --- |
| Auth/session | SQL-backed session stamps, optional MFA, auth/session changes | Existing HADES revocation adapters retained and tested; MFA policy stays off. |
| Database/migration | Additional schema and data migrations | Tested on disposable populated 0.11.4 copy; users, UI settings, model endpoint/configuration and model visibility, stored tool, chat, file, shared channel, and SQLite integrity survived. Rollback restores the pre-upgrade database and revocation store. |
| Chat/message storage | Chat persistence and message/branch/fork changes | Migration, private/shared access, restart persistence, streamed response paths, and the synthetic browser edit/resubmit, regenerate, fork, new-chat, long-thread, reload, and delete lifecycle are tested. |
| Sharing/channels | Shared-chat replies, chat forks, permission changes | ACL and membership persistence tested; no new sharing defaults enabled. |
| Tools/MCP | Tool, model, and skill version history; experimental Tool Search | Existing HADES tool flow tested; Tool Search remains disabled. |
| WebSocket/streaming | Chat and tool streaming changes | Synthetic stream and revocation/disconnect paths tested. |
| Model controls | Group model defaults and additional model controls | Candidate does not grant new authority through UI controls; acceptance uses bounded synthetic model configuration. |
| Files | Upload and document preview changes | Bounded DOCX preview, malicious/unsupported handling, and cross-user isolation regression passed. |
| Voice | Realtime voice | Disabled; requires separate service/privacy decision. |
| Admin/user management | Nested groups and group defaults | LDAP synchronization, grant/revocation, empty-group and outage behavior tested with HADES adapters. |
| Security | Session, revocation, sharing, file, and socket changes | Existing HADES security guarantees preserved by focused candidate tests. |
| UI only | Branding, theme, model presentation, and layout | Candidate starts and synthetic authenticated UI flows render; no production customization changes. |

Realtime voice, MFA policy, and Tool Search remain unconfigured in this
candidate. No optional feature is enabled by the upgrade itself.

## HADES compatibility disposition

| Adapter | Candidate disposition | Evidence |
| --- | --- | --- |
| Fail-closed JWT/session revocation | Retain, adapted | Preserves upstream session-stamp/MFA code while failing closed when Redis is unavailable or revocation metadata is malformed. Candidate HTTP/session tests pass. |
| Authority revocation routes | Retain, adapted | 0.12 route shapes differ; role changes, account deletion, group hierarchy, and LDAP reconciliation need HADES revocation before authority changes. |
| LDAP empty-group reconciliation | Retain | 0.12 still skips native reconciliation when the LDAP group list is empty. Empty/final-group removal is exercised by candidate tests. |
| Socket disconnect fail-closed | Retain, adapted | Upstream still suppresses disconnect failures; candidate wrapper propagates failures to authority-changing callers. |
| Channels response consumption | Remove from candidate | The same authenticated synthetic model-stream test passes on the exact upstream 0.12 image without the HADES patch. The 0.11.4 production image is unchanged. |
| Finance/receipt/task routes, HADES branding, client stream recovery | Retain | Product capabilities or existing HADES-specific behavior; not replaced by 0.12 features in this qualification. |

The candidate fails startup if its persistent revocation store is not
configured. Candidate UI harnesses use a disposable, isolated Valkey instance;
they do not weaken this production requirement.

## Qualification evidence so far

- Candidate-only Docker wrapper built locally from the pinned amd64 image.
- Final candidate source: `bd77b10c7cd06fb0e1d9fae6b0590bd4a0a1e0f4`.
- Repeating two no-cache candidate builds for that exact source yielded
  byte-identical 1,618,772,992-byte Docker archives with SHA-256
  `92eb3d13b937558c6b76dfc99eb16a585030de6b6865b9551da3b19dc5654c1d` and
  image config ID `sha256:358ccb2f35f9959638fe0a77ced1f37e6fb5a4927e71c372f49cd28fb7fbc3c2`.
  The manifest records the upstream and BuildKit pins, source SHA, Dockerfile
  SHA, Buildx version, platform, image ID, and artifact SHA.
- Synthetic owner/household populated 0.11.4 state migrated on the HADES 0.12
  wrapper; users, persisted user UI settings, configured model endpoint,
  post-migration model visibility, stored Open WebUI tool, private chat/file
  isolation, shared-channel membership, original and forked chat branches,
  uploaded DOCX bytes, and SQLite integrity survived. The repeatable disposable
  migration and rollback check is `scripts/test-openwebui-012-populated-migration.sh`;
  its run against the pinned candidate image and 0.11.4 baseline passed on
  2026-10-13.
- Rollback rehearsal restored the pre-upgrade application-data snapshot and
  persistent Valkey revocation state on the 0.11.4 HADES baseline. Pre-cutover
  sessions remained rejected; fresh login and state survived restart.
- A malformed disposable SQLite database made the candidate exit visibly;
  the separately preserved source snapshot remained unchanged.
- Exact final-image candidate tests pass for LDAP identity/group synchronization,
  group grant/revocation and LDAP outage; HTTP/session revocation, role change,
  password change, account deletion; private chat isolation and restart
  persistence; shared Channels permission and restart; and streamed Channels
  model responses. The disabled-role session boundary also passes.
- The upstream-only 0.12 image passes the synthetic Channels model-response
  test without the HADES Channels compatibility patch.
- The final candidate artifact passes the browser-based DOCX preview security
  regression, including cross-user file isolation and explicit shared-chat
  ACL behavior.
- The authenticated candidate Hindsight UI flow passes explicit save,
  correction, fresh-chat recall, actor isolation, and chat persistence using
  synthetic identities and an isolated persistent Valkey/Hindsight runtime.
- On the exact candidate image, a normal synthetic-user browser login, new
  chat, two streamed user/assistant turns, history listing, and reload all
  passed. The browser journey also passed edit/resubmit, regenerate through
  the 0.12 “Try Again” menu, fork with a new chat ID, create a fresh chat,
  complete an eight-turn thread, and delete that thread with history removal
  verified after reload. The repeatable synthetic acceptance is
  `scripts/test-openwebui-012-chat-lifecycle-ui.sh`.
- Authenticated synthetic candidate UI journeys pass for household Grocy
  operations, homelab network diagnosis, and read-only finance monthly
  aggregation/household denial. These exercise the 0.12 UI with the HADES
  gateway and synthetic canonical sources; they do not use private owner data.
- The synthetic owner/household candidate suite also passes LDAP bootstrap and
  group synchronization, session revocation across active sessions and restart,
  authority changes, private/shared chat ACLs, streaming, and the bounded
  document-security regression.
- Production was not changed and remains on qualified 0.11.4.

## Performance and resource comparison

- A local disposable harness used the same synthetic streamed model for both
  versions. Startup-to-health was 10.56 s on 0.11.4 and 11.14 s on 0.12.0;
  signup/signin were approximately 0.2 s each on both; first streamed byte and
  completion were 0.040 s and 0.032 s respectively; history reload was 0.016 s
  and 0.012 s. Restart-to-health was 27.04 s for both. This does not measure
  real model latency or tool-backed HADES turns.
- Image size was 6,459,245,954 bytes for the HADES 0.11.4 baseline and
  6,326,191,192 bytes for the HADES 0.12.0 candidate. One idle sample measured
  743,538,688 versus 750,530,560 cgroup bytes; this is not enough evidence for
  a material memory difference.

## Conditions and remaining limits

- Candidate tests use synthetic identities, data, and model/tool fixtures; no
  real Scotty account or private production database was migrated. The UI
  harness uses a synthetic OpenAI-compatible model and disposable candidate
  state; it does not replace natural owner dogfood against private production
  integrations.
- Owner regression semantics were checked through candidate UI journeys and
  focused source tests. This is bounded compatibility evidence, not a claim
  that every prompt variant or every live production integration was exercised
  against the candidate.
- MFA, Realtime voice, and experimental Tool Search remain disabled. Enabling
  them requires separate product decisions and qualification.
- Hosted Public CI run `38416741710` passes for source commit
  `bd77b10c7cd06fb0e1d9fae6b0590bd4a0a1e0f4`.
- Hosted Public CI run `38423575575` passes for commit
  `39f01ad82d945425efc719d63cb659fae15012e0`, including the exact-candidate
  browser lifecycle contract. The later migration assertions are covered by
  the subsequent branch-tip CI run and by the direct disposable migration run.
- Hosted Public CI run `38425117193` passes for commit
  `7fb51755454193a45f10baca74399bce33dd44a3`, including the added migration
  coverage. The final documentation-only commit also passed Public CI run
  `38425270625`.

No production promotion is authorized by this qualification. Candidate
evidence supports the tested migration/rollback data classes, authentication
and revocation, LDAP, chat and shared-object persistence, streaming/tool-backed
synthetic journeys, memory identity, and the bounded upload-security contract.
The recommendation is **QUALIFIED WITH CONDITIONS**: keep MFA, voice, and Tool
Search disabled; retain the documented HADES security adapters; require a
separate explicit owner promotion decision; and keep production on 0.11.4 until
then.
