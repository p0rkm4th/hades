# HADES backup and restore requirements

This is a design and operator checklist, not an instruction to copy live
owner data into the repository. Backups must remain in a private, encrypted
location with access controls appropriate to the data they contain.

## Persistence map

| Component | Persistent state | Authority | Backup requirement | Restore note |
|---|---|---|---|---|
| Open WebUI | `/app/backend/data/webui.db` plus Chroma data and HADES-owned static assets; SQLite WAL sidecars were present during inspection | Open WebUI for conversations and account/config state | Quiesce WebUI or use a consistent database backup; preserve the deployed asset files separately | Restore the database and matching assets before starting the service; verify authentication and chat reload. Never copy only a live `.db` while its `-wal`/`-shm` sidecars are active. |
| Hindsight | PostgreSQL cluster under `/home/hindsight/.pg0/instances/hindsight/data` | Hindsight for semantic memory | Use PostgreSQL native consistent backup/export, not a raw live directory copy | Restore before Hermes; verify bank health and a known memory recall without treating it as live domain truth. |
| Grocy | `/config/data/grocy.db` and application configuration | Grocy for household/grocery state | Back up the complete persistent config using a consistent snapshot or native database method | Restore before enabling HADES mutations; verify stock and shopping-list state canonically. |
| Agent Zero | `/a0/usr` projects, settings, and delegated context; its `.env` is sensitive | Agent Zero for operator workspace state | Snapshot/export the dedicated persistent volume while excluding public artifacts and protecting secrets | Restore with the same bounded permissions; verify a harmless delegated task and failure behavior. |
| SearXNG | Configuration and optional cache | SearXNG for search configuration/cache only | Preserve configuration; cache is reconstructable and need not be treated as authoritative | Recreate cache if absent; verify JSON search and provider wiring. |
| Hermes | Profile configuration, sessions, skills, and service credentials | Hermes for orchestration/session state | Back up private profile data and secrets separately from public HADES source | Restore secrets with correct permissions, then start Hermes and verify the Open WebUI API contract. |

## Current recovery matrix

This matrix is the current public-safe recovery summary. Exact backup paths,
identities, credentials, and artifact identifiers belong in the private
operator record.

| Component | Authority / reconstructability | Consistency method | Restore acceptance | Identity and canonical-state implications | Last verified | Remaining gate |
|---|---|---|---|---|---|---|
| Open WebUI | Authoritative for application accounts, conversations, and settings; static HADES assets are reconstructable from the deployment | Quiesce or SQLite online backup, including WAL-aware handling; preserve matching assets | Start with matching assets, authenticate, and reload a marker conversation | Restored application subjects must align with the chosen directory mapping; does not own Grocy, finance, or memory truth | 2026-09-13 | Owner-data restore and production cutover remain operator work |
| LLDAP | Authoritative for directory identities; application records are separate | Quiesced database copy and isolated pinned-image restore | Verify directory health, login behavior, and restored identity records | Restored identities do not invalidate existing WebUI tokens automatically; use the ordered revocation bridge | 2026-09-13 | Production owner recovery and subject remapping remain gated |
| Hindsight | Authoritative for durable memory; service can be recreated around a native PostgreSQL export | Native PostgreSQL export/restore, not a raw live data-directory copy | Verify health and a known marker recall in the intended bank/namespace | Stable subject-to-bank mapping must be restored before private recall is trusted; never treat memory as live domain truth | 2026-09-13 | Production owner-bank migration and mapping policy remain unapproved |
| Grocy | Authoritative for household and grocery state; service image is reconstructable | Consistent SQLite backup of `/config`, with canonical API verification | Verify stock, shopping list, recipes, and restart persistence before mutations | Restore must preserve canonical quantities and duplicate-folding behavior; no HADES shadow state | 2026-09-13 | Complete owner recipe-authoring acceptance and production backup policy |
| Hermes | Authoritative for orchestration, sessions, skills, and service configuration; package is reconstructable | Private profile/state backup with secrets handled separately and correct permissions | Start after dependencies, verify API health, chat reload, and one bounded tool call | Service credentials must be restored without exposing them; downstream canonical systems remain authoritative | 2026-09-13 | Full candidate promotion and owner-authenticated rehearsal remain gated |
| Agent Zero | Authoritative for its private operator workspace and delegated context; image is reconstructable | Snapshot the dedicated volume while protecting `.env` and excluding public artifacts | Verify a harmless bounded delegation and a controlled failure response | Restore the same persistent identity before trusting delegated context; no host access expansion | 2026-09-13 | Broader delegation and native A2A interoperability remain future work |
| SearXNG | Configuration is authoritative; search cache is reconstructable and non-authoritative | Preserve configuration; recreate cache when absent | Verify JSON search and Hermes provider wiring | No household or identity state is canonical here; outage must fail honestly | 2026-09-13 | No independent production gate beyond operator destination/retention policy |

## Live deployment mount inventory

This inventory was captured from the running production containers on
2026-09-12. Host source paths are intentionally omitted from this public
document; the private operator record should retain the exact host locations.

| Container | Persistent object | Container destination | Writable |
|---|---|---|---|
| `hades-open-webui` | `hades-open-webui-v0111-data` application-data bind | `/app/backend/data` | yes |
| `hades-open-webui` | HADES theme assets (bind-mounted individually) | `/app/backend/open_webui/static/hades-theme.css`, `hades-theme.js` | no |
| `hades-hindsight` | `hades-hindsight-data` | `/home/hindsight/.pg0` | yes |
| `hades-grocy` | `hades-grocy-data` | `/config` | yes |
| `hades-agent-zero` | `hades-agent-zero-data` | `/a0/usr` | yes |
| `hades-searxng` | `hades-searxng-data` plus cache volume | `/etc/searxng`, `/var/cache/searxng` | yes |
| `hades-searxng` | tracked `searxng/settings.yml` bind | `/tmp/hades-settings.yml` | no |

The runtime also has a private Hermes profile outside the containers. Its
configuration, sessions, skills, and service credentials must be backed up
separately from the container volumes and never copied into public CI.

## Operational requirements

1. Identify the exact bind mounts and named volumes from the live deployment;
   never infer them from a sample compose file.
2. Record component versions and image digests beside each private backup.
3. Quiesce writers, or use a native consistent backup mechanism, before
   copying SQLite or PostgreSQL files. A filesystem copy of a busy database is
   not automatically a valid backup.
4. Keep credentials and recovery passwords out of backups intended for public
   review. Encrypt private backups at rest and test access separately.
5. Restore into an isolated staging namespace first. Do not point a restored
   staging service at production household, finance, homelab, or memory
   endpoints.
6. Verify health, authentication, conversation reload, Hindsight recall,
   canonical Grocy state, and bounded Agent Zero behavior after restore.
7. Retain at least one known-good pre-migration backup until the replacement
   runtime has passed its owner acceptance matrix.

## Recovery order and evidence

Restore dependencies in this order so a recovered owner session does not
silently point at incomplete canonical state:

1. Open WebUI data and matching HADES static assets.
2. Hindsight's PostgreSQL data, followed by a health check and a known
   synthetic recall.
3. Grocy's complete `/config` state, followed by canonical stock and
   shopping-list checks.
4. Hermes' private profile and credentials, followed by the Open WebUI API
   contract and a bounded tool call.
5. Agent Zero's private volume, followed by a harmless delegated task and a
   controlled failure check.
6. SearXNG configuration and cache, followed by a JSON search check.

The first four steps are required before owner-facing chat is considered
recovered. Agent Zero and SearXNG may be restored independently, but HADES
must report those integrations as unavailable until their checks pass.

The private drill should record, outside Git:

```text
component, source backup identifier, creation time, image/version/digest,
restore target, health result, canonical verification result,
reload/restart result, operator, limitations
```

For the isolated synthetic rehearsal, use marker-only conversation, memory,
Grocy, and delegation fixtures. The rehearsal is successful only when the
markers are produced by the restored authoritative services, survive a fresh
session, and are absent from the public repository and CI artifacts.

## Current recovery artifact policy

The temporary test-admin plaintext credential file and duplicate recovery/database
copies were retired after authenticated admin use, synthetic non-admin
dogfood, database health, and restart checks passed. One protected private
database backup remains pending owner password rotation; it is not a runtime
dependency and is not in Git. Delete that final backup after the owner confirms
the temporary password has been replaced.

## Synthetic rehearsal evidence

On 2026-09-12, a disposable Grocy instance using the deployed pinned image
was initialized with an empty synthetic configuration. The service was
quiesced before its configuration directory was copied to a separate
disposable restore target. The restored SQLite database passed `PRAGMA
quick_check`, and a fresh Grocy container started successfully from the
restored target. The fixture and disposable containers were removed after the
check.

This proves the basic quiesced-copy and application-start path for Grocy; it
does not prove a production backup, encrypted retention, or recovery of owner
state. Those remain private operational gates.

On the same date, an equivalent empty Open WebUI rehearsal completed the
quiesced copy and SQLite integrity stages. A restored container reached the
Open WebUI health endpoint after allowing its embedding artifact download to
finish. The disposable instance and fixtures were stopped and removed.

This proves the isolated Open WebUI application-start path, but not recovery of
owner conversations, authentication, or matching static assets. Those remain
private operational gates. The Hindsight image includes a bundled PostgreSQL
server and its native backup tools.

The live Hindsight PostgreSQL listener passed `pg_isready` on 2026-09-12, and
the pinned image exposes matching PostgreSQL 18.1 `pg_dump`, `pg_restore`, and
`pg_isready` binaries. A protected custom-format export was created from the
live database and its archive structure validated. The dump was restored into
a temporary database on the same embedded PostgreSQL/pgvector server, then
that temporary database was dropped. The canonical Hindsight database was not
modified.

On 2026-09-13, a synthetic LLDAP directory backup was copied only after the
staging service was quiesced. SQLite `quick_check` returned `ok`, and the
backup restored into a separate container using the same pinned image, key
seed, and JWT secret; its isolated health endpoint returned HTTP 200. The
restore container was stopped and auto-removed after verification. This
proves the basic identity-database restore path, but not production owner
recovery or automatic Open WebUI subject remapping.

## Missing automation

[`scripts/backup-sqlite-state.sh`](../scripts/backup-sqlite-state.sh) now
provides a private, component-specific SQLite backup helper for Open WebUI,
LLDAP, Grocy, and Hermes. It uses online SQLite backup for WebUI, a native
SQLite snapshot for Grocy, a brief quiesced copy for the LLDAP image (which
does not ship SQLite tooling), and SQLite backup for Hermes state. The
quiesced LLDAP path waits for the container's health check after restart before
the run can succeed. It enforces private destination permissions, validates
each artifact, and writes checksums. It does not encrypt or retain backups,
and it deliberately does not claim coverage for Hindsight PostgreSQL, Agent
Zero, or SearXNG.
Each output also contains a mode-0600 `MANIFEST` with authoritative component
versions/digests and adapter revisions; this metadata is included in
`SHA256SUMS` so a restore can prove which composition produced the snapshot.
When present, the recovery validator checks the metadata format, manifest
version, required component fields, permissions, and checksum; older artifacts
without `MANIFEST` remain structurally verifiable but do not gain this newer
provenance guarantee.
Native production database/export procedures and isolated restore evidence are
now present for Hindsight, Agent Zero, SearXNG, and the Hermes profile at the
documented level: native Hindsight restore, disposable Agent Zero/SearXNG
launches, and isolated Hermes profile CLI parsing have passed. Retention,
encryption, and a complete all-component job remain operator work.
Hindsight native export and same-server isolated restore are now verified.

On 2026-09-13, the live production Grocy database was copied through the
container's SQLite/PDO path into a private recovery checkpoint. The copy is
non-empty, mode `0600`, and passed SQLite `PRAGMA integrity_check`; it is not
stored in Git. This replaces the previously unusable zero-byte Grocy artifact
in the older migration-preflight set. Hindsight export is separately validated
in the recovery section above.

The live production Open WebUI database was also copied through SQLite's
online backup API into that private checkpoint on 2026-09-13. The copy is
non-empty, mode `0600`, and passed `PRAGMA integrity_check` without stopping
the service. This is a current consistent database artifact; matching static
assets and an isolated restore are still required for full recovery proof.

The current LLDAP `users.db` was copied into the same private checkpoint on
2026-09-13 after confirming that no WAL sidecar was present; it passed
`PRAGMA integrity_check` and is mode `0600`. The current Hermes state database
was copied with SQLite's online backup API and likewise passed integrity
checks. These are fresh database-state snapshots, not a claim that the full
Hermes profile, identity secrets, or encrypted off-host retention has been
rehearsed.

The existing private preflight copies for Open WebUI, LLDAP, and Hermes also
passed offline SQLite integrity checks on 2026-09-13, and the copied Hermes
session JSON artifacts parsed successfully with private permissions. These
checks prove readable artifacts only; they do not replace isolated restore
acceptance or a fresh encrypted production backup.

Repeatable offline validation is available in
[`scripts/check-recovery-artifacts.sh`](../scripts/check-recovery-artifacts.sh).
It accepts a private recovery directory, prints only component labels and
structural results, validates protected tar archives and their relative paths,
and deliberately does not attempt to inspect Hindsight's native database
without its protected PostgreSQL credentials.

Encrypted copies can be created with
[`scripts/encrypt-recovery-artifacts.sh`](../scripts/encrypt-recovery-artifacts.sh)
by setting `HADES_RECOVERY_GPG_RECIPIENT` to an operator-managed public-key
identity. The wrapper fails closed when the recipient is unavailable, leaves
plaintext sources untouched for verification, skips quarantined failed
rehearsals, quarantines partial encryption output on failure, and writes a
checksum manifest for the encrypted output. Operators
must supply the key custody, off-host destination, retention, and eventual
plaintext-retirement policy; none of those secrets belong in Git.
The wrapper also rejects symlinked recovery trees and source files whose
permissions are broader than the private recovery contract before invoking
GPG.

On 2026-09-14, the encryption wrapper was exercised with a disposable
synthetic recovery marker and an ephemeral GPG encryption key. The encrypted
destination was mode `0700`; its checksum manifest verified, and decrypting the
artifact reproduced the marker. The temporary key, plaintext, and encrypted
destination were removed after the rehearsal. This validates the mechanics
only; real key custody, off-host transfer, retention, and plaintext retirement
remain operator decisions.

Readiness-only checks on 2026-09-12 also confirmed that SearXNG's config and
cache mounts, Agent Zero's dedicated persistent volume, and Hermes' enabled
systemd service with a private profile are present. Their normal runtime
health/smoke paths pass. Protected private archives now cover the SearXNG
configuration, the quiesced Agent Zero workspace, and the quiesced Hermes
profile. SearXNG configuration may contain secrets, Agent Zero can contain
delegated work, and Hermes contains sessions and service credentials; the
archives are not in Git. The Agent Zero archive was restored into a fresh
volume and launched with the pinned image without a published port while
production remained running. The SearXNG configuration archive was likewise
restored into a fresh volume and launched without a published port; production
remained running. The Hermes profile archive was extracted into a fresh
temporary home and its pinned production CLI parsed the restored profile
successfully; the live service was not stopped or reconfigured. Encryption and
retention remain private operational work.

The Agent Zero private environment file was found mode `0644` during the
readiness check and corrected to mode `0600` in the live persistent volume.
Future restore checks must preserve that restriction before the service is
started.

## Private operator procedure outline

The following is intentionally a procedure outline, not an executable public
backup job. Substitute a private encrypted destination and retain the image
digest alongside each artifact.

```text
quiesce the component
create a native/consistent export into the private destination
write a checksum and component digest beside the export
restore into an isolated namespace
start the restored component with isolated endpoints
run health, canonical-state, reload, and restart checks
retain the prior known-good artifact until acceptance passes
```

For Hindsight, use the bundled PostgreSQL `pg_dump` custom format and
`pg_restore`; provide the database password through a protected operator
credential mechanism rather than a command line or repository file. For
SQLite-backed Open WebUI and Grocy, use SQLite's online backup facility while
the writer is quiesced. For Hermes and Agent Zero, snapshot their private
profiles/volumes only after stopping their writers. SearXNG configuration can
be exported separately from its reconstructable cache.
