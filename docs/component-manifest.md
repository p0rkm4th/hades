# Component Manifest

The first dogfood slice is deployed outside this repository's source tree;
runtime secrets and persistent volumes remain outside Git.

| Component | Authority | Planned integration | Version / license / upgrade note |
|---|---|---|---|
| Hermes | intelligence and agent execution | supported upstream deployment/API | Current reconstruction pin is `HADES_HERMES_VERSION` from `config/versions.env` (0.21.2, upstream `v2026.9.11`); install the checksum-verified source into a new locked environment, never copy a seasoned venv |
| Open WebUI | owner-facing conversation interface | supported Hermes-compatible interface | Production remains 0.11.1 until live P0 acceptance; the exact 0.11.4 candidate is bound by `config/versions.env:HADES_OPEN_WEBUI_CANDIDATE_IMAGE`. Its Dockerfile applies DOCX, fail-closed JWT, LDAP empty-group, authority-revocation, Socket.IO revocation, and Channels compatibility patches; build output is software custody, not state |
| Open WebUI auth-state Valkey | JWT revocation and cross-worker Socket.IO coordination | dedicated private service in the 0.11.4 P0 Compose template | `config/versions.env:HADES_OPEN_WEBUI_VALKEY_IMAGE` pins the immutable image; AOF uses `appendfsync always`, and the persistent named volume is part of Open WebUI backup/restore |
| Hindsight | durable semantic/personal memory | Hermes external memory provider over supported client API | `ghcr.io/vectorize-io/hindsight@sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`; embedded pg0 volume; upgrade by digest |
| Agent Zero | bounded subordinate computer operator | isolated deployment with explicit objective/result boundary | pinned image digest; no shared unrestricted credentials; native A2A evaluated and retained MCP bridge is bounded |
| Grocy | canonical pantry, groceries, consumption, inventory, recipes | maintained integration, then supported API or tiny adapter | select upstream release; Grocy remains source of truth |
| Actual Budget / Finance MCP | canonical imported finance account and transaction truth | `integrations/actual-finance-readonly/` read adapter plus `integrations/actual-finance-import/` preview-only file MCP; synthetic staging only | Actual 26.9.0 server/client must be pinned together; owner authorization remains required for native import execution and no finance write authority is registered |
| Proxmox / NetBox / Uptime Kuma | homelab and availability truth | registered read-only MCP profile in `hermes/config.yaml.example`, bounded LAN discovery, and `docs/homelab-readonly.md` | owner-approved endpoints and protected token files required for live reads; no writes |
| Home Assistant | physical smart-home state/control | future selected-entity integration | deferred; least privilege required |
| n8n | deterministic workflows | existing fixed read-only templates; bounded Phase 3 canary implementation | The owner has authorized Server Health Watch, Low Inventory Summary, Weekly Household Summary, and Backup Verification only; keep the runner inactive until HADES-owned operation-time identity/resource checks and recovery acceptance pass |

## Reconstruction manifest

This is the minimum rebuild contract. Exact secret values, volume names, image
digests where private, and owner-selected endpoints belong in the operator
record. Restore order and canonical checks are detailed in
[`backup-restore.md`](backup-restore.md).

The same contract is maintained in the machine-readable
[`config/reconstruction-manifest.json`](../config/reconstruction-manifest.json)
for validators and future rebuild tooling. It contains no secret values or
private endpoints; those remain explicit operator inputs.

The authoritative public pins are maintained in
[`config/versions.env`](../config/versions.env). Every private deployment
record must carry the matching image/tag or digest rather than silently using
`latest`.

| Component | Pinned/rebuild source | Persistent state | Required private inputs | Network dependency | Startup order | Health check | Restore check |
|---|---|---|---|---|---|---|---|
| LLDAP | Pinned image digest in `deploy/lldap.compose.yaml` | Directory database and key material | JWT/key seed, admin bootstrap | Private identity network | 1 | LDAP/HTTP health and login | Isolated database restore and identity record check |
| Open WebUI | Pinned immutable base plus tracked `webui/Dockerfile`, HADES static assets, and security adapters | WebUI database, uploaded/vector data, signing key, matching assets | Image build output and database/auth secrets | LLDAP and Hermes over existing private bridges; auth-state Valkey over a dedicated internal bridge | 3 | WebUI health, login, chat reload, and required revocation-store availability | SQLite integrity, uploads/assets, old-token rejection, and restart persistence |
| Open WebUI auth-state Valkey | Pinned `HADES_OPEN_WEBUI_VALKEY_IMAGE` plus tracked Compose service | Persistent named volume `hades-open-webui-auth-state` | None; port is not published and network is internal | Open WebUI only | 2 | `valkey-cli ping`, AOF persistence | RDB/AOF restore, revoked-token rejection, and socket revocation |
| Hindsight | Pinned image with embedded PostgreSQL | PostgreSQL cluster/export | Database credentials and subject-bank policy | Hermes to private memory API over `hades-application-net` | 4 | PostgreSQL readiness and Hindsight health | Native export restore and subject-scoped marker recall |
| Grocy | Pinned image digest plus `grocy-mcp==0.2.0` and `integrations/grocy-mcp/requirements.lock` | Complete Grocy configuration/database | API key file, read by the tracked MCP launcher | Hermes to private Grocy API over `hades-grocy-net`; MCP tool allowlist in `hermes/config.yaml.example` | 5 | Grocy HTTP health and registered scoped MCP catalog | SQLite integrity, stock/list/recipe canonical checks |
| Actual Budget / Finance MCP | Pinned Actual 26.9.0 server/client plus tracked read and preview-only file adapters | Private synthetic or owner-authorized Actual state | Endpoint, budget identity, credentials, and explicit target account ID for imports | Hermes to private finance API; local file input remains inline-only | 4 | Read-only health plus finance-file preview contract | Synthetic ledger marker, preview/reconciliation contract, and read-only response; real restore is owner-gated |
| Hermes | Pinned verified upstream source archive selected by `config/versions.env:HADES_HERMES_SOURCE_URL` and checksum, plus generated unit and HADES overlay | Profile, sessions, skills, state | Provider, MCP, and service credentials | Open WebUI, Hindsight, Grocy, SearXNG, Agent Zero | 6 | Private API health and authenticated model contract | Profile parse, bounded tool call, reload/restart |
| Agent Zero | Pinned image digest in `deploy/agent-zero.compose.yaml`; optional native-login env generated from explicit private input | Dedicated operator volume/settings | Optional native UI password; an external API credential only when externally managed | Hermes to private operator API; UI remains loopback/private | 7 | Agent Zero health and live-service token match when native auth is enabled | Isolated volume restore and harmless bounded delegation |
| SearXNG | Pinned image plus tracked generated deployment and search configuration | Configuration; cache is reconstructable | Any private provider settings | Hermes to private search API | 8 | JSON search response | Config parse and provider search check |
| HADES policy/assets/adapters | Repository at pushed `main` plus deployed overlay copy | No canonical domain state | Private deployment environment variables | Loaded by Hermes; no separate authority | With Hermes | Overlay syntax, boundary, and MCP registration checks | Source/runtime match, policy tests, and smoke contract |

## Boundary rule

Hindsight may provide remembered context but cannot override live truth from
Grocy, Finance, Proxmox, NetBox, Uptime Kuma, or Home Assistant. HADES should
not add a shadow store, universal tool registry, planner, scheduler, or event
bus.

See [`stable-v1-readiness.md`](stable-v1-readiness.md) for the current
production contract, compatibility overlay inventory, recovery dependencies,
and remaining owner/authority gates.

## Configuration drift audit

The public deployment directory tracks the safe base contracts plus templates
for the formerly private application records. Runtime secrets and volumes are
not copied into Git. Staging/demo containers
are disposable and are not treated as production topology.

The audit explicitly checks both the three safe top-level Compose contracts and
the four generated application templates, including the staged OCR template.
It found no provably obsolete public compose file or adapter to delete.
The remaining drift risk is documentation-to-private-runtime parity: when a
component version, image digest, endpoint, or startup dependency changes, the
reconstruction manifest and operator record must be updated together. Ambiguous
private state is deliberately retained until an owner-authorized migration.

### Observed runtime reconciliation — 2026-09-14

The live, public-safe topology was compared with the manifest without reading
environment values or persistent data:

| Observed component | Runtime evidence | Reconciliation |
|---|---|---|
| Open WebUI | Local HADES theme image derived from pinned 0.11.1 base, LAN binding on `:3000` | The tracked Dockerfile and immutable base now explain the application layer; the local image digest remains runtime evidence only |
| SearXNG | `searxng/searxng:2026.5.31-7159b8aed@sha256:35b089054ac9b4257976107e71673d9e30ac17c9b50bbf8b4783f2f6d1d1981f`, loopback `:8080` | Generated template consumes the immutable manifest reference; tracked settings remain the public configuration source |
| LLDAP | Pinned `hades-lldap` on loopback `:17170`; separate local-only production/staging instance on `:17171` | The second instance is staging topology, not a replacement authority; identity migration must be explicitly selected |
| Grocy / Agent Zero | Pinned compose digests and loopback bindings match tracked contracts | No drift found |

The old untracked Open WebUI/Hindsight/SearXNG service definitions and Hermes
unit remain compatibility inputs only. The generated templates and verified
artifact installers are the V1 reconstruction source; private records are not
required for the generated path.

The metadata-only permission audit also found the three staged LLDAP secret
files at mode `0600`, while tracked non-secret settings remain `0644`. The
LLDAP Compose contract uses read-only bind mounts with an SELinux `Z` relabel
rather than embedding values in the repository; this preserves narrow service
access on enforcing Fedora/Rocky hosts. Secret contents were not read or
recorded.

### Validator checkpoint — 2026-09-16

The current tracked configuration passed the reconstruction-manifest,
rollback-manifest, protected-bundle, protected-tree, capability-matrix,
inventory-drift, and monitor-plan validators. The audit found no provably
obsolete public deployment file to delete. Private runtime state and any
ambiguous legacy artifacts remain review-gated and were not modified.
