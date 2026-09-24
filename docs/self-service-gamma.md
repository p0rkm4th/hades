# Gamma bounded self-service workloads

Gamma starts self-service with a plan-only product contract. The current
policy allows only the approved `minecraft`, `website`, and `linux-sandbox`
templates, validates fixed resource shapes, enforces per-owner quotas, records
ownership and explicit sharing, and requires owner confirmation. It does not
contact Proxmox, accept raw VM IDs/images/scripts, expose host mounts or
network configuration, or grant users hypervisor authority.

The repository now also contains a constrained provisioner boundary that accepts
only a confirmed `WorkloadRequest`, uses policy-owned placement, permits
creation only by the workload owner, and caches terminal canonical outcomes so
an unknown response is never blindly retried. The live executor uses the
existing least-privilege Proxmox broker, maps only the approved template, waits
for asynchronous clone/start tasks, and reconciles canonical state. A
disposable VM 854 create/read-back passed and was purged. The authenticated
owner UI now also has a bounded “show my servers” path and lifecycle adapter
for status/start/stop/restart/delete. Inventory is least-privilege: the broker
does not require pool-audit permission; managed guests are identified by the
explicit `hades-managed` tag, approved node, and approved VMID range. A tagged
VM900 was created and reconciled through the live product path, then stopped
and purged. A durable authorization-only registry now records the authenticated
owner and explicit grants; it contains no VM runtime state or private user
data. The owner DOM path has now passed status, explicit restart confirmation,
and explicit delete confirmation, including stop-before-destroy reconciliation
and registry removal. The owner path can explicitly share and revoke a workload
with configured synthetic household subjects. Authenticated DOM dogfood passed:
Household A saw and could request an approved action on the shared sandbox,
Household B could not see it, revocation immediately removed Household A's
visibility, and the owner then deleted the workload with canonical cleanup.
Restart uses a bounded graceful reboot with a confirmed stop-start fallback
when guest-agent reboot is unreliable.

The Rocky 10.2 candidate was rejected after its x86-64-v2 userspace panicked
on Erebus's i7-5930K before cloud-init or networking. The approved template
candidate is now Debian 12 GenericCloud on Erebus VM 853, with a derived image
adjustment for Proxmox's generated `eth0` cloud-init network stanza. A
disposable clone reached SSH, completed cloud-init, and reported an active
QEMU guest agent; it was purged after acceptance. The constrained credential
and canonical live executor gate are green; product wiring and household
dogfood remain.
