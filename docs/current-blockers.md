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
  A full live homelab summary remains partial because NetBox application-
  service coverage is incomplete and cross-source identity links are missing.
- An optional provider-native reader now queries Ollama model catalogs and
  residency plus OpenAI-compatible model catalogs, preserving endpoint
  identity and partial/unavailable states. Deployed HADES owner dogfood
  confirms provider catalogs and reported residency, while explicitly
  distinguishing these from successful generation and available capacity.
  Fixed-command read-only GPU telemetry is now activated for the explicitly
  approved private HADES deployment. Fresh owner UI reads return current
  utilization/free-VRAM samples from the configured inference endpoints;
  Household A/B receive only the infrastructure-diagnostics boundary. Other
  deployments still require their own approved host identities and profile.
  Point-in-time GPU samples can compare observed single-GPU headroom, but do
  not prove workload execution or model fit and do not account for context or
  runtime allocation. HADES must keep that distinction in placement answers.
- Live activation exposed private Hermes-profile drift: the service parent had
  the telemetry path, but the MCP child environment did not, and the explicit
  HADES tool allowlist omitted `homelab_gpu_telemetry`. Both profile gaps are
  corrected with root-only rollback copies. The owner route now composes the
  live fixed-command sample with provider inventory; household requests are
  denied before source access. The adapter's synthetic safety contracts and
  exact-route runtime checks pass.
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
  Proxmox resource records with explicit partial-scope caveats. A later fresh
  owner source comparison found no contradictions among the linked records
  compared, but explicitly flagged unlinked records and partial guest scope as
  excluded from comparison and disclaimed a lab-wide all-clear. Household UI
  turns remained generic and denied owner-only placement/source details; fresh
  Household B comparison dogfood also disclosed no private source detail.
- A named Agent Zero availability/task-execution question also fell through
  to a generic answer. The current route uses only the configured bounded
  endpoint probe and explicitly says task execution was not tested. Fresh
  authenticated owner and household UI checks pass; no operator task is
  dispatched by this status question.
- Fresh broad-status dogfood confirmed that empty service-catalog coverage is
  reported as unknown intended placement. It names Uptime Kuma as the source
  of current probes and distinguishes host-probe responses from application
  readiness; guest visibility and live GPU capacity remain open evidence gaps.
- Fresh owner dogfood found a named-host workload query was rejected by the
  deterministic read-intent gate and persisted only a progress preamble.
  Candidate `e01570c` now answers from the verified Proxmox host/guest
  relationship and states that selected-guest visibility may be incomplete.
  Public CI and composed-overlay checks pass; deployment with rollback and
  fresh persisted owner/household UI acceptance now pass. Guest inventory does
  not establish application-service health.
- Fresh owner placement and health questions for a household app confirmed the
  live NetBox application-service catalog has no records and no matching
  current Uptime Kuma monitor is available. HADES correctly refuses to infer
  placement or health. Candidate `1beba11` adds the Kuma source-read time (or
  explicit source state) when a matching monitor is absent; CI, composed
  overlay, rollback deployment, and persisted owner/household UI checks pass.
  The household reply gives no host or address details. Canonical service
  inventory and service-health coverage remain incomplete.
- A fresh owner “Is the game server working?” question fell through to broad
  homelab status instead of the named-service health path. Candidate `b6c9cfb`
  maps that plain-language alias to Minecraft's monitor check. Public CI,
  focused route/runtime contracts, overlay composition, rollback deployment,
  and persisted owner/household UI acceptance pass. The owner now sees that no
  current service monitor matches Minecraft and gets the source-read time;
  Household A and B receive only the generic unknown. Both household replies
  persist without host, address, or infrastructure-source details. Minecraft
  health remains unverified because canonical service inventory and a matching
  monitor are absent.
- Fresh broad owner dogfood returns an explicitly partial current summary:
  selected-guest visibility, empty intended-service inventory, host-probe
  availability, inference catalog/residency, and unlinked records remain
  distinct evidence. It does not promote host probes to app health or model
  catalogs to generation/GPU capacity. Household A receives only the generic
  boundary.
- Fresh owner dogfood found that a host-scoped guest-inventory phrasing could
  fall through to the narrower self-service VM registry and return only its
  managed guest. Candidate routing now sends these variants through the
  canonical read-only host inventory path and includes guest IDs with current
  VM/CT state. Focused contracts, exact composed-overlay runtime checks, and
  Public CI run `37149616879` pass. Deployment with a hash-guarded root-only
  rollback is complete. Fresh owner UI lists currently visible guest IDs and
  power states with the selected-scope caveat intact; fresh Household A/B
  answers remain generic and expose no infrastructure detail. Full Proxmox
  scope and NetBox application-service coverage remain partial.
- Fresh named inference-host owner dogfood combines provider-reported catalog
  and residency with the current configured host probe, while labeling
  hardware specifications historical and host workload/GPU utilization
  unavailable. Candidate `f4aea3b` also labels stale roles as last recorded;
  it passed Public CI, composed-overlay checks, rollback deployment, and fresh
  persisted owner/household UI acceptance. The deployed capability matrix still
  predates newer private inventory observations and needs owner/infra review.
  Household A remains limited to the generic boundary.
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
- Fresh owner GPU-capacity dogfood now reports live per-device utilization and
  free VRAM with a source-read timestamp and a point-in-time/model-fit caveat.
  Provider residency remains separate evidence and does not establish model
  execution or capacity. Household A and B receive only the infrastructure-
  diagnostics boundary. The configured read path is non-sudo, fixed-command,
  strict-host-key verified, and read-only.
- A compound owner placement prompt that also asked “what is already running”
  was misread as a generic node-activity lookup. Candidate `ec09ed3` makes
  placement intent take precedence over that embedded clause; its focused
  adapter, service-health, and Hermes runtime contracts pass, and Public CI
  run `37152683615` passes. After rollback-ready deployment, a fresh owner
  answer includes the current largest single-GPU headroom and explicitly says
  it cannot confirm model fit. Household A/B answers remain generic.
- Fresh named-node owner dogfood then found that a natural-language inference
  node status question still omitted the now-connected GPU sample and claimed GPU telemetry
  was not connected. Candidate `3c6504c` requests telemetry only when stable
  inventory identity links the named node to an inference endpoint, formats
  only that endpoint’s live sample, and keeps host CPU load explicitly
  unmeasured. Focused adapter, Hermes runtime, and service-health contracts
  pass; Public CI run `37153465634` passes. The rollback-ready deployment is
  active and healthy. Fresh owner UI shows timestamped per-device free VRAM
  and utilization while identifying provider residency and hardware role data
  as separate/historical evidence. Household A/B receive only the generic
  infrastructure boundary. Live named-node telemetry is now verified; broader
  guest visibility and service catalog coverage remain incomplete.
- Representative post-deployment node dogfood now passes for identity-linked
  inference hosts, with target-only GPU readings. Nyx-4 verified that the
  configured provider IDs resolve to current NetBox devices; candidate
  `09698a3` fixes the remaining owner friendly-name lookup by accepting an
  exact provider ID only through one explicit linked identity and presenting
  the canonical NetBox label. Ambiguous or unlinked endpoint IDs remain
  unresolved. Public CI, focused adapter/owner-route/runtime contracts, and
  rollback-ready deployment pass. Fresh owner activity and placement answers
  include timestamped GPU readings with model-fit uncertainty; Household A
  receives only the generic boundary. Guest visibility and service-catalog
  coverage remain incomplete.
- A later fresh owner dogfood exposed a natural-language hardware-target gap:
  a card-model/count question returned broad status, while “big GPU box” fell
  through to a generic unsupported answer despite configured live telemetry.
  Candidate `40054cb` passed Public CI run `37167027365` and was deployed to
  VM 802 with hash-guarded root-only rollback copies. Fresh authenticated owner
  UI resolved the card model/count and returned timestamped per-card readings
  for “big GPU box”, with an explicit limitation on workload completion.
  Household A received only the generic hardware boundary. Hashes, modes,
  service state, and UI acceptance pass. Lowercase rendering of the canonical
  host label remains a presentation P2; broader source coverage remains
  incomplete.
- Owner service-placement dogfood reports the configured Agent Zero endpoint
  and its bounded HTTP reachability check separately from the empty NetBox
  application-service catalog, and explicitly disclaims task/delegation
  execution. Household A/B receive only the internal-host-details boundary.
- Fresh owner network-slowdown dogfood composes configured probe response
  times and current Proxmox resource samples, then states that these are not a
  network-wide measurement and packet-loss, throughput, DNS timing, and trends
  are unavailable. It does not invent a bottleneck. Household A/B are told
  whole-home diagnosis is not available from their account.
- A fresh multi-intent owner question—check one named inference host and assess
  room for another model—fell through to a generic answer. Candidate `a8fbb3a`
  adds a bounded target form, resolves it through one stable inventory identity,
  and returns only that host's linked endpoint and per-device readings with a
  no-fit-guarantee caveat. Focused adapter, Hermes runtime, and service-health
  contracts pass; Public CI run `37156030235` passes. After rollback-ready
  deployment, fresh owner dogfood shows only the requested host's four GPU
  readings; Household A/B receive only the internal-host boundary. This closes
  the named-node multi-intent routing defect. Model requirements and fit remain
  unknown.
- Backup readiness must report scope and custody. Repository verification is
  not proof that host/VM backups are current or independently recoverable.
- Fresh owner backup dogfood found that Proxmox's archived history can include
  a successful `vzdump` record with no guest ID. The current adapter omits that
  aggregate row while correctly refusing to attribute it to a selected guest.
  Candidate handling preserves it as separate unattributed evidence and says
  it cannot verify any specific guest's backup; it also avoids appending an
  unrelated HADES Backup Check to explicit Proxmox/guest-scoped questions.
  Candidate `a87f3ba` passed Public CI and is deployed on VM 802 with hash-
  guarded root-only rollback copies of the overlay and adapter. Fresh owner
  dogfood now reports both source-level aggregate task records without
  attributing either to a guest, retains selected-guest coverage limits, and
  disclaims backup-content, off-site custody, and restoreability verification.
  Household A and B receive only the generic home-computer boundary. The
  adapter omission is closed; complete guest attribution and restore
  verification remain open.
  Focused adapter contracts and Public CI runs `37150356935` and
  `37150661595` pass; deployment acceptance is complete. Backup contents,
  off-site custody, and restoreability remain unverified.

## Release and owner gates

- Live owner and household UI acceptance remains separate from public
  synthetic tests; both are required because synthetic tests do not prove
  deployed-source behavior.
- Real finance, home automation, off-host recovery custody, and optional
  private integrations remain owner-gated.
- Production changes require an explicit migration campaign and owner approval.

No public document in this repository is authoritative for private
infrastructure state. Use the private inventory and live canonical sources.

### Current live follow-up evidence — 2026-10-04

HADES review candidate `9511c75` passed Public CI run `37169928930`. Its
composed Hermes route handles cluster-wide guest status, returns source
read timestamps, limits complete claims to full configured scope, and routes a
compound household status question directly to the safe boundary. Direct-route
fixtures cover complete and partial Proxmox scopes; focused adapter/runtime and
public-tree checks pass. The candidate is not deployed pending approval for
that exact candidate. A fresh authenticated production owner chat reproduced
the defect: the cluster-wide guest question was treated as a request about a
physical host, and no guest states or source times were returned. The last
recorded review-head CI passed at `4096f39` (run `37170321258`); later commits
only reconcile documentation. Public `main` remains at `c83ddd6`.

Both approved Proxmox audit scopes are effective and Nyx-4 verified complete
guest enumeration with no access-denied exclusions. That gives inventory and
reported power state, not guest OS, application, or workload health. Broad
status is still partial: NetBox's application-service and VM records are empty,
and some Proxmox/Kuma observations lack verified stable identity links. HADES
reports those placement/correlation gaps rather than guessing.

Read-only inference catalogs and linked fixed-command GPU telemetry are active
only in the approved owner deployment. Samples do not prove successful
inference or model fit. Nyx-4 completed a scoped persistence-service correction
and verified affected inference services remained available without restarts;
no reboot was performed, so reboot persistence remains unverified.

Backups are represented by configured jobs and bounded task metadata. Backup
contents, independent off-site custody, and restoreability are not verified.
Network diagnosis remains limited by absent loss, throughput, DNS timing, and
long-term trend telemetry. Fresh owner/Household A/B UI evidence remains
protected outside this public repository; recent representative household
prompts disclosed no private topology or owner-only details.

### Current review branch follow-up

Fresh authenticated owner dogfood found that asking whether recent restore
checks left temporary guests present was routed to HADES repository backup
status instead of current Proxmox guest inventory. The owner-only source route
and regression coverage are now implemented on the review branch. It joins
bounded restore tasks to current guest rows by stable Proxmox source and guest
IDs, qualifies partial visibility as unknown, and does not claim guest or
application health. The generic-infrastructure/private-person classifier false
positive encountered by this route is also fixed, with named-person location
controls retained.

Focused contracts and the Hermes runtime route test pass. Candidate `e4b6084`
passed Public CI run `37172827916`, and the composed artifact passed against a
fresh read-only copy of the active production overlay. Production is unchanged;
exact-candidate deployment acceptance remains separate. Backup contents,
restoreability, and older or truncated task history remain outside what this
route can establish.

A deployment-shape review found that the initial restore-state implementation
was outside the closure copied by the active-overlay composer. The route is now
inside the composed homelab read path, with an earlier owner-only restore
preflight ahead of the generic backup fallback and a household denial before
source dispatch. The focused composer and composed Hermes runtime contracts
pass against a fresh read-only copy of the current production overlay. This
follow-up is committed as `e4b6084` and passed Public CI run `37172827916`. No
production file was changed. The preceding `ac95286` CI success covered the
earlier source revision.

A subsequent source audit closed one more false-certainty case: empty partial or
truncated Proxmox task history now returns unknown rather than “no restore task
found.” The malformed/partial-history contract passes locally, including the
composed runtime against the current deployed overlay base. This changes the
artifact hash after the prior approval request; that earlier hash must not be
deployed. Revised candidate `544cd06` passed Public CI run `37173378921`; exact
deployment acceptance is still pending.

Fresh-chat production dogfood on VM 802 again reproduced both owner routing
failures: cluster guest-state wording is treated as a physical-host query, and
the restore follow-up returns repository Backup Check status. Household A
received generic boundaries for both the restore question and broad health
question, with no private detail detected. The owner restore response matched
chat history after normalizing rendered Markdown whitespace/list markers; the
initial mismatch was in the test harness. Stable-render samples were 3.7–4.5 s;
no websocket terminal marker was emitted, so the prior 90-second harness
measurements are not valid latency observations. Protected raw evidence is
outside the public tree. The production correction remains gated on approval of
the current exact overlay candidate.

A new owner “Is everything okay?” dogfood returns a bounded partial view across
Proxmox, NetBox, Kuma, identity links, and inference providers. It reports no
failing fresh Kuma probe, does not equate endpoint reachability with application
readiness, preserves 15 unlinked resources, and qualifies model catalog and
reported residency. Household A receives only the generic boundary. The broad
answer's initial version lacked per-source retrieval timestamps in its text.
The current composed review candidate adds up to six bounded source/read
timestamp pairs to owner summaries and includes the tested owner routes for
cluster-wide guest state and restore-check guest presence; household responses
remain unchanged. HADES `e7fb6a1` passed Public CI run `37175267641`. A
cross-`PYTHONHASHSEED` regression proves deterministic composer output, and
the exact composed runtime covers cluster guest state, restore guest matching,
source timestamps, and household boundaries. The deterministic composed
overlay SHA-256 is `214c755e…ac128e8` over the last verified active base
`d6977174…e29277a2`. A read-only VM 802 check has now reconfirmed that exact
active hash, file mode/owner `0640 scotty:hades-runtime`, and active
`hades-hermes.service`. The base still needs a final hash check immediately
before installation. Exact-scope deployment approval and post-deployment owner
and Household A/B acceptance remain pending.

Fresh authenticated production UI dogfood reconfirmed the gap before rollout.
The owner broad summary says the live view is partial, identifies responding
source categories, leaves 15 cross-source identities unlinked, and distinguishes
probe response from application readiness; it still omits per-source read
timestamps. Household A receives a generic computer-status boundary, and its
game-server check says no current check is available rather than calling the
service healthy. Protected four-prompt evidence is mode 0600 outside the public
tree. No source or infrastructure configuration was changed.

Fresh owner dogfood asked which GPUs were available and where to host another
model. Live read-only telemetry returned eight timestamped device rows across
three configured inference endpoints, with observed free VRAM ranging from
about 0.4 to 7.9 GiB and zero utilization at that sample. HADES treated this as
point-in-time headroom, did not claim a model would fit, and reported the
hardware role/capability inventory as stale. Household A's AI availability
answer disclosed only that configured checks respond; it said generation was
not tested. Household A's game-server answer remained unknown because no current
check is configured. Protected evidence is mode 0600 outside the public tree.
Nyx-4 was asked to verify the capability inventory freshness and the canonical
service/Kuma records; no infrastructure writes were made.

A fresh provenance follow-up confirmed that an owner can ask when the broad
answer was checked and receive per-source retrieval times, plus an explicit
warning that retrieval time does not make an older observation live. Two
summary rows had no retrieval time and were labeled accordingly. The initial
broad response still omits those times, which is the pending overlay change.
Household A's follow-up stayed at the generic home-computer boundary and did not
read or reveal owner-only sources.

A separate fresh before-rollout comparison reconfirmed both pending owner-route
defects on the active production base. The cluster-wide guest question is
misread as a query about a physical Proxmox host, and the restore-check guest
question falls through to HADES repository Backup Check status. Household A
and Household B receive the expected generic boundary for both, with no
Proxmox, host, or guest details disclosed. Protected raw responses are mode
0600 outside the public tree. These are the exact routes included in the
deterministic candidate; deployment approval remains pending.

### Current deployed status — 2026-10-04 (supersedes pre-rollout notes above)

The deterministic homelab Hermes implementation in HADES `e7fb6a1` passed
Public CI run `37175267641` and is deployed in the owner environment. Its
private overlay hash and root-only rollback bundle are recorded in `hades-infra`,
not this public repository. Review documentation head `608598c` also passed
Public CI run `37176967000`; public `main` remains green at `c83ddd6`.

Fresh authenticated owner UI acceptance now passes for the previously failing
routes. Broad status carries per-source retrieval times and continues to call
partial coverage partial. Cluster-wide Proxmox status returns all nine
configured guest IDs in running/stopped groups, cites both source-read times,
and distinguishes guest power state from application health. Restore follow-up
joins recent restore tasks to current guest inventory, gives both read times,
and preserves its seven-day and workload-health limits. Fresh Household A/B
replies to the same cluster and restore prompts disclose no private topology or
owner data; persisted chat histories contain no tool-role messages or tool-call
records for those household turns. Protected captures remain outside this repo.

A separate read-only comparison confirmed that HADES's deployed capability
reader is using an older copy of the private hardware matrix. HADES correctly
labels that input stale; Nyx-4 is refreshing the existing read-only source and
will verify a fresh owner answer. Private paths, hashes, and machine data remain
in `hades-infra`.

The overall view remains **PARTIAL**. NetBox's application-service and VM
catalogs are empty, game-server health has no current matching monitor, and
some observations remain unlinked. Proxmox guest power state does not prove
in-guest health; GPU samples do not prove successful inference or model fit;
backup task history does not prove contents, independent custody, or
restoreability. These unknowns remain explicit in owner answers.

### Current operational follow-up — 2026-10-04

Nyx-4 refreshed the existing deployed capability-matrix input from the current
private inventory with a root-only rollback copy. Fresh authenticated owner
acceptance now uses its current dated hardware/capability data and does not
describe the role inventory as stale or historical; model-fit uncertainty
remains explicit. Private file hashes, paths, and raw responses are recorded
only in `hades-infra`.

The latest read-only NetBox/Kuma audit found that canonical service and
monitoring records still need reconciliation for HADES Core and two household
Minecraft deployments. Source-backed placement evidence and the safe object
creation sequence are documented privately. Under the owner's standing
authorization for this campaign, Nyx-4 is continuing the narrow reconciliation
with pre/post reads and rollback evidence; HADES's own source integrations
remain read-only. Network-wide OS/package/image currency and the naturally
scheduled management-backup result are also still being checked. No network-wide
“up to date” or backup-restorable claim is made until those checks finish.
