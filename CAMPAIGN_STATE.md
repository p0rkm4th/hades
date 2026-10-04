# HADES campaign state — sanitized public summary

This file records product and repository status only. Deployment identities,
private topology, account identifiers, source credentials, host paths, rollback
locations, and raw owner-acceptance transcripts belong in protected operator
records.

## Current checkpoint — 2026-10-04

The homelab code checkpoint is `8e4a804a575c7e5035bc9feab2a0f26aa72857b2`
on `main`; documentation checkpoints `619d1da` and `22ae967` followed it.
Public CI passed for code revision `e939b3caac8760291f610d2d428795956257ccb4` (run `37227907387`), the
source-attribution follow-up `8e4a804` (branch run `37230026776`; main run
`37230088761`), and subsequent documentation updates through `22ae967` (run
`37230783833` passed on main). The source adds
provider-read timestamps and partial-provider caveats to model-location
answers, and source/time attribution plus conservative ambiguity wording to
HADES guest placement. Synthetic outage regressions cover Proxmox runtime and
backup evidence. A fresh 19-prompt owner/household dogfood found the original
response gaps; all prompts returned and household leak checks passed. The
composed read-only adapter and Hermes overlay were deployed with hash-guarded,
root-only rollback. A follow-up same-scope duplicate fix also passed focused
owner/household UI acceptance; service health remained green. A fresh owner
conversation also passed the “How do you know?” follow-up: HADES refreshed
configured sources, reported per-source read times, and distinguished NetBox
intent, Proxmox runtime, and Kuma probe results without promoting older
observations to live truth.

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
  capacity checks; Nyx-4 is independently reviewing the same-scope response
  against the exact source commit.
- Complete backup-custody, reboot, and end-to-end restore evidence before
  claiming recovery readiness.
- Keep infrastructure reads read-only; write authority is outside this
  campaign.
