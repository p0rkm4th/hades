# HADES campaign state

This public continuation record describes repository work only. Live host
identity, addresses, credentials, deployment provenance, and private operational
evidence are maintained in the private infrastructure repository.

## Current engineering focus

The release-convergence baseline is complete. This campaign is improving the
read-only homelab view so it composes current canonical inventory, runtime,
availability, inference, and backup sources without inventing a second source
of truth.

## Current repository work

- Source identity is explicit. Proxmox, NetBox, and Kuma records are never
  joined by display name or address alone.
- Missing identity links, duplicate mappings, source disagreement, and stale
  observations remain visible in the read model.
- Source adapters remain bounded and read-only.
- Generic natural-language node-status routing is covered by synthetic tests.
- Current-tree privacy checks and the focused homelab contracts pass.

## Remaining evidence

- Complete protected identity links for the live sources and verify their
  intended/runtime relationships.
- Add or connect a provider-native inference inventory and live resource
  telemetry; the current capability matrix is not current runtime truth.
- Recheck NetBox and Kuma directly, then exercise partial-source, stale-data,
  and source-conflict behavior against current observations.
- Complete authenticated owner dogfood for broad health, node status, service
  placement, backups, network diagnosis, and model placement.
- Confirm owner/household response separation and measure representative query
  latency.
- Keep production unchanged unless the owner separately authorizes deployment.

## Repository and deployment authority

Public source contains generic code, test fixtures, and deployment-neutral
contracts. The private infrastructure repository owns topology, host IDs,
addresses, access configuration, live deployment provenance, and private
acceptance records. Synthetic evidence is not live infrastructure proof.
