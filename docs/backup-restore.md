# HADES backup and restore requirements

This is a design and operator checklist, not an instruction to copy live
owner data into the repository. Backups must remain in a private, encrypted
location with access controls appropriate to the data they contain.

## Persistence map

| Component | Persistent state | Authority | Backup requirement | Restore note |
|---|---|---|---|---|
| Open WebUI | `/app/backend/data/webui.db` plus Chroma data and HADES-owned static assets; SQLite WAL sidecars were present during inspection | Open WebUI for conversations and account/config state | Quiesce WebUI or use a consistent database backup; preserve the deployed asset files separately | Restore the database and matching assets before starting the service; verify authentication and chat reload. Never copy only a live `.db` while its `-wal`/`-shm` sidecars are active. |
| Hindsight | PostgreSQL cluster under `/home/hindsight/.pg0/instances/hindsight/data` | Hindsight for semantic memory | Use PostgreSQL native consistent backup/export, not a raw live directory copy | Restore before Hermes; verify bank health and a known memory recall without treating it as live domain truth. |
| Grocy | `/config/grocy.db` and application configuration | Grocy for household/grocery state | Back up the complete persistent config using a consistent snapshot or native database method | Restore before enabling HADES mutations; verify stock and shopping-list state canonically. |
| Agent Zero | `/a0/usr` projects, settings, and delegated context; its `.env` is sensitive | Agent Zero for operator workspace state | Snapshot/export the dedicated persistent volume while excluding public artifacts and protecting secrets | Restore with the same bounded permissions; verify a harmless delegated task and failure behavior. |
| SearXNG | Configuration and optional cache | SearXNG for search configuration/cache only | Preserve configuration; cache is reconstructable and need not be treated as authoritative | Recreate cache if absent; verify JSON search and provider wiring. |
| Hermes | Profile configuration, sessions, skills, and service credentials | Hermes for orchestration/session state | Back up private profile data and secrets separately from public HADES source | Restore secrets with correct permissions, then start Hermes and verify the Open WebUI API contract. |

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

The temporary test administrator plaintext credential file and duplicate recovery/database
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
server; its native backup tool is available inside the image, but no live
Hindsight backup was created during this public-safe rehearsal.

The live Hindsight PostgreSQL listener passed `pg_isready` on 2026-09-12, and
the pinned image exposes matching PostgreSQL 18.1 `pg_dump`, `pg_restore`, and
`pg_isready` binaries. A schema-only export check was not completed because
the embedded server requires its private password; no credential was recovered
or recorded as part of this campaign. A private operator must supply that
credential to perform the native export and isolated restore rehearsal.

## Missing automation

No final backup job or installer is defined here yet. The next implementation
step is a private, component-specific backup/restore drill with explicit
retention and encryption settings, followed by an isolated restore test. The
mount inventory, recovery order, and synthetic Grocy/Open WebUI restore paths
are now documented; native production database/export procedures and restore
evidence remain outstanding for Hindsight, Hermes, Agent Zero, and SearXNG.
Hindsight tool availability and listener readiness are verified, but its native
export remains credential-gated.

Readiness-only checks on 2026-09-12 also confirmed that SearXNG's config and
cache mounts, Agent Zero's dedicated persistent volume, and Hermes' enabled
systemd service with a private profile are present. Their normal runtime
health/smoke paths pass. No SearXNG cache, Agent Zero workspace, or Hermes
profile was copied: SearXNG configuration may contain secrets, Agent Zero can
contain delegated work, and Hermes contains sessions and service credentials.
Their native backup/restore rehearsals remain private operational work.
