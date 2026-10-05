# Homelab read-only integration plan

The owner has authorized read-only activation for the current connected LAN.
Dedicated Proxmox, NetBox, and Uptime Kuma read-only inputs are provisioned and
their live read paths are accepted through the owner-scoped HADES route. Kuma
is exposed to HADES through its LAN-scoped published status page only.
The current upstream MCP candidate evaluation is recorded in
[`docs/homelab-mcp-evaluation.md`](homelab-mcp-evaluation.md).

## Current source and runtime checkpoint

Public HADES `main` is `b17ce8e733d777ae7e0c7a7d5af15a1948671ae9`; Public CI
run `37252630983` passed. The canonical summary retains the monitor source's
`last_updated` value as `observed_at`; response freshness remains a separate
field. This source change is not deployed. Runtime overlay and adapter hashes
are kept in the protected operator record and must be rechecked before a
rollout. The current active composition is not assumed to match repository
source.

The read layer remains **PARTIAL**: synthetic contracts and prior targeted
owner/household dogfood do not establish live stale-source, contradiction,
native service-health, network-trend, or restoreability acceptance. Backup job
or task evidence does not prove artifact validation, independent custody, or a
successful restore. Unknown and incomplete source coverage must remain explicit.

## Authority boundaries

| Domain | Canonical source | Planned HADES access | Write authority |
|---|---|---|---|
| Virtualization | Proxmox VE | API reads for nodes, guests, status, and resources | None |
| Inventory/topology | NetBox | REST `GET` reads for approved objects | None |
| Availability | Uptime Kuma | Published status-page data or metrics, where intentionally exposed | None |
| Hardware capability | Tracked observed capability matrix | Timestamped CPU/RAM/GPU inventory; freshness is FRESH for observations no older than seven days, STALE beyond that, or UNKNOWN for missing/invalid/future timestamps. This does not establish live availability or utilization | None |
| Host operations | Dedicated restricted SSH account, only if later approved | Explicitly scoped read commands | None |

Hindsight may supply remembered labels or locations, but live status always
comes from the relevant canonical system. HADES must report stale, unavailable,
or partial data rather than infer health.

Household users do not receive owner topology or raw homelab source output. If
there is no explicitly approved household-safe live status source for a
request, HADES must answer with an explicit unknown before model or memory
fallback; it must not claim computers or services are healthy from remembered
conversation content or expose internal MCP/tool names.

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
pveum acl modify /vms/<configured-guest-id> --user svc-hades-ro@pve --role HADESVmAudit
pveum acl modify /vms/<configured-guest-id> --token 'svc-hades-ro@pve!readonly' --role HADESVmAudit
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

For multiple independent Proxmox endpoints, set one unique source ID per URL in
the same order with `HADES_PROXMOX_SOURCE_IDS`. A reviewed identity crosswalk
may be supplied separately through `HADES_HOMELAB_IDENTITY_LINKS_FILE`; keep
that file outside the repository, owned by the HADES service identity, and
mode `0600` or `0640`. It is bounded JSON with this shape:

```json
{"links":[
  {"source_identity":"proxmox:site-a:node:compute-a","netbox_device_id":17},
  {"source_identity":"kuma:monitor:4","netbox_device_id":17}
]}
```

The adapter constructs Proxmox identities as
`proxmox:<configured-source-id>:<resource-type>:<resource-id>` and Kuma monitor
identities as `kuma:monitor:<monitor-id>`. Proxmox-to-NetBox links join only
the explicitly identified resource and NetBox device ID. A Kuma link records
the monitored device as a parent association; it does not merge that monitor's
service health into the device's host health. When a stable ID exists but no
reviewed link joins it, same-name records remain separate and the response
reports the missing identity link. Duplicate display names within one source
are disambiguated with their stable source IDs instead of overwriting a row.
Malformed, duplicate, oversized, symlinked, or group/world-readable crosswalks
fail closed for the link read; they never trigger inventory writes.

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

The composed summary returns a separate observation record per configured
Proxmox endpoint, NetBox, and Uptime Kuma, with `AVAILABLE`, `UNAVAILABLE`, or
`NOT_CONFIGURED` plus the retrieval timestamp and bounded row count where
available. Failure of one independent Proxmox endpoint does not discard rows
from another endpoint; the overall result becomes `PARTIAL`. The optional
NetBox application-service catalog carries its own retrieval timestamp and
does not borrow device inventory or Kuma freshness.

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
NetBox service coverage follows its paginated `count`, `next`, and `results`
fields. HADES reports a catalog as complete only when those fields are valid,
`next` is null, the result count matches `count`, and every returned record is
projected. A known next page, count mismatch, or malformed row makes coverage
partial; missing results or invalid pagination metadata leaves coverage
unknown. Contradictory status, coverage, and row combinations are surfaced as
inconsistent. Placement answers do not infer that an unlisted service is absent
from partial or unknown coverage. The existing NetBox token needs read-only permission to view
application services for this optional catalog; when unavailable, the host/VM
summary still works and reports the service catalog as unavailable.
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

Read sources are enabled only through protected deployment configuration and
least-privilege credentials. Public source contains no concrete host identities,
addresses, resource IDs, access paths, or private inventory. The protected
operator matrix and acceptance records are maintained in `hades-infra`.

Read-only deployment provenance was rechecked after the 2026-10-05 adapter
rollout. Active `server.py` SHA-256 is `3c14a4bd22d4da57f773365860ecb24d7823360470bf0601ec65c52889d5e659` and active
`inference_view.py` SHA-256 is `90cfb99901ab1c8b0cfd994eec88ebf730940f1dc7ee445d8533e9167d011a00`; both are mode `0640` with the HADES
runtime owner/group and match reviewed candidate `6bc6063702f73665a9cf666ca14cf7057d5924e4`. Hermes was
active and its configured health endpoint returned HTTP 200 after one restart.
The adapter rollout made no Hermes overlay or source-access change. The last
separately recorded composed overlay hash is
`1e731bee9385d8f918ddceadb374796b5c730e52f0adae38e6dc758d7f777f91`; it is a
composed runtime artifact, not the base public `sitecustomize.py`. Candidate
`6bc6063702f73665a9cf666ca14cf7057d5924e4` passed Public CI `37245877931` and NYX-002 review. Seven fresh
authenticated owner/household chats passed with zero turn errors; household
topology checks were false. The candidate has not yet been promoted to public
main. These are source/runtime and targeted dogfood facts; remaining campaign
gaps stay open.


Proxmox supplies hypervisor and guest runtime observations within its configured
read scope. When the effective-permissions endpoint is readable, HADES reports
whether guest visibility is cluster-wide or selected-scope; unavailable ACL
evidence stays `UNKNOWN` and must not be inferred from the returned guest rows.
The scope read is read-only and does not expand permissions. A broad `/vms`
inventory response alone is not proof that every guest was visible to the token;
explicit exclusions remain partial coverage rather than being presented as a
complete cluster view.
NetBox supplies intended inventory and topology. Uptime Kuma supplies
availability observations. Service-native and inference APIs supply only their
own reported state. These sources can disagree; HADES must preserve the source,
retrieval time, and conflict rather than choosing an arbitrary green result.

HADES does not query guest-agent operating-system details unless a separate
read privilege is explicitly configured and justified. It exposes no broad shell
or infrastructure mutation interface. Household users receive only approved
service-level status, with private topology and owner-only infrastructure
capabilities withheld.

## Current telemetry coverage

Available measurements depend on the source and its current permissions. A
point-in-time resource gauge is not a historical trend or root-cause diagnosis.
For configured Proxmox sources, the adapter may expose the node rows returned
by the existing read-only cluster-resource feed, including online node CPU
fraction and memory used/total. These rows carry the Proxmox source identity
and retrieval timestamp, are explicitly a bounded observed sample rather than
a complete node inventory, and are omitted when source identity or freshness
is missing. Owner answers must keep host/node readings separate from guest,
GPU, and process load; household users do not receive host metrics.
Host operating-system state, in-guest service health, filesystem capacity,
network trends, GPU utilization, and backup restoreability remain `UNKNOWN`
unless a currently configured source explicitly provides that evidence.

### Provider inventory and live GPU telemetry

Provider-native model inventory is optional and owner-only. Configure
`HADES_INFERENCE_ENDPOINTS_JSON` as a JSON list of endpoint records with a
stable `id`, `url`, and optional `provider` (`ollama` by default or
`openai-compatible`), `token_file`, and `ca_file`. Keep this deployment-specific
value and any token or CA material outside the public repository. Token-bearing
endpoints must use HTTPS. Ollama catalog and loaded-model reads are separate
observations; OpenAI-compatible catalogs do not provide a standard residency
read. Neither path sends a generation request.

Live GPU utilization/free-VRAM is a separate optional owner-only source,
configured through `HADES_GPU_TELEMETRY_CONFIG_FILE`. Its protected profile
contains only pre-approved endpoint IDs, hostnames, a dedicated non-sudo SSH
identity, and pinned `known_hosts`; the adapter accepts no caller-supplied host
or command and invokes the fixed `hades-gpu-telemetry-v1` command. Each remote
account must enforce the documented ForceCommand contract. Missing, stale,
partial, or unavailable data remains unknown/partial. GPU readings are
point-in-time headroom evidence, not a model-fit guarantee; artifact size,
quantization, context, KV cache, and runtime behavior still matter.

The Hermes owner route exposes provider inventory and GPU telemetry only for
owner homelab turns. Capacity/placement questions use one combined read that
preserves Proxmox/NetBox/availability, hardware, provider, and GPU source
results independently. Household users do not receive these infrastructure
tools. Provider and GPU reads cannot mutate endpoints or hosts. Validate the
profile and run the synthetic contracts before activating private endpoints.

The runtime must distinguish host reachability, guest power state, service
process state, endpoint health, and a successful functional request. Stale
observations cannot be promoted to live truth, and one unavailable optional
source must not erase unrelated results.

### HADES Core guest identity

If the Proxmox guest running HADES uses a deployment-specific name, provide
that name through the protected `HADES_CORE_PROXMOX_GUEST_NAMES` environment
variable (comma-separated when aliases are needed). Do not commit real guest
names to source or fixtures. Without an explicit match in the current guest
inventory, placement remains unknown; HADES does not infer the guest from an
IP address or a historical label.
