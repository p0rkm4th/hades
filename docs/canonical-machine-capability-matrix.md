# Operator-owned machine capability matrix

This public document defines the data contract only. Concrete machine names,
addresses, hardware, access paths, and observations belong in the protected
operator inventory in `hades-infra`; they are intentionally absent here.

## Ownership

| Data | Canonical owner | HADES use |
|---|---|---|
| Intended device identity, role, address, and topology | NetBox when configured; otherwise explicitly operator-managed inventory | Match and describe intended topology, retaining source and freshness |
| Hypervisor and guest runtime | Proxmox when configured | Current power state and bounded resource gauges |
| Availability | Uptime Kuma when configured | An observation, reconciled with direct checks where available |
| Service-specific state | The service's read-only API | Service health and inventory |
| Hardware capability | Protected operator inventory plus current host telemetry | Supplemental evidence; never sufficient by itself to claim availability |

HADES composes these sources. It does not become a second inventory authority.
Each observation retains source, retrieval time, and status. Conflicts remain
visible; stale or missing values become `STALE` or `UNKNOWN`, never green.

## Private matrix contract

The private matrix may include stable source identifiers, friendly names,
aliases, intended roles, hardware summaries, and links to other canonical
systems. It is read-only input. Runtime adapters must enforce size and record
bounds, reject symlinks where secrets or private configuration are involved,
and expose only fields needed for the current query.

Public fixtures use synthetic names and documentation-only addresses. They
must not be copied into operator inventory or described as live evidence.

## Evidence labels

Use `LIVE VERIFIED`, `REPOSITORY VERIFIED`, `SYNTHETIC VERIFIED`,
`HISTORICAL`, `UNVERIFIED`, or `OWNER-GATED` with a source and observation
time where applicable. A hardware row does not prove a host is reachable, and
a reachable host does not prove a service is healthy.
