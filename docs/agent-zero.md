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
enforces a 2,000-character limit and timeout, and returns upstream failures
without claiming success. The local API/MCP path has been exercised. A fresh
synthetic mobile HADES session also rendered a bounded Agent Zero result in
the assistant DOM after the private tool completed. This closes the founding
bounded-delegation milestone; persistent delegated context and wider operator
tasks remain future work.

The bridge uses MCP 2.0's low-level stdio server API, which is compatible with
the MCP dependency shipped by Hermes 0.21.2. The former MCP 1.x `FastMCP`
import is intentionally not used.

This integration is intentionally not registered as an Open WebUI-native tool
or exposed as a separate A2A assistant. In an isolated disposable Agent Zero
instance, the native A2A server enabled successfully and returned a bounded
JSON-RPC response. However, its current tokenized endpoint does not expose the
agent-card path or wire shape expected by Hermes v0.21.2's native A2A client;
the interoperability probe failed while the direct Agent Zero A2A request
passed. Hermes therefore retains the smaller bounded MCP bridge for the
founding milestone. Re-evaluate native A2A when both sides provide a matching
card/transport contract and an authenticated lifecycle can be exposed without
broadening Agent Zero authority.

Upstream references:

- [Agent Zero installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/setup/installation.md)
- [Agent Zero repository](https://github.com/agent0ai/agent-zero)
- [Agent Zero A2A setup](https://github.com/agent0ai/agent-zero/blob/main/docs/guides/a2a-setup.md)
