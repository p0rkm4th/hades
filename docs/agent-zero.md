# Agent Zero integration boundary

Agent Zero is an optional subordinate operator for bounded tasks. It is not a
second HADES brain and is not given HADES administration, host-root, Docker
socket, Proxmox, finance, or household credentials by this deployment.

The checked-in compose recipe follows Agent Zero's supported Docker layout:
only `/a0/usr` is persistent. The default binding is loopback on port `7002`,
so exposing it through LAN or Tailscale requires an explicit owner-approved
change. Pin the image to the digest verified for a deployment rather than
silently relying on a moving tag. The container contract also uses a read-only
root filesystem, drops all Linux capabilities, and enables
`no-new-privileges`; only the dedicated operator volume is persistent and
writable. Temporary files use an ephemeral `/tmp` mount.

The current local test instance was pulled as:

```text
agent0ai/agent-zero@sha256:680ab243d358b5fd41847f640c2eac1c59b83b154b22fc38004b8a0631b3d028
```

Model credentials and Agent Zero onboarding settings stay outside this
repository. `integrations/agent-zero-mcp/server.py` is the deliberately small
bridge for the documented external API. It exposes one bounded text task,
enforces a 2,000-character task limit, a bounded response limit, a bounded
context-ID limit, and a timeout; it returns upstream failures without claiming
success. A failure before the delegation request is sent is `FAILED`; an HTTP
failure after the request is attempted is `OUTCOME UNKNOWN`, because Agent Zero
may have accepted the task. The secret-free adapter contract, disposable synthetic API/MCP path,
and authenticated production marker task are exercised. The production
container is healthy and private; its derived API token matches the protected
Hermes profile token.

The bridge uses MCP 2.0's low-level stdio server API, which is compatible with
the MCP dependency shipped by Hermes 0.21.2. The former MCP 1.x `FastMCP`
import is intentionally not used. Its registration callbacks follow the
installed low-level API, and the adapter has a public boundary regression so
an MCP runtime upgrade cannot silently remove the delegation tool.

This integration is intentionally not registered as an Open WebUI-native tool
or exposed as a separate user-facing assistant. The production Agent Zero
instance has its native A2A server enabled on the existing loopback-only
listener; unauthenticated access is rejected. The installed FastA2A route is
the legacy `/.well-known/agent.json` path and advertises the container-local
URL, while Hermes' v0.21.2 client expects the v1 `agent-card.json` and a
different card/transport contract. The endpoint is not LAN- or Tailscale-
exposed, and the token remains private in Agent Zero settings. Hermes retains
the smaller bounded MCP bridge. Revisit native interoperability separately;
enabling the server does not broaden Agent Zero authority.

Upstream references:

- [Agent Zero installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/setup/installation.md)
- [Agent Zero repository](https://github.com/agent0ai/agent-zero)
- [Agent Zero A2A setup](https://github.com/agent0ai/agent-zero/blob/main/docs/guides/a2a-setup.md)
