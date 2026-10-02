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
- Optional Ollama reads now collect installed model catalogs and current
  residency from `/api/tags` and `/api/ps`. OpenAI-compatible `/v1/models`
  catalogs are supported without claiming loaded state. Synthetic contract
  coverage includes source identity, linked NetBox display names, partial
  failure, token transport requirements, and owner response shaping.
- A direct development-runner probe against approved private APIs verified
  configured provider endpoints and NetBox device-ID joins. This is adapter
  evidence only; it is not deployed HADES or authenticated owner dogfood.
- Current canonical inventory/availability gaps were observed: NetBox service
  and address projections are empty, and the published monitoring page has no
  monitor rows. Proxmox responds but the current runner is not authorized to
  read guest state. No source was modified.
- Model inventory questions use only configured inference sources and fetch a
  targeted NetBox record only when a model-location answer needs one; they do
  not call the broad Proxmox/Kuma summary.
- Current-tree privacy checks and the focused homelab contracts pass.

## Remaining evidence

- Complete protected identity links for the live sources and verify their
  intended/runtime relationships.
- Configure the provider-native inference adapter in deployed HADES and add
  live GPU/resource telemetry; the capability matrix is not current runtime
  truth and free capacity/model fit remain unknown.
- Repair canonical NetBox service/address inventory and monitoring coverage
  through their owners, then exercise stale-data and source-conflict behavior
  against current observations.
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
