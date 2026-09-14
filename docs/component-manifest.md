# Component Manifest

The first dogfood slice is deployed outside this repository's source tree;
runtime secrets and persistent volumes remain outside Git.

| Component | Authority | Planned integration | Version / license / upgrade note |
|---|---|---|---|
| Hermes | intelligence and agent execution | supported upstream deployment/API | 0.14.0; user systemd service; upgrade through upstream installer |
| Open WebUI | owner-facing conversation interface | supported Hermes-compatible interface | 0.11.5; pinned image; no fork or branding patch |
| Hindsight | durable semantic/personal memory | Hermes external memory provider over supported client API | pinned image digest `sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`; embedded pg0 volume; upgrade by digest |
| Agent Zero | bounded subordinate computer operator | isolated deployment with explicit objective/result boundary | pinned image digest; no shared unrestricted credentials; native A2A evaluated and retained MCP bridge is bounded |
| Grocy | canonical pantry, groceries, consumption, inventory, recipes | maintained integration, then supported API or tiny adapter | select upstream release; Grocy remains source of truth |
| Actual Budget / Finance MCP | canonical imported finance account and transaction truth | `integrations/actual-finance-readonly/` small stdio MCP adapter over the official client; synthetic staging only | Actual 26.9.0 server/client must be pinned together; owner authorization and no finance write authority |
| Proxmox / NetBox / Uptime Kuma | homelab and availability truth | read-only preparation documented in `docs/homelab-readonly.md`; runtime deferred | owner-approved endpoints and credentials required; no writes |
| Home Assistant | physical smart-home state/control | future selected-entity integration | deferred; least privilege required |
| n8n | deterministic workflows | future configuration | preparation contract in [`automation-boundary.md`](automation-boundary.md); deferred until product-manager authorization of one concrete workflow |

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
| Open WebUI | Private pinned 0.11.5 image/build record plus HADES static assets | WebUI database, vector data, matching assets | Database/auth secrets | LLDAP and Hermes | 2 | WebUI health, login, chat reload | SQLite integrity, marker conversation reload, asset match |
| Hindsight | Pinned image with embedded PostgreSQL | PostgreSQL cluster/export | Database credentials and subject-bank policy | Hermes to private memory API | 3 | PostgreSQL readiness and Hindsight health | Native export restore and subject-scoped marker recall |
| Grocy | Pinned image digest in `deploy/grocy.compose.yaml` | Complete Grocy configuration/database | API key | Hermes to private Grocy API | 4 | Grocy HTTP health | SQLite integrity, stock/list/recipe canonical checks |
| Actual Budget / Finance MCP | Pinned Actual 26.9.0 server/client plus tracked read-only adapter | Private synthetic or owner-authorized Actual state | Endpoint, budget identity, and credentials | Hermes to private finance API | 4 | Adapter read-only health/contract check | Synthetic ledger marker and read-only response; real restore is owner-gated |
| Hermes 0.14 baseline | Pinned upstream package and private profile | Profile, sessions, skills, state | Provider, MCP, and service credentials | Open WebUI, Hindsight, Grocy, SearXNG, Agent Zero | 5 | Private API health and authenticated model contract | Profile parse, bounded tool call, reload/restart |
| Agent Zero | Pinned image digest in `deploy/agent-zero.compose.yaml` | Dedicated operator volume/settings | Bounded API credential | Hermes to private operator API | 6 | Agent Zero health and authenticated card/API check | Isolated volume restore and harmless bounded delegation |
| SearXNG | Private pinned image record plus tracked search configuration | Configuration; cache is reconstructable | Any private provider settings | Hermes to private search API | 7 | JSON search response | Config parse and provider search check |
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

The public deployment directory intentionally tracks only the compose contracts
that are safe to publish: Agent Zero, Grocy, and LLDAP. Open WebUI, Hindsight,
Hermes, and SearXNG use the private operator deployment/service records; their
runtime secrets and volumes are not copied into Git. Staging/demo containers
are disposable and are not treated as production topology.

The audit found no provably obsolete public compose file or adapter to delete.
The remaining drift risk is documentation-to-private-runtime parity: when a
component version, image digest, endpoint, or startup dependency changes, the
reconstruction manifest and operator record must be updated together. Ambiguous
private state is deliberately retained until an owner-authorized migration.

### Observed runtime reconciliation — 2026-09-14

The live, public-safe topology was compared with the manifest without reading
environment values or persistent data:

| Observed component | Runtime evidence | Reconciliation |
|---|---|---|
| Open WebUI | Local `0.11.5-remote-prefs` theme image, LAN binding on `:3000` | Private build input and static theme assets must remain in the operator record; the manifest's upstream 0.11.5 version is the compatibility baseline |
| SearXNG | `searxng:2026.5.31-7159b8aed`, loopback `:8080` | Record the image digest with the private deployment record before rebuild; tracked settings remain the public configuration source |
| LLDAP | Pinned `hades-lldap` on loopback `:17170`; separate local-only production/staging instance on `:17171` | The second instance is staging topology, not a replacement authority; identity migration must be explicitly selected |
| Grocy / Agent Zero | Pinned compose digests and loopback bindings match tracked contracts | No drift found |

The untracked Open WebUI/SearXNG service definitions are intentional private
deployment state, not dead public compose files. This is now an explicit
rebuild input rather than an undocumented assumption.

The metadata-only permission audit also found the three staged LLDAP secret
files at mode `0600`, while tracked non-secret settings remain `0644`. The
LLDAP Compose contract uses read-only bind mounts with an SELinux `Z` relabel
rather than embedding values in the repository; this preserves narrow service
access on enforcing Fedora/Rocky hosts. Secret contents were not read or
recorded.
