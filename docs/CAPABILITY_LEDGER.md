# HADES capability ledger

This public ledger reports product-level contracts and synthetic acceptance. It
is not a record of a particular deployment. Private host identities, service
placement, endpoints, real user data, live status, and recovery custody belong
in `hades-infra`.

| Capability | Public state | Evidence and remaining gate |
|---|---|---|
| Identity and access control | SYNTHETIC CONTRACTS | Stable subject mapping, owner/household separation, revocation, and fail-closed identity checks are covered by generic tests. Repeat on an owner-approved deployment. |
| Conversation and memory | SYNTHETIC CONTRACTS | Persistence, correction, isolation, and restart behavior have acceptance coverage. Restore must preserve subject-to-bank mapping. |
| Shared household inventory | SYNTHETIC UI COVERAGE | Canonical read-back, bounded safe mutations, and household isolation are tested with synthetic identities. Real household onboarding remains owner-gated. |
| Web research | PRODUCT CONTRACT | Research requests are separated from private homelab reads; live-source failure and citation behavior require owner dogfood for configured sources. |
| Homelab read-only view | PARTIAL | Proxmox, NetBox, and Kuma remain distinct authorities. Explicit identity links, provenance, partial failure, freshness, and contradictions are covered synthetically. Authenticated live owner acceptance remains open. |
| Inference awareness | PARTIAL | Optional Ollama catalog/residency and OpenAI-compatible model catalog reads support stable identity links; synthetic tests and a direct development-runner probe pass. Deployed HADES activation, GPU utilization/free-memory telemetry, and evidence-based placement remain open. |
| Backup and restore | PARTIAL | Repository verification and application restore are distinct. Independent synthetic destroy/restore evidence and owner-managed off-host custody are separate requirements. |
| Installation and upgrade | CONTRACT DOCUMENTED | Installer, doctor, recovery, and supported-host contracts exist. Independent clean-host reproduction and human-readable upgrade/decommission guidance remain release gates. |
| Optional integrations | OWNER-GATED | Private credentials and endpoints must be explicit. Missing integrations remain disabled and do not block unrelated core reads. |
| Infrastructure mutation | SEPARATE AUTHORIZATION | This homelab reliability work is read-only. Diagnosis does not authorize restart, provisioning, network, storage, or firewall changes. |

## Evidence labels

Use `LIVE VERIFIED`, `REPOSITORY VERIFIED`, `SYNTHETIC VERIFIED`, `HISTORICAL`,
`UNVERIFIED`, and `OWNER-GATED` accurately. A health endpoint does not prove a
workload is usable. Unknown and contradictory remain valid states.
