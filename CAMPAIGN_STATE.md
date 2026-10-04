# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current checkpoint — 2026-10-04

Public `main` is at
`6a04e9c82a2740cb66f897cd007d6679b662b2f0`, fast-forwarded from
`codex/inference-read-freshness-20261004`. Hosted Public CI passed for code
revision `e939b3caac8760291f610d2d428795956257ccb4` (run `37227907387`) and the
latest docs checkpoint (run `37228838517`). The code adds visible provider-read
times and partial-provider caveats to model-location answers, source IDs/read
times and ambiguity wording to cross-source HADES guest placement, and
sequential outage regressions for Proxmox runtime and backup evidence. A fresh
19-prompt owner/household dogfood found these response gaps; all prompts
returned and household leak checks passed. The private overlay and matching
read-only adapter were then deployed with hash-guarded, root-only rollback;
service health and fresh owner/household UI acceptance passed.

The current source tree removes private destination acceptance records and
per-user share mappings, requires explicit destination hostname input, and uses
synthetic guest names in fixtures. Current-tree safety, introduced-history
path/address audit, and the known-private-literal scan pass. Existing public
history is not rewritten; older reachable commits retain previously published
private identifiers. Do not claim historical erasure or merge from an older
candidate ref.

The deployment changed only the composed Hermes overlay and profile-selected
read-only HADES adapter. No Proxmox, NetBox, Kuma, host, driver, guest, network,
account, source ACL, or source-access configuration changed.

## Homelab read reliability

The read-only adapter composes Proxmox runtime, NetBox intended inventory,
Uptime Kuma observations, inference providers, and explicitly configured
telemetry. Owner output distinguishes source timing, stale observations,
source disagreement, and unknown runtime state. Household summaries remain
redacted. Synthetic adapter coverage seeds a stable Proxmox-to-NetBox identity
link, then makes NetBox unavailable; live runtime remains while the prior
inventory identity disappears, and stale Kuma data stays stale.

Authenticated synthetic UI acceptance exposed a registration gap: deterministic
owner routes could run before the local read-only adapter fallback was
registered. After MCP discovery returned no handler, the route incorrectly
reported the source as unconfigured. The route now registers the same bounded
owner-only fallback used by tool discovery. The authenticated acceptance passed
with synthetic identities and sources.

## Open work

- Continue live stale/partial-source acceptance, native service-health and
  service-placement coverage, network measurements, and bounded inference
  capacity checks.
- Review whether same-name guest matches within one Proxmox scope need clearer
  owner wording; pin the private overlay builder input hash before reuse.
- Complete backup-custody, reboot, and end-to-end restore evidence before
  claiming recovery readiness.
- Keep infrastructure reads read-only; write authority is outside this
  campaign.
