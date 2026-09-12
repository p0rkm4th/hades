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
| n8n | deterministic workflows | future configuration | deferred until product-manager authorization |

## Boundary rule

Hindsight may provide remembered context but cannot override live truth from
Grocy, Finance, Proxmox, NetBox, Uptime Kuma, or Home Assistant. HADES should
not add a shadow store, universal tool registry, planner, scheduler, or event
bus.
