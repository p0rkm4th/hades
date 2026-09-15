# Upgrade and decommission contract

This repository does not perform unattended upgrades or destructive removal.
Production changes remain an explicit operator operation against one component
at a time.

## Bounded upgrade sequence

1. Record the current version, HADES layer digest, and runtime health.
2. Create and validate the component-specific backup described in
   [`backup-restore.md`](backup-restore.md).
3. Run installer preflight and validate the proposed pinned source.
4. Change exactly one component's private deployment record or supported
   upstream package while retaining the previous record and backup.
5. Start the changed component, verify its health, then run
   `hades-doctor.sh` and `validate-install.sh`.
6. Keep the previous artifact until persistence, restart, and owner acceptance
   pass. Roll back the changed component and its configuration if any check
   fails.

Changes are classified as follows:

- **Reconstructable component:** image/package or static configuration can be
  replaced from the pinned source after a health check.
- **State-bearing migration:** the component owns persistent data; backup and
  native migration/restore checks are mandatory before acceptance.
- **Authority-bearing migration:** identity, memory-bank mapping, or canonical
  domain ownership changes; this requires an explicit owner decision and is
  never an automatic upgrade.

The public manifest remains the version source of truth. Private deployment
records must use a specific tag or digest; `latest` and bulk update commands
are not part of the contract.

## Current update map

Updates are staged in this order so that the conversation surface and
authority-bearing services are not changed together:

| Component | Current production baseline | Candidate/action | Acceptance gate |
|---|---|---|---|
| Open WebUI | pinned 0.11.1 image plus the tracked HADES compatibility layer | build and test a new immutable image; preserve the Channels patch only if the new source still needs it | disposable login/channel/model-stream test, restart persistence, then owner UI acceptance |
| Hermes | 0.14.0 | qualify 0.21.2 with the explicit HADES suite; keep production unchanged until promotion rehearsal | candidate suite, rollback-backed owner-authenticated rehearsal, and owner approval |
| Hindsight | pinned digest, API/control ports 8888/9999 | upgrade one digest after backup and runtime/read-back checks | memory persistence, subject mapping, restart, and no port collision |
| Grocy | pinned digest | upgrade one digest after canonical backup | inventory, recipe, shopping-list, restart, and reconciliation checks |
| LLDAP | pinned digest | upgrade one digest after identity backup | login, group/capability mapping, restart, and revocation checks |
| SearXNG / Agent Zero | pinned records | upgrade independently when a bounded candidate is selected | read-only search freshness or bounded delegation contract; no authority expansion |

Open WebUI and Hermes therefore require two separate controlled changes. The
remaining owner input is authentication/acceptance and rollback approval, not
a need to run an unattended or bulk upgrade.

For the tracked LLDAP, Grocy, and Agent Zero Compose components,
`scripts/upgrade-hades.sh` implements this boundary. It is plan-only by
default. `--apply` requires root, a mode-0700 backup directory,
`HADES_UPGRADE_BACKUP_VERIFIED=1`, and a complete installer preflight; it
retains the previous Compose record and version manifest before pulling and
restarting exactly one component. Open WebUI, Hindsight, SearXNG, and Hermes
remain private-record/upstream-package changes governed by the same sequence
but are not bulk-managed by this helper.

## Bounded decommission sequence

Stop the runtime, remove only reconstructable application/runtime material,
and preserve `/var/lib/hades` and `/var/backups/hades` by default. Configuration
may be removed as a separate operator choice after backups are verified.
Permanent state destruction is intentionally not implemented by this project;
it requires a separately reviewed, explicit operator action.

## Future production migration

Verify backups, provision a fresh supported guest, install from the repository
and explicit operator inputs, restore canonical state, validate, obtain owner
acceptance, then cut over private DNS/network routing while retaining the old
environment for rollback. This campaign does not migrate production.
