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
Hermes profile token. That is the current deployed baseline. The v2 clean
install path can instead take an explicit native Operator password and
synchronize the live pinned service token into a protected Hermes
`EnvironmentFile` after Agent Zero starts; it does not copy a token from a
development host.

The bridge now also rejects task text containing credential requests,
infrastructure control, shell/SSH/Docker access, operational verbs/utilities
(including deploy, install, reboot, chmod, and network/port scans), or other
write-capable operations before making an upstream request. This is defense in
depth, not a replacement for server-side Agent Zero authorization. Harmless
bounded inspection and evidence-collection tasks remain eligible for
delegation.

The bridge uses MCP 2.0's low-level stdio server API, which is compatible with
the MCP dependency shipped by Hermes 0.21.2. The former MCP 1.x `FastMCP`
import is intentionally not used. Its registration callbacks follow the
installed low-level API, and the adapter has a public boundary regression so
an MCP runtime upgrade cannot silently remove the delegation tool.

## Optional interactive Operator access

The native Agent Zero UI is a separate, optional owner/admin surface. Its
loopback gateway is disabled by default and requires the explicit Operator
password plus the live LLDAP authority inputs described in
[`private-input-contract.md`](private-input-contract.md). When enabled, the
gateway listens on the HADES host's loopback address, normally port `7004`.
On that host, open `http://127.0.0.1:7004/` and complete both the HADES
owner/admin session check and Agent Zero's native login.

From an authorized workstation, keep the service private and forward the
loopback port over the existing SSH access to the HADES host. Replace
`user@hades-host` with the SSH account and host alias you already use:

```sh
scripts/open-agent-zero-operator.sh user@hades-host
```

Use the SSH target or profile already authorized for your HADES host. The
helper binds the local port to `127.0.0.1` only, checks that the chosen local
port is unprivileged, and keeps the tunnel open until Ctrl-C. A different
local port can be supplied as the second argument. While the tunnel is
running, open the URL printed by the helper. Do not publish port `7004` on
the LAN, Tailscale, or the public internet. Removing
owner/admin LLDAP membership denies the next HTTP request or WebSocket
handshake; an already-open WebSocket remains authorized until it reconnects.
To disable the feature, set
`HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=false` and rerun
`scripts/install-hades.sh`; the installer stops the gateway and restores the
configured direct Open WebUI bind without deleting application state.

This documented SSH-tunnel path has not yet been exercised from an external
workstation against a live enabled guest. See
[`agent-zero-operator-evaluation.md`](agent-zero-operator-evaluation.md) for
the current acceptance boundary. The ordinary Hermes delegation path remains
separate and bounded.

This integration is intentionally not registered as an Open WebUI-native tool
or exposed as a separate user-facing assistant. The production Agent Zero
instance has its native A2A server enabled on the existing loopback-only
listener; unauthenticated access is rejected. The installed FastA2A route is
the legacy `/.well-known/agent.json` path and advertises the container-local
URL, while Hermes' v0.21.2 client expects the v1 `agent-card.json` and a
different card/transport contract. The endpoint is not LAN- or Tailscale-
exposed, and the token remains private in Agent Zero settings. Hermes retains
the smaller bounded MCP bridge. Native A2A is **DEFERRED FOR V1**. Revisit
only after a mutually compatible authenticated card/transport contract passes
bounded task, failure, and household-denial acceptance without increasing
privileges. Enabling the server does not broaden Agent Zero authority.

Upstream references:

- [Agent Zero installation guide](https://github.com/agent0ai/agent-zero/blob/main/docs/setup/installation.md)
- [Agent Zero repository](https://github.com/agent0ai/agent-zero)
- [Agent Zero A2A setup](https://github.com/agent0ai/agent-zero/blob/main/docs/guides/a2a-setup.md)
