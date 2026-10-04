# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
private account identifiers, credentials, deployment identifiers, and raw
acceptance transcripts belong in protected operator records. These statements
summarize engineering evidence; they are not a live infrastructure probe.

## Release baseline

The homelab code checkpoint on public `main` is
`8e4a804a575c7e5035bc9feab2a0f26aa72857b2`; documentation checkpoints
`619d1da` and `22ae967` followed it. Public CI passed for the initial source
candidate (run `37227907387`), same-scope placement code (main run
`37230088761`), and docs checkpoint `22ae967` (main run `37230783833`). Owner answers now show source read times for multiple matching
HADES guests, including same-scope matches, and state that guest inventory
alone does not prove which guest serves the application. Model-location output
includes provider-read time and partial-source coverage. Synthetic tests also
cover sequential Proxmox runtime and backup outages.

The composed Hermes overlay and profile-selected read-only adapter were
deployed with exact hash checks and root-only rollback copies. The same-scope
follow-up changed only the overlay. Service health passed after each restart.
Fresh owner UI checks covered duplicate guest placement, model-location
freshness, and conservative capacity wording. Fresh household checks preserved
redaction and owner-only placement access. A fresh owner “How do you know?”
follow-up refreshed configured sources, supplied per-source read times, and
kept NetBox intended state, Proxmox runtime, and Kuma probes distinct. This
closes these candidates’ deployment and focused UI parity checks, not the
broader homelab campaign. No
Proxmox, NetBox, Kuma, host, network, account, ACL, or source-access changes
were made.

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
