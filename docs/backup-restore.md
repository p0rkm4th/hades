# HADES backup and restore requirements

This is a design and operator checklist, not an instruction to copy live
owner data into the repository. Backups must remain in a private, encrypted
location with access controls appropriate to the data they contain.

## Persistence map

| Component | Persistent state | Authority | Backup requirement | Restore note |
|---|---|---|---|---|
| Open WebUI | Application database, user/chat/model configuration, and HADES-owned static assets | Open WebUI for conversations and account/config state | Quiesce WebUI or use a consistent database backup; preserve the deployed asset files separately | Restore the database and matching assets before starting the service; verify authentication and chat reload. |
| Hindsight | PostgreSQL/pg0 data, including durable memory | Hindsight for semantic memory | Use the database's native consistent backup/export method | Restore before Hermes; verify bank health and a known memory recall without treating it as live domain truth. |
| Grocy | `/config` application database and configuration | Grocy for household/grocery state | Back up the complete persistent config using a consistent snapshot or native database method | Restore before enabling HADES mutations; verify stock and shopping-list state canonically. |
| Agent Zero | `/a0/usr` projects, settings, and delegated context | Agent Zero for operator workspace state | Snapshot/export the dedicated persistent volume | Restore with the same bounded permissions; verify a harmless delegated task and failure behavior. |
| SearXNG | Configuration and optional cache | SearXNG for search configuration/cache only | Preserve configuration; cache is reconstructable and need not be treated as authoritative | Recreate cache if absent; verify JSON search and provider wiring. |
| Hermes | Profile configuration, sessions, skills, and service credentials | Hermes for orchestration/session state | Back up private profile data and secrets separately from public HADES source | Restore secrets with correct permissions, then start Hermes and verify the Open WebUI API contract. |

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

## Current recovery artifact policy

The temporary test administrator recovery database backup remains private and is retained
until the reset account has been independently used and the owner confirms it
is no longer needed. The temporary plaintext recovery credential is not a
runtime dependency and must be deleted after the owner has rotated or replaced
it. Neither artifact belongs in Git.

## Missing automation

No final backup job or installer is defined here yet. The next implementation
step is a private, component-specific backup/restore drill with explicit
retention and encryption settings, followed by an isolated restore test.
