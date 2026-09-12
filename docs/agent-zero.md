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
repository. Hermes integration is not considered accepted until a harmless
delegated task is exercised through the HADES owner UI and its result is
verified independently.

Upstream references:

- [Agent Zero installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/setup/installation.md)
- [Agent Zero repository](https://github.com/agent0ai/agent-zero)
