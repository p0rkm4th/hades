# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
private account identifiers, credentials, deployment identifiers, and raw
acceptance transcripts belong in protected operator records. These statements
summarize engineering evidence; they are not a live infrastructure probe.

## Current convergence checkpoint — 2026-10-05 UTC

Latest HADES code on public `main` is `9008e9059e5b58d8f6117361c361a0146cdbdcb9`; exact Public CI runs [37315944780](https://github.com/p0rkm4th/hades/actions/runs/37315944780) and [37316942770](https://github.com/p0rkm4th/hades/actions/runs/37316942770) passed. It includes the reviewed backup and recent-activity presenter extractions; NYX-002/004 found no material P1/P2 gap. The old GPU-parity ref remains review material only; its introduced history fails public-history safety and it regresses current main contracts. No old history or code was imported.

Fresh read-only provenance confirms the production Hermes process is active, has zero restarts, and selects the configured overlay. Its exact bytes match the protected deployment record and private deterministic per-slice builder. The running homelab MCP server maps to a public historical HADES commit, while current-main presenter refactors are not yet deployed; this does not establish byte parity with current main or fresh owner/household behavior. A private per-slice composition exists, but there is no single end-to-end public composition manifest. The existing protected owner and Household A/B sign-in inputs returned HTTP 400; no alternate passwords or account resets were attempted. Keep the read layer **PARTIAL** pending fresh authenticated owner/household dogfood and live stale/partial/conflict, service-health/placement, network-trend, and restoreability acceptance. No deployment, host, network, driver, source-ACL, or backup mutation occurred during this check.

Private-infra recovery also remains gated: the current checkout is dirty, and independent encrypted off-host custody and restore proof are not established. The owner confirms there is no off-site backup at this time. Treat private-infra recovery as a known owner-managed limitation; do not represent same-host copies as independent recovery.

**Next:** complete fresh authenticated owner/household dogfood using an authorized disposable identity and protected inputs, then document any behavior divergence. Keep current-main view refactors staged until they can be composed and proven against the active deployment without overwriting deployment-local policy.

## Historical release baseline and prior evidence

Code checkpoint `f55bd0a` passed Public CI run `37240583967`. Earlier
source checkpoint `07b0055` adds NetBox pagination completeness and
contradictory-coverage handling. HADES calls the service catalog
complete or empty only when `count`, `next`, and `results` agree; missing pages
and malformed or contradictory metadata remain partial or unknown. Focused
synthetic source and response contracts pass.

A first private overlay composition accidentally removed adjacent helpers. The
hash-guarded rollback restored the prior overlay and adapter, and a fresh owner
chat confirmed recovery. The corrected composition changes only the intended
coverage and placement functions; the bundle's AST/fallback tests and Nyx-4's
independent read-only review passed. The revised adapter and overlay are now
active with Hermes and WebUI healthy. Fresh owner UI acceptance reported the
empty service catalog with probe-health caveats, refused to infer Minecraft
placement, and retained the bounded Agent Zero endpoint response. Household A
was denied internal host/address details with no topology leak. No source
permissions or infrastructure settings changed.

This closes the NetBox completeness slice, not the broader homelab campaign.
The deployed read layer still needs representative stale/partial live-source
checks, service-native application health, source-conflict dogfood, network
measurements, backup/recovery evidence, and broader normal-user dogfood.

Fresh owner dogfood found a status/freshness conflation for the hardware
capability matrix and a duplicated GPU count in aggregate inventory labels.
Source read status and data freshness are now separate; the matrix timestamp is
evaluated against a seven-day window, and aggregate strings such as `4x Quadro
P4000` are preserved without a second inferred count. The owner response keeps
provider-residency and host-health limitations while distinguishing recorded
inventory from timestamped GPU samples. Public CI run `37238630968` passed at
`86ca48f`; fresh owner and household UI checks passed, including household
redaction and unknown game-server status. These specific defects are closed.
The wider homelab reliability campaign remains **PARTIAL** pending live-source
failure/conflict checks, service-native health and placement coverage, network
measurements, and backup/recovery evidence.

The owner question “Is everything okay with the homelab?” now returns a
bounded status summary instead of a guest inventory dump. It distinguishes
fresh configured checks from guest power state and keeps incomplete service
placement, unmonitored application health, and backup-content/restoreability
unknown. Follow-up dogfood correctly identifies duplicate display labels as
separate stable identities rather than a source disagreement; an initial
candidate that misclassified these labels was rolled back before the corrected
candidate passed owner and household checks. Public CI passed at `f55bd0a`
(run `37240583967`). The broader homelab campaign remains **PARTIAL**. The
summary does not query backup schedule/task status, and network measurement,
service-native checks, stale-source acceptance, and synthetic restore evidence
remain open.

A separate fresh owner backup query returns bounded configured Proxmox
job/task evidence and repository-check status, but does not establish expected
guest coverage, backup contents, off-site custody, or restoreability. It
preserves unknown guest attribution, and a fresh household check withholds
private backup details. Backup recovery remains open.

Fresh owner/household network-slow dogfood returns configured-probe timing
samples only and explicitly declines a network-wide diagnosis. Packet loss,
throughput, DNS timing, and historical comparison are not currently available,
so network bottleneck and trend claims remain unverified. Household wording
withholds private infrastructure details.

Previously published history is preserved and still contains older private
identifiers. Current-tree sanitization and the introduced-range path/address
audit do not erase or certify every older public commit. The current branch tip
removes the destination-specific acceptance records and per-user share mapping,
uses explicit operator hostname input, and uses synthetic guest identities.

## Homelab read reliability — PARTIAL

HADES composes configured Proxmox, NetBox, Uptime Kuma, service-native, and
inference observations without creating a second inventory authority. Owner
reads distinguish freshness, conflicts, and unknowns. Current evidence does not
establish every intended node, service, GPU, backup, or network condition.
Host utilization is available only for observed Proxmox node rows; network
trends, general host operating-system state, in-guest service health,
filesystem capacity, and backup restoreability remain unknown unless a current
source explicitly provides them. Household status remains unknown when no
approved household-safe live check is configured.

A synthetic NetBox outage test seeds a stable Proxmox-to-NetBox link before
withdrawing NetBox. The adapter retains current Proxmox runtime and removes the
prior inventory identity, while a stale Kuma observation remains stale. A
separate authenticated UI test found and fixed local read-only adapter fallback
registration for deterministic owner routes; the post-fix UI acceptance
passed. The current deployed owner UI also distinguishes guest power/placement
from application health and reports provider read times; household leak checks
passed.

Remaining work:

- exercise stale-source and partial-source-outage behavior against live and
  synthetic feeds without promoting cached data to live truth;
- verify contradictory Proxmox/NetBox/Kuma observations remain visible;
- reconcile stable identity links and service placements;
- qualify backup coverage separately from local copies, contents, and restore
  success;
- complete reboot and synthetic restore acceptance;
- continue owner and household dogfood for service placement, failures, model
  inventory, and distributed placement;
- retain read-only enforcement and household redaction under partial outages.

Do not infer current state from a capability matrix, prior chat, memory, or an
old report. No infrastructure mutation authority is included.

## Separate owner or external gates

- Production cutover, client/DNS changes, or retirement of an existing runtime
  require their own explicit owner decision.
- Real household onboarding requires the selected identity and credential
  flow.
- Real finance, Home Assistant, off-host encrypted recovery custody, and
  privileged browser workflows remain separately gated.
- Infrastructure changes discovered during read-only inspection are assigned
  to the authorized infrastructure operator; HADES integration work must not
  modify hosts, networks, drivers, or hypervisor state.

## Evidence location

Detailed private acceptance records and the canonical machine matrix belong in
protected `hades-infra`. Public fixtures and contracts use synthetic names,
addresses, credentials, and measurements.
