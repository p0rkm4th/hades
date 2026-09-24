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
| Alexandra | GTX 660; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | CPU/virtualization online; GPU runtime unverified and IOMMU not observed | Proxmox/storage pool; no GPU workload placement |
| Erebus | Quadro P4000; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | CPU/virtualization online; GPU passthrough and reboot acceptance pending | Proxmox/passthrough candidate; no native GPU placement yet |
| Hermes | 2× RTX 2080; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | NVIDIA/DKMS and Docker were staged; controlled reboot did not restore ARP/SSH/management reachability; console/power recovery required | Fedora GPU pool unavailable until recovery and post-recovery acceptance |
| Thanatos | RTX 2080; 12 logical CPUs; 31.2 GiB RAM | UNVERIFIED / UNVERIFIED | Host online with healthy temporary management plane; Secure Boot enabled and `nouveau` active despite staged NVIDIA/DKMS packages | Temporary management pool; GPU placement requires an approved firmware/driver maintenance window |
| Tartarus | 4× Quadro P4000; 12 logical CPUs; 62.2 GiB RAM | 8 GiB each / ~8.1 GiB free each at capture | SSH recovered; `nvidia-smi`, CUDA Driver API smoke, and `nvidia-container-cli` pass; Podman 5.8.2 + NVIDIA CDI configured; no local image for execution test; reboot persistence PASS | Native Rocky high-density GPU pool; container-backed placement awaits an execution proof |
| Hypnos | 2× Quadro P4000; 12 logical CPUs; 62.2 GiB RAM | 8 GiB each / ~8.1 GiB free each at capture | SSH recovered; `nvidia-smi`, CUDA Driver API smoke, and `nvidia-container-cli` pass; Podman 5.8.2 + NVIDIA CDI configured; no local image for execution test; reboot persistence PASS | Native Rocky batch GPU pool; container-backed placement awaits an execution proof |

The P4000 counts, exact VRAM, current free capacity, driver health, CUDA
Driver API smoke, and disk health are verified on Tartarus and Hypnos. Podman
and NVIDIA CDI are configured; controlled reboot persistence passed, but
GPU-container execution remains open.
The RTX 2080 and GTX 660 entries likewise do not imply active CUDA capacity.

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

1. Capture GPU-container evidence on Tartarus and Hypnos before enabling
   container-backed placement; use an already-approved local image and do not
   pull one solely for qualification.
2. Recover Hermes at console/power level, then capture `nvidia-smi`, CUDA,
   container-GPU, and persistence evidence; resolve Thanatos Secure Boot/
   `nouveau` policy in a maintenance window and complete the explicit
   passthrough checks on Erebus.
3. Add verified VRAM/free-capacity fields for the remaining candidates before enabling workload-to-resource
   recommendations in the live owner path.
