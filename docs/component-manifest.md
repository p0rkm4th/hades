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

| Component | Pinned/rebuild source | Persistent state | Required private inputs | Network dependency | Startup order | Health check | Restore check |
|---|---|---|---|---|---|---|---|
| LLDAP | Pinned identity image | Directory database and key material | JWT/key seed, admin bootstrap | Private identity network | 1 | LDAP/HTTP health and login | Isolated database restore and identity record check |
| Open WebUI | Pinned upstream image plus HADES static assets | WebUI database, vector data, matching assets | Database/auth secrets | LLDAP and Hermes | 2 | WebUI health, login, chat reload | SQLite integrity, marker conversation reload, asset match |
| Hindsight | Pinned image with embedded PostgreSQL | PostgreSQL cluster/export | Database credentials and subject-bank policy | Hermes to private memory API | 3 | PostgreSQL readiness and Hindsight health | Native export restore and subject-scoped marker recall |
| Grocy | Pinned LinuxServer image | Complete Grocy configuration/database | API key | Hermes to private Grocy API | 4 | Grocy HTTP health | SQLite integrity, stock/list/recipe canonical checks |
| Hermes 0.14 baseline | Pinned upstream package and private profile | Profile, sessions, skills, state | Provider, MCP, and service credentials | Open WebUI, Hindsight, Grocy, SearXNG, Agent Zero | 5 | Private API health and authenticated model contract | Profile parse, bounded tool call, reload/restart |
| Agent Zero | Pinned operator image | Dedicated operator volume/settings | Bounded API credential | Hermes to private operator API | 6 | Agent Zero health and authenticated card/API check | Isolated volume restore and harmless bounded delegation |
| SearXNG | Pinned search image/configuration | Configuration; cache is reconstructable | Any private provider settings | Hermes to private search API | 7 | JSON search response | Config parse and provider search check |
| HADES policy/assets/adapters | Repository at pushed `main` plus deployed overlay copy | No canonical domain state | Private deployment environment variables | Loaded by Hermes; no separate authority | With Hermes | Overlay syntax, boundary, and MCP registration checks | Source/runtime match, policy tests, and smoke contract |

## Boundary rule

Hindsight may provide remembered context but cannot override live truth from
Grocy, Finance, Proxmox, NetBox, Uptime Kuma, or Home Assistant. HADES should
not add a shadow store, universal tool registry, planner, scheduler, or event
bus.

See [`stable-v1-readiness.md`](stable-v1-readiness.md) for the current
production contract, compatibility overlay inventory, recovery dependencies,
and remaining owner/authority gates.
