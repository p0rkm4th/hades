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
| Open WebUI | pinned 0.11.1 image plus the tracked HADES compatibility layer | 0.11.4 is the current immutable staging candidate; keep the Channels patch only if native behavior still needs it | candidate acceptance and cross-user DOCX replay pass; production backup/cutover/rollback rehearsal and owner UI acceptance remain gates |
| Hermes | 0.21.2 active; 0.14.0 rollback artifact retained | qualify a later pinned upstream version as a separate candidate | bounded candidate suite, rollback-backed owner-authenticated rehearsal, and owner approval |
| Hindsight | pinned digest, API/control ports 8888/9999 | upgrade one digest after backup and runtime/read-back checks | memory persistence, subject mapping, restart, and no port collision |
| Grocy | pinned digest | upgrade one digest after canonical backup | inventory, recipe, shopping-list, restart, and reconciliation checks |
| LLDAP | pinned digest | upgrade one digest after identity backup | login, group/capability mapping, restart, and revocation checks |
| SearXNG / Agent Zero | pinned records | upgrade independently when a bounded candidate is selected | read-only search freshness or bounded delegation contract; no authority expansion |

Open WebUI and Hermes therefore require two separate controlled changes. The
remaining owner input is authentication/acceptance and rollback approval, not
a need to run an unattended or bulk upgrade.

The 2026-09-15 Open WebUI candidate note below is historical. Open WebUI
production remains pinned at 0.11.1; the 0.11.4 candidate evidence is recorded
in [`open-webui-0.11.4-staging-candidate.md`](open-webui-0.11.4-staging-candidate.md).
Hermes 0.21.2 was later promoted on HADES guest and is the current
`config/versions.env` reconstruction pin. Hermes 0.14.0 remains a rollback
artifact. Future promotions still require a separately qualified candidate.
The upgrade helper
prints plan-only instructions for `hermes`, `open-webui`, `hindsight`, and
`searxng`; `--apply` is rejected for those private-record components. It can
still plan and apply the tracked one-component LLDAP, Grocy, or Agent Zero
changes under the backup and preflight requirements below. The plan prints the
exact candidate version, plus the Open WebUI candidate digest when applicable.

The historical Open WebUI 0.11.3 candidate was built from immutable amd64 manifest
`ghcr.io/open-webui/open-webui@sha256:9cd136effce6bb12a6a1988a35ab3b82cb40c48a6768fceeb17c83baf7cfac9c`
with the tracked HADES asset/compatibility layer. On 2026-09-15 it passed
`scripts/test-open-webui-candidate.sh`: private-chat persistence and Beta
access denial across restart, shared-channel membership/restart/authority,
and streamed model-mention persistence. This is disposable candidate evidence
only; it does not promote the image or prove owner UI acceptance.

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

## Production migration contract

Verify backups, provision a fresh supported guest, install from the repository
and explicit operator inputs, restore canonical state, validate, obtain owner
acceptance, then cut over private DNS/network routing while retaining the old
environment for rollback. The active migration record is
[`production-migration-20260916.md`](production-migration-20260916.md); this
runbook supplies its preservation-first upgrade and decommission safety rules.
