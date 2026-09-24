# Canonical machine and capability matrix

Names are intentionally disambiguated: a row such as `Hermes` identifies a
physical resource pool, while `Hermes` in application/deployment documents
identifies the HADES orchestration service. The service location and the model
endpoint are independent fields; do not infer one from the other.

> **Superseded for current migration state:** use the live matrix and
> evidence in the private `hades-infra` repository, especially
> `inventory/capability-matrix.yaml` and `CURRENT_STATE.md`. This historical
> application-side snapshot is retained for provenance but must not be used to
> infer current GPU, SSH, NetBox, Kuma, or Proxmox state.

Status: historical read-only acceptance snapshot, reconciled 2026-09-17.  The matrix is
derived from HADES-bounded LAN discovery, authenticated SSH probes, and local
interface/neighbor evidence.  It is not an intended-topology declaration.

## Machines

| Host / IP | MAC | OS / kernel | CPU / RAM | GPU and driver state | Storage observed | Network / access | Current role | Acceptance |
|---|---|---|---|---|---|---|---|---|
| Alexandra / `<private>` | redacted | Debian 13; `7.0.2-6-pve` | i7-5930K / 31.3 GiB | GTX 660; no active driver; IOMMU absent | 7.3 TB HGST + 953.9 GB Samsung; PVE root and EFI mounts; SMART PASSED on 3 disks | `vmbr0`; SSH verified; 1 Gb/s link; Cockpit not enabled; private FQDN | Proxmox VE; GPU passthrough candidate, pending BIOS VT-d/IOMMU | PARTIAL |
| Erebus / `<private>` | redacted | Debian 13; `7.0.2-6-pve` | i7-5930K / 31.3 GiB | Quadro P4000; nouveau currently active; VFIO binding staged, reboot pending | 2 × 953.9 GB Samsung; PVE root mounts; SMART PASSED on 2 disks | `vmbr0`; SSH verified; 100 Mb/s negotiated link; Cockpit not enabled; private FQDN | Proxmox VE; GPU passthrough candidate | PARTIAL |
| Tartarus / `<private>` | redacted | Rocky Linux 10.2; `6.12.0-211.54.1.el10_2.0.1.x86_64` | i7-5930K / 62.2 GiB | 4 × Quadro P4000; NVIDIA 580.178.04; CUDA Driver API smoke passed; ~8.1 GiB free each at capture | 2 × 953.9 GB Samsung; XFS root/home/boot; SMART PASSED on both | `eno1` 1 Gb/s full duplex; SSH verified; autoconnect enabled; Cockpit enabled/listening; private FQDN | Rocky infrastructure/compute pool | PARTIAL: container/persistence gates |
| Hypnos / `<private>` | redacted | Rocky Linux 10.2; `6.12.0-211.54.1.el10_2.0.1.x86_64` | i7-5930K / 62.2 GiB | 2 × Quadro P4000; NVIDIA 580.178.04; CUDA Driver API smoke passed; ~8.1 GiB free each at capture | 2 × 953.9 GB Samsung; XFS root/home/boot; SMART PASSED on both | `eno1` 1 Gb/s full duplex; SSH verified; autoconnect enabled; Cockpit not observed; private FQDN | Rocky infrastructure/compute pool | PARTIAL: container/persistence gates |
| Thanatos / `<private>` | redacted | Fedora Server 41; `6.17.10-100.fc41` | i7-5930K / 31.2 GiB | RTX 2080; nouveau active; NVIDIA 575.57.08/DKMS packages present but inactive; Secure Boot enabled | 4 × 953.9 GB Samsung; SMART overall PASS; `/dev/sdd` historical marginal attributes and one CRC error; Fedora XFS root/boot | `eno1` plus Docker bridges; SSH verified; 1 Gb/s link; Cockpit enabled/listening; private FQDN | Fedora GPU-compute / temporary management pool | PARTIAL |
| Hermes / `<private>` | redacted | Fedora Server 42; `6.14.0-63.fc42` | i7-5930K / 31.2 GiB | 2 × RTX 2080; NVIDIA stack staged; controlled reboot did not return ARP/SSH/management ports | 2 × 953.9 GB Samsung; Fedora XFS root/boot | `eno1` pre-reboot; post-reboot reachability failed; private FQDN | Fedora GPU-compute / HADES workstation | PARTIAL |
| Unclassified / `<private>` | redacted | Unknown | Unknown | Unknown | Unknown | Layer-2 neighbor responds; no tested TCP service; SSH unavailable; no reverse name | Claimed seventh physical host; identity gate | OWNER/LOCAL CONSOLE INPUT |

The local HADES workstation also currently has two private interfaces; these
are two interfaces on the same Garuda workstation,
not additional homelab hosts.

## Capability state

| Capability | Current evidence | State | Smallest remaining contract |
|---|---|---|---|
| SSH reachability | Key-only SSH is verified to all six named hosts; Tartarus and Hypnos recovered on 2026-09-17 after controlled reboot persistence acceptance | PARTIAL | Complete remaining GPU-container acceptance and locate/provision the planned seventh host; `.113` is a Sony PS5, not infrastructure |
| Hostnames/FQDN | Six names observed; Fedora FQDNs are absent or inconsistent; Rocky names are DHCP-derived | PARTIAL | Choose stable hostnames and DNS/reservation policy before changing identity |
| GPU enumeration | GPUs visible on Alexandra, Erebus, Thanatos, and Hermes | PASS | Reboot and verify active NVIDIA/VFIO ownership |
| NVIDIA compute | Rocky native CUDA passes; Hermes staged NVIDIA reboot failed to restore reachability; Thanatos remains unqualified | PARTIAL / RECOVERY-GATED | Recover Hermes at console/power level, then run post-recovery NVIDIA/CUDA/container tests; qualify Thanatos separately |
| Proxmox passthrough | Erebus has isolated IOMMU group and VFIO config staged; Alexandra has no IOMMU groups | PARTIAL | Reboot Erebus; enable VT-d/IOMMU in Alexandra firmware |
| Storage health | Disk inventory collected; non-destructive SMART checks passed for all five Proxmox ATA disks and both SSDs on each Rocky host | PASS for observed Proxmox/Rocky disks | Collect privileged health evidence for Fedora disks when those hosts are available |
| Network/DNS/NTP | Links and addresses observed; NTP synchronized on six; reverse/forward naming inconsistent | PARTIAL | Establish stable reservation/DNS contract |
| Cockpit | Active on Tartarus, Thanatos, Hermes; installed/enabled on Tartarus; absent on Hypnos | PARTIAL | Decide whether Cockpit is required on Hypnos and enable only if needed |
| Container GPU access | Tartarus/Hypnos have Podman 5.8.2 with generated NVIDIA CDI; no local image was present for execution; reboot persistence passed | PARTIAL | Run a bounded GPU-container proof against an already-approved local image; do not pull images solely for qualification |

## Acceptance findings

- Both Proxmox nodes are standalone and currently have no VMs or containers.
  No two-node cluster was created. A safe cluster design still needs a
  deliberate QDevice/QNetd host and network plan.
- Tartarus and Hypnos do not expose QNetd because Rocky 10 repositories lack
  the package. Thanatos now has Fedora `corosync-qnetd` 3.0.3 with an
  initialized CA, active service, and TCP/5403 reachable from Alexandra and
  Erebus only. It is a temporary independent candidate; cluster activation
  still requires explicit architecture approval and qdevice/rollback review.
- Alexandra and Erebus local storage reports healthy SMART status for all five
  disks checked. Privileged read-only SMART checks now also pass on both SSDs
  in Tartarus and Hypnos; Fedora disk checks remain maintenance-window work.
- Erebus's active bridge link is only 100 Mb/s while Alexandra is at 1 Gb/s;
  this is an unresolved cabling, switch-port, or negotiation finding.
- Hermes' controlled reboot did not restore ARP/SSH/management reachability and
  requires console/power recovery before driver, CUDA, or GPU-container
  acceptance can be recorded. Thanatos is reachable, but Secure Boot is
  enabled and `nouveau` owns its GPU despite the staged NVIDIA/DKMS packages;
  its management workloads were deliberately not rebooted. Tartarus/Hypnos
  native CUDA and reboot-persistence acceptance is recorded separately; their
  remaining gap is GPU-container execution against an approved local image.
- `.113` is an active Sony PS5 consumer device (`PS5-9D7428`, Sony OUI) with
  no tested management service. It is excluded from the HADES machine set;
  the planned seventh server remains unidentified.

## Control-plane gates

- Proxmox nodes are not yet proven clustered. Do not create a two-node cluster
  or change quorum configuration.
- A QDevice/QNetd host has not been selected or provisioned. Tartarus or
  Hypnos could be candidates, but this requires a deliberate architecture
  decision and should not be inferred from hardware inventory.
- Proxmox least-privilege PVEAuditor token inputs are provisioned in protected
  local configuration and live node reads are accepted through the owner-only
  HADES path. Current NetBox/Kuma provisioning and host liveness are tracked
  in the private `hades-infra` matrix; this historical snapshot must not
  override that evidence.
- No NetBox writes, VM lifecycle writes, firewall changes, VLAN/routing
  changes, or machine reboots were performed during this snapshot.

## Evidence limitations

The bounded TCP worker does not identify hosts that expose no tested port;
`.113` was classified separately using its reverse-DNS name and local OUI
database, but it is not a HADES host. The planned seventh server still needs
to be found through DHCP/DNS, console, or an owner-provided service endpoint.
GPU driver packages are staged on Hermes and Thanatos, but active driver and
CUDA acceptance remain reboot-gated.
