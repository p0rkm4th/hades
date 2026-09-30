# Homelab read-only integration plan

The owner has authorized read-only activation for the current connected LAN.
Dedicated Proxmox, NetBox, and Uptime Kuma read-only inputs are provisioned and
their live read paths are accepted through the owner-scoped HADES route. Kuma
is exposed to HADES through its LAN-scoped published status page only.
The current upstream MCP candidate evaluation is recorded in
[`docs/homelab-mcp-evaluation.md`](homelab-mcp-evaluation.md).

## Authority boundaries

| Domain | Canonical source | Planned HADES access | Write authority |
|---|---|---|---|
| Virtualization | Proxmox VE | API reads for nodes, guests, status, and resources | None |
| Inventory/topology | NetBox | REST `GET` reads for approved objects | None |
| Availability | Uptime Kuma | Published status-page data or metrics, where intentionally exposed | None |
| Hardware capability | Tracked observed capability matrix | Confirmed CPU/RAM/GPU inventory, explicitly separate from live availability | None |
| Host operations | Dedicated restricted SSH account, only if later approved | Explicitly scoped read commands | None |

Hindsight may supply remembered labels or locations, but live status always
comes from the relevant canonical system. HADES must report stale, unavailable,
or partial data rather than infer health.

## Credential-independent preparation

Before any future integration is enabled, run
[`scripts/check-homelab-readonly-config.sh`](../scripts/check-homelab-readonly-config.sh)
with the owner-approved values in a protected environment. The preflight only
checks that all required values have the expected shape; it never contacts a
homelab endpoint and never prints credential values. It exits with status `2`
when the owner gate is still incomplete and fails with status `1` for invalid
configuration.

### Proxmox VE

Create a dedicated read-only service identity and privilege-separated API
token. Proxmox calculates a separated token's effective rights from the
intersection of user and token ACLs, so both need the required read roles. Keep
token ACLs narrower than the user's where possible. For the current HADES
reads, the minimum roles are node audit (`Sys.Audit`) at `/` and VM audit
(`VM.Audit`) only at each explicitly approved guest path. On a new Proxmox
installation, an operator can define and assign these roles as follows (repeat
per independent Proxmox installation; substitute the approved guest IDs and
token name):

```bash
pveum role add HADESNodeAudit --privs Sys.Audit
pveum role add HADESVmAudit --privs VM.Audit
pveum acl modify / --user svc-hades-ro@pve --role HADESNodeAudit
pveum acl modify / --token 'svc-hades-ro@pve!readonly' --role HADESNodeAudit
pveum acl modify /vms/802 --user svc-hades-ro@pve --role HADESVmAudit
pveum acl modify /vms/802 --token 'svc-hades-ro@pve!readonly' --role HADESVmAudit
```

Verify both views with `pveum user permissions <userid>` and
`pveum user token permissions <userid> <token-name>` on the Proxmox host.
Start with read requests for `/cluster/resources`, node status, and guest
configuration/status. Do not grant write privileges. If optional QEMU
guest-agent metadata is separately approved, grant only
`VM.GuestAgent.Audit` at the approved guest path; do not use
`VM.GuestAgent.Unrestricted`, file-read/write, or filesystem-management
privileges for status reporting.

The first live acceptance must inspect the returned resource types as well as
HTTP success: `/cluster/resources` can return a node-only view while guest rows
are still absent. Acceptance for guest coverage requires the intended VM rows
and successful reads of only the explicitly approved guest-agent information.

Required private placeholders:

```dotenv
HADES_PROXMOX_URL=https://proxmox.example.invalid:8006/api2/json
HADES_PROXMOX_TOKEN_ID=svc-hades-ro@pve!readonly
HADES_PROXMOX_TOKEN_SECRET=<private>
```

### NetBox

Use a current v2 API token with write access disabled and an expiry. Scope the
owning user or group to the approved read objects; object-based permissions
can further constrain visibility. Begin with sites, devices, interfaces, and
IP prefixes only if those are the owner-approved inventory domains.

```dotenv
HADES_NETBOX_URL=https://netbox.example.invalid
HADES_NETBOX_TOKEN=<private-v2-token>
```

### Network discovery

The HADES-owned bounded scan worker is enabled for the explicitly authorized
connected-LAN CIDR. The reusable parser in
`integrations/homelab-readonly/discovery.py` accepts bounded Nmap XML evidence,
requires a valid retrieval timestamp, and enforces target/host scope without
invoking a scanner. It accepts UTF-8 only and rejects DTD/entity declarations
because Nmap output does not need them and entity expansion is unsafe for
untrusted evidence. Scan
output is observed evidence only: it must carry target scope and retrieval time, must
not execute arbitrary shell, and must not silently create or update NetBox
records. See the candidate selection and command boundary in
[`homelab-mcp-evaluation.md`](homelab-mcp-evaluation.md).

The bounded scan runner also rejects targets larger than 4,096 addresses
before starting Nmap, even when a containing network is allowlisted. Its
current TCP-connect profile uses fixed ports, a bounded timeout, no scripts or
version probing, and a bounded packet rate.

`integrations/homelab-readonly/catalog.py` can turn normalized scan evidence
into a transient review projection containing observed IPs, hostnames, open
ports, and NetBox context matches by exact DNS name or canonical IP. DNS
matching folds case and an optional terminal root dot only; it does not guess
search suffixes. It accepts
NetBox's nested `primary_ip`/`primary_ip4`/`primary_ip6` assigned-address
objects, including CIDR values, alongside flat address fields. Every candidate is marked
`REVIEW_REQUIRED`, includes `writes_performed: false`, and is never a second
HADES inventory or an automatic NetBox reconciliation.

### Uptime Kuma

Prefer a deliberately published status page or metrics endpoint for read-only
availability summaries. Kuma's internal Socket.IO API is not a stable
third-party integration surface, so it must not be adopted as a hidden
administrative dependency. Never use a push token or authenticated write path
for HADES reads.

```dotenv
HADES_UPTIME_KUMA_URL=https://status.example.invalid
HADES_UPTIME_KUMA_STATUS_SLUG=<owner-approved-slug>
```

## Owner acceptance prompts

Once credentials are explicitly supplied, verify through the HADES owner path:

- “What’s running in the lab?”
- “What’s down?”
- “Where does `<owner-approved host or service>` live?”
- “What’s wrong with the lab?”
- “Show me the source and freshness of that answer.”

Each result must include source, retrieval time/freshness, and a clear failure
state when a source is unavailable. A request such as “restart that server”
must remain an authorization-boundary test and must not perform a write.

The public synthetic response contract in
`scripts/test-readonly-response-contracts.py` exercises these metadata,
coverage, partial-failure, and read-only invariants without contacting a real
homelab service.

The reusable read-only MCP composition adapter is in
`integrations/homelab-readonly/`. Its `homelab_summary` tool fetches only
configured HTTP(S) GET endpoints and delegates authority-aware composition to
`reconcile.py`; the focused contract is
`scripts/test-homelab-readonly-adapter.sh`. Missing or failed sources produce
partial results and errors rather than substituting memory or another source.
The owner summary also reads NetBox's application-services endpoint and
projects bounded service names, parent devices, declared addresses, and
validated TCP/UDP/SCTP port mappings. Those are intended-inventory facts;
they never imply that a process is running or reachable. A matching Uptime
Kuma probe or a separate explicit check is required for current liveness.
The existing NetBox token needs read-only permission to view application
services for this optional catalog; when unavailable, the host/VM summary
still works and reports the service catalog as unavailable.
The adapter accepts the documented base inputs above and derives only bounded
read paths (`/cluster/resources`, `/api/dcim/devices/`, `/api/ipam/services/`, and the selected
published `/api/status-page/heartbeat/<slug>` JSON endpoint, joined with the
public `/api/status-page/<slug>` monitor metadata); deployment-specific
derived URL variables remain supported for private composition. Runtime bearer
values are read only from protected token files, never from repository
configuration.
For standalone Proxmox nodes, `HADES_PROXMOX_RESOURCES_URLS` and
`HADES_PROXMOX_TOKEN_FILES` accept matching comma-separated lists so runtime
state from more than one node is composed without inventing a cluster.
During a management-plane restore, explicit `HADES_NETBOX_DEVICES_URL`,
`HADES_KUMA_STATUS_URL`, and `HADES_KUMA_CONFIG_URL` overrides switch the
read-only adapter to restored endpoints without changing source authority;
`scripts/test-homelab-endpoint-switch-contract.sh` verifies those overrides
and fails closed on mismatched Proxmox endpoint/token lists.
Its `homelab_discovery_scan` tool invokes only the bounded worker inside
`HADES_DISCOVERY_ALLOWED_NETWORKS`; its `homelab_discovery_candidates` tool
accepts normalized evidence and returns the review-only catalog projection.
Neither tool performs inventory or management writes.

[`scripts/test-homelab-fixture.sh`](../scripts/test-homelab-fixture.sh) adds a
disposable loopback fixture for the next integration step. It exposes minimal
Proxmox, NetBox, and Uptime Kuma-shaped read endpoints with an online node, a
degraded node, a running guest, a stopped guest, a runtime-versus-inventory
node contradiction, and a stale monitoring result. The fixture verifies that
Proxmox remains authoritative for current runtime placement, NetBox remains
the intended inventory source, Kuma is reported as stale availability
observation, and writes return `405`. It is exercised in public CI; no real
homelab endpoint or credential is involved.

## Current activation state

The current connected-LAN discovery contract is authorized and has completed a
real read-only scan. The result is transient review evidence and is not a
canonical inventory update. Proxmox and NetBox are
`AUTHORIZED / READ-ONLY`; Uptime Kuma is
`AUTHORIZED / READ-ONLY ACCEPTED` at the published
`hades-infrastructure` status path. Real failure, freshness, conflict, and
write-surface acceptance remains required for every live source.

**Proxmox credential correction (2026-09-27):** the privilege-separated
Alexandra/Erebus tokens originally lacked token-side ACLs, so the approved
`/cluster/resources` reads returned node-only rows. Restored the existing
read-only contract with `Sys.Audit` at `/` and `VM.Audit` only at the explicitly
approved CT 803 (`/vms/803`) and HADES VM 802 (`/vms/802`) paths. The active
protected token inputs now return exactly one node and one approved guest row
per PVE instance, including point-in-time CPU/memory/disk allocation/network
counters/uptime; historical VM 800/801 and other Erebus guest rows remain
inaccessible to these tokens. No VM write privileges or user ACLs changed.
QEMU guest-agent OS/filesystem calls are still outside the configured contract;
no `VM.GuestAgent.Audit` privilege was granted. The audit and exact scopes are
recorded in [`docs/current-blockers.md`](current-blockers.md).

The owner API uses the read-only `homelab_owner_snapshot` for combined
status-and-hardware questions. It composes the live summary with the observed
capability matrix while preserving source authority: Proxmox supplies current
runtime, NetBox intended inventory, Kuma observed availability, and the matrix
only supplies supplemental hardware evidence. A GPU cannot be treated as
available, CUDA-capable, or placeable without current runtime and acceptance
evidence. The deployed owner profile retains separate bounded discovery tools;
it does not expose a broad shell or homelab control plane.

Owner requests for a server IP, port, endpoint, or firewall destination first
read the bounded NetBox application-service catalog. HADES reports an endpoint
only when one matching service record provides a single address and validated
protocol/port mapping. It states that this is inventory, not evidence the
service is running or externally reachable. Missing, unavailable, incomplete,
or ambiguous records do not trigger model-based guesses or template
provisioning, and the response states that no server or firewall change was
made. A follow-up such as “Perfect, continue” closes against that same
no-action result instead of falling through to a generic response. Household
sessions cannot use this owner endpoint shortcut.

References: [Proxmox API-token monitoring example](https://pve.proxmox.com/pve-docs/pve-admin-guide.pdf),
[Proxmox token permission separation and ACL rules](https://github.com/proxmox/pve-docs/blob/master/pveum.adoc),
[NetBox REST API authentication and read-only tokens](https://netbox.readthedocs.io/en/stable/integrations/rest-api/),
[Uptime Kuma API documentation and stability warning](https://github.com/louislam/uptime-kuma/wiki/API-Documentation/692198f84f3675a53a8ece7eb91a6a84566ee98e).

## Current telemetry coverage

The current Proxmox token response contains point-in-time CPU ratio, memory,
bounded disk allocation, network counters, and uptime for the two explicitly
approved guests and their hosts. These are current gauges only, not historical
trends or proof of why a service feels slow. Uptime Kuma contributes only its
intentionally published monitor observations. Guest operating-system
identity, in-guest major-service state, actual guest filesystem free space, and
historical network or storage trends remain unknown unless a separately
approved canonical source supplies them. HADES must state that limit instead
of inferring a diagnosis from a running VM or a hardware inventory row.
