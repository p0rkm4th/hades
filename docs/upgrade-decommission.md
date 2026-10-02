# Upgrade and decommission contract

Change exactly one component per upgrade. Pin the intended version; never
upgrade from a mutable `latest` tag. Verify a component-specific backup,
then apply the pinned version and run `hades-doctor.sh` plus
`validate-install.sh` before accepting the result. Preserve a recoverable
active migration record and use the generic sequence in
`production-migration-20260916.md` where a destination transition is required.

## Migration classes

- **Reconstructable component:** install from pinned source/config and validate
  the resulting service.
- **State-bearing migration:** back up, migrate through the component's
  canonical method, then validate read-back and persistence.
- **Authority-bearing migration:** preserve identity, permissions, stable
  subject mappings, and owner acceptance before switching authority.

Decommissioning separates service removal from data deletion. Stop services
through their generated systemd/Compose controls, preserve `/var/lib/hades`
state unless the owner explicitly approves deletion, and retain backups through
the confidence period. Never use blanket volume pruning as application removal.

Private deployment revisions, paths, rollback locations, and real backup
custody belong in `hades-infra`. This public contract does not authorize
production migration or decommissioning.
