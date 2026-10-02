# Current engineering blockers

This public page tracks product-level work only. Deployment identities,
endpoints, current host/resource state, credentials, backup custody, and
recovery evidence are maintained in private `hades-infra` records.

## Homelab read reliability

Status: **PARTIAL**

- The public read adapter now keeps Proxmox runtime, NetBox intent, and Kuma
  observations separate.
- Cross-source identity uses stable IDs and explicit private links. It never
  joins records by display name or IP alone.
- Synthetic tests cover stale observations, unavailable sources, duplicate
  names, source conflicts, household boundaries, and no-write behavior.
- Current source-link configuration and authenticated owner UI dogfood remain
  private deployment gates. Until that work is proven, a complete live
  homelab summary is not accepted.
- An optional provider-native reader now queries Ollama model catalogs and
  residency plus OpenAI-compatible model catalogs, preserving endpoint
  identity and partial/unavailable states. A direct development-runner probe
  verified approved private endpoints, but deployed HADES and authenticated
  owner dogfood remain unverified. GPU utilization/free-memory telemetry and
  placement evidence remain open.
- Current live source coverage is incomplete: NetBox device records are
  reachable but its service and address projections are empty; the published
  monitoring page has no monitor rows; Proxmox API reads require an authorized
  token not available to this execution path. Do not infer broad health from
  those incomplete sources.
- Backup readiness must report scope and custody. Repository verification is
  not proof that host/VM backups are current or independently recoverable.

## Release and owner gates

- Owner acceptance on the production deployment remains separate from public
  synthetic tests.
- Real finance, home automation, off-host recovery custody, and optional
  private integrations remain owner-gated.
- Production changes require an explicit migration campaign and owner approval.

No public document in this repository is authoritative for private
infrastructure state. Use the private inventory and live canonical sources.
