# Homelab compute capability map

This map translates observed hardware into conservative HADES placement
guidance. Native CUDA capacity is recorded separately from container-backed
placement; a card is not selectable for a container workload until the
container and persistence gates pass.

Terminology note: the physical machine named **Hermes** is only a GPU resource
pool in this map. The **Hermes service** is HADES's orchestration layer and is
currently staged on the HADES destination VM; neither the machine name nor the
service name implies that the physical node is running the active model
endpoint. A model host becomes selectable only when its endpoint is explicitly
configured and its hardware acceptance evidence is current.

## Observed resource pools

| Pool | Observed hardware | Verified VRAM / free capacity | Current usable state | Appropriate HADES interpretation |
|---|---|---|---|---|
| Alexandra | GTX 660; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | Read-only refresh 2026-09-26: Debian 13/Proxmox reachable; no NVIDIA runtime; GPU has no IOMMU group in current boot. | Proxmox/storage pool; GPU passthrough unavailable/unverified |
| Erebus | Quadro P4000; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | Read-only refresh 2026-09-26: Debian 13/Proxmox reachable; P4000 is bound to `vfio-pci`, IOMMU groups exist; VM 802 config has no `hostpci` entry. | Passthrough prepared at host level, not attached to VM 802; no HADES GPU placement |
| Hermes | 2× RTX 2080; 12 logical CPUs; ~33.5 GB RAM | 8 GiB each; 7.4/7.6 GiB free at inspection | Read-only refresh 2026-09-27: NVIDIA 590.48.01 sees both cards; Docker active. Docker lists only `runc`/containerd runtimes; `nvidia-container-cli` is unavailable. | Native CUDA available; container GPU injection is not configured or proven; reboot persistence remains unverified |
| Thanatos | RTX 2080; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | Read-only refresh 2026-09-27: Secure Boot enabled, `nouveau` loaded, NVIDIA module absent; `corosync-qnetd` active. | Temporary management pool; GPU placement requires an approved firmware/driver maintenance window |
| Tartarus | 4× Quadro P4000; 12 logical CPUs; ~66.8 GB RAM | Not currently available | Read-only refresh 2026-09-27: kernel 6.12.0-211.58.1; NVIDIA 615.71.09 module/DKMS package installed for current kernel, but no loaded NVIDIA module or device nodes and `nvidia-smi` fails. Docker/containerd/Podman inactive. | GPU unavailable pending approved driver maintenance; prior 580.178.04 acceptance is superseded for current state |
| Hypnos | 2× Quadro P4000; 12 logical CPUs; ~66.8 GB RAM | Not currently available | Read-only refresh 2026-09-27: kernel 6.12.0-211.58.1; NVIDIA 615.71.09 module/DKMS package installed for current kernel, but no loaded NVIDIA module or device nodes and `nvidia-smi` fails. Docker/containerd/Podman inactive. | GPU unavailable pending approved driver maintenance; prior 580.178.04 acceptance is superseded for current state |

Read-only live refresh (2026-09-26) supersedes the earlier Tartarus/Hypnos
native-CUDA and reboot-persistence claims: both Rocky hosts currently have
NVIDIA 615.71.09 installed, but the kernel reports that the P4000 GPU is not
included in the driver and no NVIDIA device nodes are available. NVIDIA's
615.71.09 support list classifies the P4000 among GPUs maintained through the
580.xx legacy driver branch. This points to a driver-branch mismatch, not a
missing build toolchain or Secure Boot issue. No driver changes or reboot were
performed. The prior 580.178.04 acceptance remains historical evidence only.

Hermes is reachable and has a working native 590.48.01 driver for its RTX 2080s;
Docker is active, but container GPU injection and reboot persistence were not
checked. Thanatos remains unqualified: the live read-only refresh confirms its
RTX 2080, with `nouveau` loaded and `nvidia-smi` unavailable. No host was
modified. Container-backed placement still requires a bounded execution proof.

## Placement contract

HADES may reason from this map only after reconciling current availability:

- Proxmox is authoritative for current hypervisor and guest runtime.
- NetBox is authoritative for intended inventory and topology.
- Kuma is authoritative for observed service/host availability.
- A GPU is selectable for a workload only when its host is reachable and the
  current acceptance record proves the required driver/runtime capability.
- A workload requiring a stated VRAM amount must not be placed from card count
  alone; the map must contain a verified VRAM value and current free capacity.

## Smallest remaining contracts

1. In an approved maintenance window, restore the supported NVIDIA 580.xx
   legacy driver branch on Tartarus and Hypnos, then repeat native CUDA and
   reboot-persistence checks. Do not alter either host during this read-only
   campaign.
2. On Hermes, verify container GPU injection and reboot persistence; on
   Thanatos, resolve Secure Boot/`nouveau` policy only in an approved window.
   Complete explicit passthrough checks on Erebus; Alexandra currently exposes no GPU IOMMU group.
3. Add verified VRAM/free-capacity fields for the remaining candidates before enabling workload-to-resource
   recommendations in the live owner path.
