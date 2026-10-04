# Homelab compute capability contract

Concrete node names, addresses, hardware inventory, model placement, and
measurements are private operator data maintained outside this public
repository. This document defines how HADES may reason about compute without
publishing a household's topology.

## Evidence required for placement

Before recommending a host for a model or workload, HADES must join current,
source-labelled evidence for:

- intended host identity and role;
- host reachability and inference endpoint health;
- GPU model, count, and per-device memory where available;
- current free memory and resident workloads where supported;
- model artifact size, quantization, context, and runtime overhead;
- observation timestamps and any disagreement between sources.

Artifact size is not a VRAM-fit guarantee. Context/KV-cache overhead,
quantization, runtime allocation, and multi-device behavior can change the
required memory. If any required evidence is missing or stale, return an
estimate or `UNKNOWN` rather than claiming that a model fits.

## Placement states

Use a small set of explicit states:

- `AVAILABLE`: current endpoint and capacity checks support the proposed use;
- `DEGRADED`: a relevant dependency or capacity warning exists;
- `UNAVAILABLE`: current evidence confirms the required capability is absent;
- `UNKNOWN`: evidence is missing, stale, or contradictory.

NetBox owns intended topology, Proxmox owns hypervisor runtime, service-native
APIs own endpoint/model state, and explicitly configured host telemetry owns
only the measurements it actually reports. HADES may compose these sources;
it must not keep a manually curated public shadow inventory.

Public tests use synthetic nodes and synthetic capacity. They are not evidence
about any real deployment.
