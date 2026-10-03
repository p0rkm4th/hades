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
- Reviewed read-only source links are active in the owner deployment.
  Authenticated owner UI dogfood covers broad current status and provenance,
  named-node activity, service placement, provider inventory/residency,
  backup scope, and model-capacity caveats. Household dogfood checks service
  health, private-infrastructure redaction, and plain-language boundaries for
  whole-home speed and computer-status questions. Sensitive prior assistant
  turns are removed from household model context before routing or fallback.
  A full live homelab summary remains partial because Proxmox guest visibility
  and NetBox application-service coverage are incomplete.
- An optional provider-native reader now queries Ollama model catalogs and
  residency plus OpenAI-compatible model catalogs, preserving endpoint
  identity and partial/unavailable states. Deployed HADES owner dogfood
  confirms provider catalogs and reported residency, while explicitly
  distinguishing these from successful generation and available capacity.
  Fixed-command read-only GPU telemetry is implemented and tested but remains
  unconfigured pending separate approval for host service identities and keys;
  live per-host utilization/free-VRAM evidence and model-fit recommendations
  remain open.
- An owner dogfood question about NVIDIA driver/GPU execution was misrouted to
  unrelated web research. Current-tree routing now reads the prepared GPU
  telemetry contract and provider inventory, with household requests denied
  before source access. Regression tests pass; production rollout and live UI
  acceptance are still pending. This does not activate SSH access or claim
  current host GPU evidence.
- Live source coverage is incomplete in the current private deployment.
  Detailed endpoint observations, topology, and source conflicts remain in
  private infrastructure records; do not infer broad health from partial data.
- Capability-discovery dogfood found a household question that fell through to
  model fallback and described internal source/tool capabilities; a separate
  attempt persisted only an unfinished preamble. Candidate code routes this
  question to a deterministic owner summary or a plain household boundary, with
  focused regression coverage. It passed Public CI and the composed runtime
  check, was deployed with a root-only rollback copy, and fresh authenticated
  owner/household chats passed. This disclosure defect is closed; the incomplete
  Proxmox and NetBox source coverage below remains open.
- Live owner dogfood found one compound change-history question that returned
  a broad current snapshot and, with an added qualifier, could be falsely
  refused by the private-person research guard. A general model-placement
  question also fell through to named-machine lookup, and a natural question
  comparing source systems fell back to the broad summary. A scoped resource
  ranking question returned an unfinished check preamble. Candidate routing
  and privacy contracts now cover these cases. Following the candidate rollout,
  fresh authenticated owner UI turns correctly returned bounded recent
  activity, refused unsupported model-fit ranking without live GPU capacity,
  surfaced source-comparison coverage limits, and ranked the available
  Proxmox resource records with explicit partial-scope caveats. Household UI
  turns remained generic and denied owner-only placement/source details.
- A named Agent Zero availability/task-execution question also fell through
  to a generic answer. The current route uses only the configured bounded
  endpoint probe and explicitly says task execution was not tested. Fresh
  authenticated owner and household UI checks pass; no operator task is
  dispatched by this status question.
- Fresh broad-status dogfood confirmed that empty service-catalog coverage is
  reported as unknown intended placement. It names Uptime Kuma as the source
  of current probes and distinguishes host-probe responses from application
  readiness; guest visibility and live GPU capacity remain open evidence gaps.
- Candidate `4c73e28` passed Public CI and was deployed with rollback. Fresh
  Household A/B turns for whole-home slowness and computer status persisted
  scope-limited answers without exposing private topology or querying owner
  sources. This improves household wording but does not close source coverage.
- Candidate `33b24ec` passed Public CI and deployed the Hermes overlay and MCP
  activity reader together with rollback. Fresh owner “What changed since
  yesterday?” dogfood included a source-read timestamp and bounded Proxmox task
  / NetBox update coverage, and explicitly excluded host OS, package/driver,
  and in-guest service events. Household A remained denied private change
  history. A complete history and saved before/after comparison remain open.
- Fresh owner GPU-capacity dogfood says free GPU capacity is unknown without
  live per-host telemetry and does not treat inventory or empty model
  residency as capacity evidence. Household A receives only the owner-session
  boundary. The prepared fixed-command telemetry path remains unconfigured.
- Backup readiness must report scope and custody. Repository verification is
  not proof that host/VM backups are current or independently recoverable.

## Release and owner gates

- Live owner and household UI acceptance remains separate from public
  synthetic tests; both are required because synthetic tests do not prove
  deployed-source behavior.
- Real finance, home automation, off-host recovery custody, and optional
  private integrations remain owner-gated.
- Production changes require an explicit migration campaign and owner approval.

No public document in this repository is authoritative for private
infrastructure state. Use the private inventory and live canonical sources.
