# Agent Zero integration boundary

Agent Zero is an optional subordinate operator for bounded tasks. It is not a
second HADES brain and is not given HADES administration, host-root, Docker
socket, Proxmox, finance, or household credentials by this deployment.

The checked-in compose recipe follows Agent Zero's supported Docker layout:
only `/a0/usr` is persistent. The default binding is loopback on port `7002`,
so exposing it through LAN or Tailscale requires an explicit owner-approved
change. Pin the image to the digest verified for a deployment rather than
silently relying on a moving tag.

The current local test instance was pulled as:

```text
agent0ai/agent-zero@sha256:680ab243d358b5fd41847f640c2eac1c59b83b154b22fc38004b8a0631b3d028
```

Model credentials and Agent Zero onboarding settings stay outside this
repository. `integrations/agent-zero-mcp/server.py` is the deliberately small
bridge for the documented external API. It exposes one bounded text task,
enforces a 2,000-character task limit, a bounded response limit, a bounded
context-ID limit, and a timeout; it returns upstream failures without claiming
success. The secret-free adapter contract and disposable synthetic API/MCP
path are exercised. The currently running production container is healthy and
private, but its derived API token does not match the Hermes profile token, so
an authenticated production delegation is intentionally not claimed until an
operator reconciles that private credential.

The bridge uses MCP 2.0's low-level stdio server API, which is compatible with
the MCP dependency shipped by Hermes 0.21.2. The former MCP 1.x `FastMCP`
import is intentionally not used.

This integration is intentionally not registered as an Open WebUI-native tool
or exposed as a separate user-facing assistant. The production Agent Zero
instance has its native A2A server enabled on the existing loopback-only
listener; unauthenticated access is rejected. A separately provisioned,
authenticated A2A probe passed, but current production credential
reconciliation remains pending. The endpoint is not LAN- or Tailscale-exposed,
and the token remains private in Agent Zero settings. Hermes retains the smaller bounded MCP bridge because its
v0.21.2 native client still does not match Agent Zero's card/transport contract.
Revisit that client interoperability separately; enabling the server no longer
requires broadening Agent Zero authority.

Upstream references:

- [Agent Zero installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/setup/installation.md)
- [Agent Zero repository](https://github.com/agent0ai/agent-zero)
- [Agent Zero A2A setup](https://github.com/agent0ai/agent-zero/blob/main/docs/guides/a2a-setup.md)
