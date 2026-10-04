# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, source credentials, host paths, rollback locations, and raw
owner acceptance transcripts are kept in private operator records.

## Current repository evidence

- Public `main` baseline at the last inspection: `b903ad331dc0269becf46600bf29db8931707fef`.
- Current homelab-readonly candidate before sanitization: `e211ac48476487d1f42ab4bd24af391ba5b55c43`.
- Public CI passed for that candidate in run `37219952994`.
- The branch is not promoted to `main`. A source audit found operator-specific
  identifiers in earlier commits on the candidate branch; the current tree is
  being sanitized. Do not merge this branch until the sanitized snapshot has
  been reviewed. Public history is not rewritten.

## Homelab read reliability

The read-only adapter composes Proxmox runtime, NetBox intended inventory,
Uptime Kuma observations, inference providers, and explicitly configured
telemetry. Current owner output distinguishes source timing, stale observations,
source disagreement, and unknown runtime state. Household summaries remain
redacted. A fresh owner node query completed in 4.92 seconds and withheld a
health claim when the available monitor lacked a stable identity link and the
runtime source had no corresponding node record.

Synthetic adapter coverage now seeds a stable Proxmox-to-NetBox identity link,
then makes NetBox unavailable. The current Proxmox runtime remains while its
prior inventory identity disappears; a stale Kuma heartbeat remains stale.
The focused adapter contract and current-tree safety checks pass.

## Open work

- Finish sanitizing the current public tree and retain private evidence in the
  operator repository.
- Keep infrastructure reads read-only; no host, driver, hypervisor, network,
  identity, or source configuration was changed in this follow-up.
- Continue live stale/partial-source acceptance, native service-health and
  service-placement coverage, network measurements, and bounded inference
  capacity checks.
- Complete backup-custody, reboot, and end-to-end restore evidence before
  claiming recovery readiness.
- Reconcile the sanitized candidate onto the green public baseline only after
  these privacy and engineering checks pass.
