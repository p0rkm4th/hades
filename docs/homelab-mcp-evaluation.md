# Homelab MCP evaluation

The current ecosystem has useful homelab MCP servers, but not one neutral,
well-defined command-and-control plane. HADES should compose narrowly scoped
authorities instead of handing an agent a general network shell.

## Candidates

| Capability | Candidate | Disposition | HADES boundary |
|---|---|---|---|
| Inventory and IPAM | NetBox Labs `netbox-mcp-server` | Preferred candidate; official NetBox Labs server is read-only | Read-only NetBox objects; intended topology, not live runtime |
| Virtualization runtime | Direct Proxmox API first; `tedosuji/proxmox-mcp` only as a disposable comparison | No mature first-party Proxmox MCP selected; the reviewed community server supports REST reads but has minimal adoption evidence | Read-only Proxmox API token; nodes, guests, status, resources; no SSH fallback |
| Network discovery | `ly1595/nmap-mcp` or a smaller bounded wrapper | Candidate for a separately approved scan worker | Explicit CIDR/target allowlist, rate and port bounds, no arbitrary shell |
| Availability | `mcp-uptime-kuma` or status/metrics endpoint | Prefer published status or metrics; defer authenticated write-capable MCPs | Observation only; stale data remains stale |
| Read-only homelab summary | [`brenflakes/labops-mcp`](https://github.com/brenflakes/labops-mcp) | Current read-only candidate for source review; do not install directly yet | Keep source-specific authority and HADES conflict handling at the adapter boundary |
| Broad homelab control | [`Nainounen/homelab-mcp`](https://github.com/Nainounen/homelab-mcp) or [`lidless-labs/proxmox-mcp`](https://github.com/lidless-labs/proxmox-mcp) | Rejected for direct HADES registration; these expose broad lifecycle, guest, Docker, networking, or destructive operations even where confirmation gates exist | Would require a separately isolated broker and independently approved operation surface |

The candidate list is a research result, not an installation or an approval to
scan. Community MCPs must be pinned, source-reviewed, isolated, and tested in
the disposable fixture before any owner environment is contacted.

## Current upstream check — 2026-09-15

The official NetBox Labs server is a strong fit for the inventory slice: its
documented tools are read-only object, ID, and changelog queries, and its
Docker/HTTP deployment supports an explicit MCP bearer token. Pin a released
image and keep plugin discovery disabled unless the approved inventory scope
requires it. The managed NetBox Platform MCP is broader (including CRUD and
bulk operations), so it is not the default HADES choice.

The reviewed Proxmox candidates are community projects, not a neutral
authority plane. One current project advertises 65+ tools spanning VM,
Docker, media, monitoring, storage, and networking control; another exposes
guest execution, file operations, firewall changes, token management, and
destructive resource operations behind confirmation flags. Those are useful
operator products in their own scope, but they are too broad for direct HADES
registration. HADES should use a small direct Proxmox read adapter or a
separately isolated read-only MCP process, then retain its own source and
authority reconciliation.

## Proposed HADES composition

```text
Nmap scan worker  -> observed discovery (time-bounded, explicit target scope)
NetBox            -> intended inventory/topology
Proxmox           -> current VM/container runtime
Uptime Kuma       -> observed service availability
HADES             -> source-aware explanation and conflict handling
```

Nmap must not silently populate NetBox. A scan produces evidence that can be
reviewed and optionally reconciled into inventory later. HADES must explain
conflicts such as “NetBox places X on Node A, while Proxmox currently reports
Node B.” Memory may provide labels and context but never authority.

## Command-and-control boundary

The first useful lane is read-only discovery and reconciliation. Management
actions, if later approved, require a separate tool surface with a specific
target, preview, confirmation, least-privilege credential, and canonical
read-back. A generic SSH, Docker socket, router-admin, or unrestricted Nmap
command tool is outside the HADES boundary.

The existing loopback fixture in
[`docs/homelab-readonly.md`](homelab-readonly.md) remains the independent test
target. The current connected-LAN Proxmox, NetBox, and published Kuma read
paths are now owner-authorized and exercised; physical-host recovery and
remaining hardware acceptance are still open.
The additional [`scripts/test-homelab-discovery-contract.sh`](../scripts/test-homelab-discovery-contract.sh)
fixture proves the Nmap-shaped evidence boundary: an in-scope result can
describe a device and port, while an inventory mutation and an out-of-scope
target are rejected. `integrations/homelab-readonly/discovery.py` now provides
the bounded reusable Nmap XML normalization layer; scanner invocation and
real-network access remain outside this fixture.

The first reusable HADES composition slice is
`integrations/homelab-readonly/`: a single read-only `homelab_summary` MCP
tool over approved Proxmox, NetBox, and Kuma GET endpoints plus the separate
`scan.run_bounded_scan` evidence worker. The worker invokes only an explicit
Nmap binary with an argv list, fixed safe scan flags, an approved target CIDR,
bounded ports/time, a bounded 256-packet-per-second floor, and XML stdout; it
never writes inventory. The bounded TCP-connect profile can finish a normal
`/24` without turning slow filtered hosts into an avoidable whole-scan timeout.
Its normalized output still requires review before any future reconciliation
step.

Bounded control planning is now staged in
`integrations/homelab-readonly/control.py`. It accepts only an exact Proxmox
node/VMID target and a small approved guest operation, requires canonical
preconditions plus owner authorization and confirmation, and emits a
write-free plan. It has no executor or transport. The caller must reconcile a
Proxmox read-back before reporting `SUCCEEDED`, `FAILED`, or `OUTCOME UNKNOWN`
and must not retry an unknown result blindly. The contract is exercised by
`scripts/test-homelab-control-boundary.sh`.

## Selection outcome

The stable candidate shape is **four bounded adapters**, not a single
homelab-control MCP: NetBox, Proxmox, Nmap evidence, and Kuma observation.
`labops-mcp` is a useful read-only upstream candidate to source-review against
that shape, while broad-control projects such as `homelab-mcp` must not be
registered directly. Stage the read paths first, add Nmap as an
evidence-producing scan worker, and keep Kuma observation-only. Do not install
a third-party server into production merely because it advertises write
operations.
