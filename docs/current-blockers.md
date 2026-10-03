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
- Reviewed source links are active in the owner deployment. Authenticated owner
  and household UI dogfood now covers live node reads, provider model
  inventory/residency, model-capacity caveats, and household redaction. A full
  live homelab summary is still not accepted because Proxmox guest visibility
  and service identity/catalog coverage remain incomplete.
- An optional provider-native reader now queries Ollama model catalogs and
  residency plus OpenAI-compatible model catalogs, preserving endpoint
  identity and partial/unavailable states. Deployed HADES owner dogfood
  confirms provider catalogs and reported residency, while explicitly
  distinguishing these from successful generation and available capacity.
  Fixed-command read-only GPU telemetry is prepared and tested but remains
  unconfigured; live per-host utilization/free-VRAM evidence and model-fit
  recommendations remain open.
- Live source coverage is incomplete in the current private deployment.
  Detailed endpoint observations, topology, and source conflicts remain in
  private infrastructure records; do not infer broad health from partial data.
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
