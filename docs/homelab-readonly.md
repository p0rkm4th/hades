# Homelab read-only integration plan

This document describes optional read-only integrations. Each deployment
must explicitly approve its own sources and credentials. The current upstream
MCP candidate evaluation is recorded in
[`docs/homelab-mcp-evaluation.md`](homelab-mcp-evaluation.md).

## Authority boundaries

| Domain | Canonical source | Planned HADES access | Write authority |
|---|---|---|---|
| Virtualization | Proxmox VE | API reads for nodes, guests, status, and resources | None |
| Storage and backup | Proxmox storage metadata or component-native backup verification | Separate, explicitly approved read inputs; runtime-resource reads alone do not prove storage or backup health | None |
| Inventory/topology | NetBox | REST `GET` reads for approved objects | None |
| Availability | Uptime Kuma | Published status-page data or metrics, where intentionally exposed | None |
| Hardware capability | Tracked observed capability matrix | Confirmed CPU/RAM/GPU inventory, explicitly separate from live availability | None |
| Inference catalog and residency | Provider-native APIs | Ollama `GET /api/tags` and `GET /api/ps`, or OpenAI-compatible `GET /v1/models`; bounded reads only | None |
| Host operations | Dedicated restricted SSH account, only if later approved | Explicitly scoped read commands | None |

Hindsight may supply remembered labels or locations, but live status always
comes from the relevant canonical system. HADES must report stale, unavailable,
or partial data rather than infer health.

The capability matrix is an observed inventory snapshot, not current model
availability, GPU load, or runtime health. Provider-native inference reads are
disabled unless `HADES_INFERENCE_ENDPOINTS_JSON` is explicitly configured.
Each entry has a stable ID, provider kind (`ollama` or `openai-compatible`),
and base URL; optional token and CA paths are protected operator inputs.
Tokens require HTTPS. The owner-only inventory reports provider catalog
entries, plus Ollama active models and provider-reported VRAM residency when
available, with a live check time and per-endpoint status. OpenAI-compatible
catalogs do not establish current residency. `READABLE` means only the
configured catalog (and, for Ollama, residency) APIs responded. It never
equates model artifact size with required memory or mutates a provider.
Catalog and residency responses do not prove that a generation request works.

Use the protected identity-link file to join `inference:<endpoint-id>` to a
canonical numeric NetBox device ID. Unlinked inference endpoints remain
separate source observations; display names and addresses are not join keys.
Missing or stale links do not make an endpoint healthy or identify its host.

For example, a private deployment may configure a JSON array like:

```dotenv
HADES_INFERENCE_ENDPOINTS_JSON='[{"id":"provider-a","provider":"ollama","url":"https://inference.example.invalid"}]'
```

For Ollama, the endpoint must expose its read-only API. For an
OpenAI-compatible provider, it must expose `GET /v1/models`. Never place a
token value in this setting; provide only a protected token-file path when
bearer authentication is required.

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
APPROVED_GUEST_ID=${APPROVED_GUEST_ID:?set the explicitly approved guest ID}
pveum role add HADESNodeAudit --privs Sys.Audit
pveum role add HADESVmAudit --privs VM.Audit
pveum acl modify / --user svc-hades-ro@pve --role HADESNodeAudit
pveum acl modify / --token 'svc-hades-ro@pve!readonly' --role HADESNodeAudit
pveum acl modify "/vms/${APPROVED_GUEST_ID}" --user svc-hades-ro@pve --role HADESVmAudit
pveum acl modify "/vms/${APPROVED_GUEST_ID}" --token 'svc-hades-ro@pve!readonly' --role HADESVmAudit
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
HADES separately reads `/access/permissions` to classify the token's effective
guest-audit scope. `ALL_GUESTS` means broad VM audit is present without a
reported guest exclusion; `SELECTED_GUESTS` means audit is scoped to guest or
pool paths; `NO_GUEST_AUDIT` means no applicable grant was observed. The
`scoped_guest_count` is an exact count only when every applicable grant names
an individual `/vms/<id>` path. Pool or other non-enumerable scoped grants
report `null`; HADES must not present that as zero. These permission results
describe effective authorization, while returned resource rows show what the
API actually exposed on that read. Neither alone proves every guest is healthy.

Use protected token files containing only the token secret. Proxmox token IDs
are separate non-secret identifiers. URL, token-ID, and token-file lists must
have matching counts, except that one token ID or token file may be shared
across the configured Proxmox URLs. Token files must be regular, non-symlink
files with mode `0600` or `0640`.

```dotenv
HADES_PROXMOX_RESOURCES_URLS=https://pve-a.example.invalid:8006/api2/json/cluster/resources,https://pve-b.example.invalid:8006/api2/json/cluster/resources
HADES_PROXMOX_TOKEN_IDS=svc-hades-ro@pve!readonly-a,svc-hades-ro@pve!readonly-b
HADES_PROXMOX_TOKEN_FILES=/run/hades/pve-a.token,/run/hades/pve-b.token
HADES_PROXMOX_CA_FILE=/run/hades/proxmox-ca-bundle.pem
```

For a single standalone endpoint, `HADES_PROXMOX_URL` may provide the API base
and `HADES_PROXMOX_TOKEN_FILE` the one protected secret file. The adapter
derives `/cluster/resources`; `HADES_PROXMOX_TOKEN_IDS` is still required for
the Proxmox API-token header. Inline `HADES_PROXMOX_TOKEN_SECRET` and singular
`HADES_PROXMOX_TOKEN_ID` are not consumed by the adapter and are rejected by
preflight.

### NetBox

Use a current v2 API token with write access disabled and an expiry. Scope the
owning user or group to the approved read objects; object-based permissions
can further constrain visibility. Begin with sites, devices, interfaces, and
IP prefixes only if those are the owner-approved inventory domains.

```dotenv
HADES_NETBOX_URL=https://netbox.example.invalid
HADES_NETBOX_TOKEN_FILE=/run/hades/netbox.token
```

The token file contains the read-only bearer token and must be a regular,
non-symlink file with mode `0600` or `0640`. Inline `HADES_NETBOX_TOKEN` is not
consumed by this adapter and is rejected by preflight. Uptime Kuma uses
`HADES_UPTIME_KUMA_URL` plus `HADES_UPTIME_KUMA_STATUS_SLUG` and, when its
published page requires authentication, an optional protected
`HADES_KUMA_TOKEN_FILE`.

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

A matching fresh monitor supports a statement about that configured probe only;
it does not establish that the application is usable. If no stable identity link
connects the monitor to the service named in the question, report the monitor
observation and say its target is unverified. A successful NetBox inventory read
does not prove that a particular Kuma monitor checks NetBox. A down observation
does not establish its cause.

## Owner acceptance prompts

Once credentials are explicitly supplied, verify through the HADES owner path:

- “What’s running in the lab?”
- “What guests are running on `<owner-approved Proxmox host>`?”
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
The service catalog separates API read status from inventory coverage: an
empty result is `coverage=EMPTY`, a proven complete result is `COMPLETE`, a
paginated or truncated result is `PARTIAL`, and missing pagination metadata is
`UNKNOWN`. `status=OK` means the source responded; it does not mean service
placement is populated or complete.
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

Deployment-specific token identities, ACL paths, guest IDs, and live resource
rows belong in the private infrastructure repository. The public adapter
contract requires bounded read-only Proxmox access and does not encode any
deployment's hostnames, resource IDs, or permission assignments. Guest-agent
OS and filesystem reads remain outside the adapter contract unless separately
configured and authorized.

The owner API uses the read-only `homelab_owner_snapshot` for combined
status-and-hardware questions. It composes the live summary with the observed
capability matrix while preserving source authority: Proxmox supplies current
runtime, NetBox intended inventory, Kuma observed availability, and the matrix
only supplies supplemental hardware evidence. A GPU cannot be treated as
available, CUDA-capable, or placeable without current runtime and acceptance
evidence. Hardware-matrix observations older than seven days are returned as
`STALE`; a missing, malformed, or future observation time is `UNKNOWN`. The
bounded hardware facts remain available as historical inventory, but an owner
snapshot containing stale or unknown hardware evidence is `PARTIAL`. The
deployed owner profile retains separate bounded discovery tools;
it does not expose a broad shell or homelab control plane.

The owner-only `homelab_backup_status` read reports Proxmox `vzdump` job
configuration and a bounded recent archived-task sample per configured node.
Task reads are filtered to each token's effective `VM.Audit` guest scope. A
selected-guest grant is reported as partial; a missing or unreadable permission
scope yields unknown task history and prevents task rows from being returned.
An empty task list under a selected scope does not mean that no other guest was
backed up. The read does not establish that a job succeeded merely because it
is configured, and it does not verify backup contents, guest-application data,
storage health, other backup systems, off-site custody, or restoreability. An
unavailable or partially readable Proxmox source remains unknown/partial in the
response.
This is separate from HADES Backup Checks, which track their own configured
coverage and must not be presented as a substitute for Proxmox backup evidence.

The owner-only `homelab_recent_activity` read returns an explicitly selected
window up to seven days of archived Proxmox guest tasks and NetBox device/service
records whose `last_updated` falls within that window. Proxmox task metadata is
filtered against each token's effective permissions; selected-guest and
pool-scoped grants are reported as partial. NetBox values are reduced to object
type, stable record ID, name, and timestamp. Field diffs, deletions, and prior
state are not available from this read. Usernames, UPIDs, task logs, custom
fields, and raw upstream values are omitted. This is bounded activity evidence,
not a complete homelab change log; successful tasks do not prove resulting
configuration or application health. Household sessions are denied access to
this owner-only history.

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

Each `homelab_summary` response includes per-source read provenance:
`retrieved_at` in UTC, request duration, row count, and a bounded source-read
status. `HEALTHY` at this level means the API read succeeded; it does not mean
that the monitored hosts or services are healthy. Uptime Kuma's `last_updated`
remains the time of its health observation and is kept distinct from the time
HADES retrieved the status page. With multiple
independent Proxmox endpoints, each endpoint is read separately; a failed
endpoint does not discard rows from the others. The Proxmox aggregate and the
whole summary become `DEGRADED` / `PARTIAL` when any configured endpoint fails.
Diagnostics use stable error categories and never include raw upstream
exception text or URLs, which can contain private endpoint details. A malformed
Proxmox endpoint list likewise does not prevent independent NetBox and Kuma
reads.

The read model sets `currently_online` to `true` only for Proxmox `online` or
`running` states and to `false` only for explicit `offline` or `stopped`
states. A missing Proxmox row or unfamiliar state leaves it `null`; absence
from one runtime source is not evidence that a physical host is down. The
bounded summary retains up to 64 compact source records so alphabetical
truncation cannot silently hide most configured hosts or monitors.

An owner can ask which guests Proxmox reports on a named host. HADES matches
the guest's runtime node and stable Proxmox endpoint identity; ambiguous or
missing source identity fails closed. This is only the current VM/container
list for that Proxmox host. It does not enumerate application services or
prove that any guest workload is healthy. Household sessions do not receive
host or guest names through this query.

Cross-source records are joined only through stable source identities and an
explicit private mapping to a NetBox device ID. Display-name agreement and IP
agreement alone never merge Proxmox, NetBox, and Kuma rows. Set
`HADES_PROXMOX_SOURCE_IDS` to one unique identifier per configured Proxmox
endpoint when its records need cross-source links; otherwise generic
`endpoint-N` labels are local to the configured endpoint order and cannot be
used for durable links. An optional
`HADES_HOMELAB_IDENTITY_LINKS_FILE` may point to a protected JSON file with
this shape:

```json
{
  "links": [
    {"source_identity": "proxmox:pve-a:qemu:101", "netbox_device_id": 75},
    {"source_identity": "kuma:monitor:7", "netbox_device_id": 75}
  ]
}
```

The file must be a regular non-symlink file with mode `0600` or `0640`. It
contains identifiers only; NetBox continues to own inventory fields, Proxmox
runtime fields, and Kuma probe results. Missing mappings remain separate and
are surfaced as unlinked or same-name warnings. Multiple source records
mapping to one NetBox ID or an intended-node/runtime mismatch are reported as
conflicts. A linked ID absent from the current NetBox response is also a
conflict. Invalid link configuration fails closed for the composition and
does not trigger a display-name fallback.

Owner questions such as “What is `<node>` running?” compose the node's
explicitly linked provider catalog and current loaded-model report with the
observed capability inventory and any matching fresh Kuma check. Provider
catalog/residency reads do not establish generation health, host runtime health,
CPU/GPU utilization, or free VRAM. Those fields stay unknown unless a separate
current source supports them. Stable NetBox device identity is required to
associate a provider endpoint with a named machine. Placement questions may
list linked, responding endpoints and their current loaded models. HADES must
not rank or recommend a host unless current per-host capacity evidence and the
model's runtime memory requirements are available. A stale hardware role or
responding endpoint alone is not placement evidence. A free-GPU question stays
unknown without live utilization and free-VRAM evidence. If a machine has no
linked inference endpoint, HADES falls back to Proxmox runtime and NetBox role
when present; a NetBox record alone never becomes an online claim.

Owner service-location questions use only the NetBox application-service
catalog. HADES answers placement only when catalog coverage is complete and a
single matching record identifies a parent device; an empty, partial, or
unavailable catalog is reported as insufficient evidence. Intended placement
is not current liveness. Household sessions do not receive host, address, or
port details through this path.

Household health questions about the approved game server, including “Is the
game server working?”, use the same bounded service-monitor evidence as an
explicit Minecraft health question. HADES returns only a high-level result;
if no current matching check is available, it says it cannot verify the game
server. This route runs before managed-server lifecycle handling and grants no
host visibility or mutation authority. Broad questions about computer or
homelab health remain owner-only.

The HADES `Backup Check` reports the configured repository check state.
It does not establish host, VM, service, or household-data backup coverage,
independent off-site custody, or restoreability. HADES must keep those
infrastructure backup claims unknown until their own read-only sources provide
verified coverage and freshness.

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
approved canonical source supplies them. Datastore state and backup completion
also require their own read path and authorization; an HTTP 200 from
`/cluster/resources`, a running guest, or an empty backup-task listing does not
prove that storage or backups are healthy. HADES must state that limit instead
of inferring a diagnosis from a running VM or a hardware inventory row.
