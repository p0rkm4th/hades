# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
private account identifiers, credentials, deployment identifiers, and raw
acceptance transcripts belong in protected operator records. These statements
summarize engineering evidence; they are not a live infrastructure probe.

## Current convergence checkpoint — 2026-10-05 UTC

Public `main` is `b17ce8e733d777ae7e0c7a7d5af15a1948671ae9`; Public CI run
[37252630983](https://github.com/p0rkm4th/hades/actions/runs/37252630983)
completed successfully. The source checkpoint preserves Kuma observation time
as `observed_at` in the canonical compact summary; the owner named-monitor
response labels it as observation time and treats freshness separately. This
checkpoint is not deployed. The active runtime is a deployment-local
composition, and source/runtime parity remains unverified for this change.

The older `codex/gpu-telemetry-parity-20261004` ref remains review-only; no
code or history has been imported wholesale. NYX-010 rechecked the earlier
NYX-001 classification against current `main`; its semantic dispositions are
unchanged and the old branch still has no accepted unique behavior to port.
NYX-008 accepted the source-level incomplete-conflict and named-monitor review.
That was static source review, not live failure dogfood. NYX-009 completed a
fresh read-only backup metadata pass. NYX-011 found one unnecessary protected
custody detail in the public checkpoint. It was removed in candidate `cac23756`,
which passed Public CI run `37254073685`; the targeted NYX-012 recheck is pending.

The prior inference-view extraction remains deployed according to the last
protected rollout record. The later pure `homelab_views.py` extraction remains
in source but is not deployed. Existing owner/household dogfood covers source
provenance, bounded change history, and denial of private topology requests;
those targeted results do not close live stale/partial/contradiction tests,
native application health/placement, network trends, backup artifact or restore
verification, normal-user outage acceptance, or independent-device custody.
NYX-009 found the latest observed guest backup tasks successful through Oct 4;
Oct 5 local runs were pending at read time. A weekly application archive
completed on Oct 5 UTC, its sidecar matched, and an embedded database archive
passed structural listing; full application restore remains unproven. Synthetic
file-level dataset restore and several historical stopped-clone restore checks
are documented. Copies remain in the same homelab failure domain, and fresh
artifact/restore checks remain open for other components. The campaign remains
**PARTIAL**. No current-turn runtime, host, network,
source-ACL, or backup mutation occurred.

**Next:** complete NYX-012 review of the corrected checkpoint claims; recheck
backup task and snapshot metadata after the pending local schedules; verify
active runtime provenance before any deployment decision; then take the
smallest remaining evidence-backed adapter extraction or source-completeness
fix. The dirty primary checkout is preserved; use the clean worktree based on
public `main` for integration.

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
