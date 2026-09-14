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
