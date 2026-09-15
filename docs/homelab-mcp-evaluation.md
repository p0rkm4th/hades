# Homelab MCP evaluation

The current ecosystem has useful homelab MCP servers, but not one neutral,
well-defined command-and-control plane. HADES should compose narrowly scoped
authorities instead of handing an agent a general network shell.

## Candidates

| Capability | Candidate | Disposition | HADES boundary |
|---|---|---|---|
| Inventory and IPAM | NetBox Labs `netbox-mcp-server` | Preferred candidate; official NetBox Labs server is read-only | Read-only NetBox objects; intended topology, not live runtime |
| Virtualization runtime | `k-krawczyk/proxmox-mcp-server` or equivalent | Candidate; community-maintained, read-only mode is available | Read-only Proxmox API token; nodes, guests, status, resources |
| Network discovery | `ly1595/nmap-mcp` or a smaller bounded wrapper | Candidate for a separately approved scan worker | Explicit CIDR/target allowlist, rate and port bounds, no arbitrary shell |
| Availability | `mcp-uptime-kuma` or status/metrics endpoint | Prefer published status or metrics; defer authenticated write-capable MCPs | Observation only; stale data remains stale |

The candidate list is a research result, not an installation or an approval to
scan. Community MCPs must be pinned, source-reviewed, isolated, and tested in
the disposable fixture before any owner environment is contacted.

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
target. The real Proxmox, NetBox, Kuma, and network path are still owner-gated.
The additional [`scripts/test-homelab-discovery-contract.sh`](../scripts/test-homelab-discovery-contract.sh)
fixture proves the Nmap-shaped evidence boundary: an in-scope result can
describe a device and port, while an inventory mutation and an out-of-scope
target are rejected.

## Selection outcome

The stable candidate shape is **four bounded adapters**, not a single
homelab-control MCP. Stage the NetBox and Proxmox read paths first, add Nmap as
an evidence-producing scan worker, and keep Kuma observation-only. Do not
install a third-party server into production merely because it advertises
write operations.
