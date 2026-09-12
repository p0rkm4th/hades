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
without claiming success. The local API/MCP path has been exercised; full
browser-DOM owner acceptance and failure regression remain open.

This integration is intentionally not registered as an Open WebUI-native tool
or exposed as a separate A2A assistant. Open WebUI remains the owner-facing
chat surface; Hermes owns the private MCP boundary and decides when a bounded
Agent Zero delegation is appropriate.

Upstream references:

- [Agent Zero installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/setup/installation.md)
- [Agent Zero repository](https://github.com/agent0ai/agent-zero)
