# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
hardware details, credentials, deployment identifiers, and raw acceptance
transcripts are maintained in protected operator records, not this repository.
The statements below summarize the current engineering gates and are not a
live infrastructure probe.

## Release baseline

The HADES public source and deployment records are maintained separately.
Use the current Git and CI state for source truth; use protected deployment
provenance and fresh canonical reads for runtime truth. Older reports are
historical evidence and must not be treated as current status.

## Homelab read reliability — PARTIAL

HADES composes configured Proxmox, NetBox, Uptime Kuma, service-native, and
inference observations without creating a second inventory authority. Recent
owner reads return per-source retrieval times and may remain `PARTIAL`; current
evidence does not establish every intended node, service, GPU, backup, or network
condition. Host utilization is available only for observed Proxmox node rows;
network trends, general host operating-system state, in-guest service health,
filesystem capacity, and backup restoreability remain unknown unless a source
explicitly provides them. Household status remains unknown when no approved
household-safe live check is configured.

The current `codex/gpu-telemetry-parity-20261004` candidate is `8c95bfb` and
passed Public CI run `37213164185`. Its previously deployed integration
candidate `f7890ed` contains the bounded read-only adapter,
owner-only provider/GPU details, permission-derived Proxmox guest visibility,
backup/task and recent-activity reads, and freshness/provenance behavior. The
current reviewed composition has also been applied to the protected owner
runtime with hash-guarded rollback. Fresh authenticated dogfood confirmed a
named Proxmox host load answer with its sample timestamp, and a ranking over
two observed online node rows. Household A and B received owner-only denials
for those host-load prompts, with no private topology in either response. The
ranking is explicitly partial and is not a complete homelab utilization view.

Freshness failures now suppress node metrics when a Proxmox source lacks a
stable identity or retrieval timestamp. Aggregate `UNKNOWN` wording names a
specific cause only when the endpoint error code establishes that cause. Named
node-load routing accepts a unique identity-linked display alias; collisions
and unmatched host names return unknown. Public `main` remains at the earlier baseline until this
candidate is merged, so branch and deployed-runtime provenance must be checked
separately.

Remaining work:

- exercise stale-source and partial-source-outage behavior against real and
  synthetic feeds without promoting cached data to live truth;
- verify contradictory Proxmox/NetBox/Kuma observations remain visible;
- reconcile remaining stable identity links and service placements;
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
the protected `hades-infra` repository. Public fixtures and contracts must use
synthetic names, addresses, credentials, and measurements.


## 2026-10-04 live homelab checkpoint — current state

This checkpoint supersedes the older candidate SHA and rollout snapshot earlier in this document. Current HADES work branch `codex/gpu-telemetry-parity-20261004` is at `d93d8a0`; Public CI `37217151095` passed. The branch is pushed, the worktree is clean, and public `main` remains `b903ad3` pending integration.

Fresh selected-profile reads report complete Proxmox guest permission scope and active host identity links. The protected owner runtime now correctly separates cross-source conflicts from same-source shared display labels, and the owner coverage response reports the empty NetBox application-service catalog without treating responsive Kuma probes as application health. Fresh Household A conflict-query dogfood returned only the generic boundary response; the protected topology detector was false. No infrastructure, driver, ACL, NetBox, Kuma, or network writes were made.

Remaining blockers: NetBox still has no application-service records; many service workflows lack native health checks; freshness/stale-source and live partial-outage acceptance remain incomplete; backup coverage/restoreability, reboot, and end-to-end restore acceptance remain open. GPU/driver status remains Nyx-4's separate acceptance scope.


## 2026-10-04 sequential-read freshness checkpoint

This is the latest checkpoint and supersedes the older candidate SHA above. HADES branch head is `347f74d`, Public CI run `37218397948` passed, the branch is pushed, and the worktree is clean. A new synthetic regression proves that after a successful Proxmox read followed by endpoint failure, the later summary drops the prior guest row, reports the source unavailable without a new retrieval timestamp, and keeps an unrelated available source. No adapter cache promotes the old row to current truth.

This is synthetic adapter evidence, not a live partition rehearsal. It also cannot detect an upstream server returning stale content as a successful response. Kuma heartbeat freshness is based on its observation timestamp. Remaining gates include live partial-source failure behavior, source-native service health, complete intended service placement, backup/restoreability, reboot, and end-to-end restore.


## 2026-10-04 canonical inventory outage with stale probe — latest

Latest candidate `a128bcd` on `codex/gpu-telemetry-parity-20261004` passed Public CI run `37218981309`. A new synthetic full-adapter case starts from successful source reads, then fails NetBox while Proxmox returns a current guest and Uptime Kuma returns an aged heartbeat. HADES reports partial coverage, preserves the current Proxmox observation, drops NetBox inventory/service rows, and keeps the responding-but-old Kuma heartbeat `STALE`. No previous NetBox row is reused. This is not a live outage rehearsal.

Open gates remain NetBox application-service coverage, functional service-native checks, live partial-source acceptance, backup/restoreability, reboot, and end-to-end restore.

## 2026-10-04 owner dogfood and linked-inventory outage coverage

Fresh authenticated owner UI reads now cover backup records, service coverage,
recent Proxmox activity, broad homelab status, a named inference/GPU host, and
network slowness. Backup answers distinguish archived tasks from verified
artifact contents, off-site custody, and restoreability. Service coverage
reports the empty NetBox application-service catalog and does not equate
responding Kuma probes with application health. Change-history answers bound
the claim to returned Proxmox tasks and disclose missing before/after, NetBox
deletion, and in-guest event history. Household A's broad computer-health
question returns a scope boundary; the private-topology detector remains
false.

The focused adapter fixture now seeds a real stable-ID Proxmox/NetBox match,
then fails NetBox on the next composed read. It verifies that live Proxmox
runtime remains, prior inventory/canonical identity disappears, the missing
link target is explicit, and the stale Kuma heartbeat stays stale. The
`scripts/test-homelab-readonly-adapter.sh` harness passes. This is synthetic
coverage, not a live source partition. Current authenticated dogfood details
remain in the private `hades-infra/acceptance` report.

Remaining gates are unchanged: empty NetBox service inventory, incomplete
native service health, live partial-source failure acceptance, network-wide
measurement, complete backup custody/restoreability, reboot, and end-to-end
restore. No infrastructure writes were made.

The linked-inventory expiry follow-up is HADES `e211ac4`; Public CI run
`37219952994` passed, as did the focused adapter harness and current-tree
safety check. A timed owner named-node query took 4.92 seconds and explicitly
left health unknown when the fresh monitor lacked a stable node identity link
and Proxmox runtime evidence was absent. This is one query, not a broad
performance qualification.
