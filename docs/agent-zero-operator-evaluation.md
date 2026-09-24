# Agent Zero interactive Operator evaluation

Status: SELECTED / STAGED.

The native Agent Zero UI is an advanced owner operator surface, distinct from
the normal bounded Hermes-to-Agent-Zero delegation path. The first useful
contract is a dedicated native tab reached through a protected private route.
Embedding is explicitly out of scope until native behavior is proven.

## Current deployment finding

Agent Zero is bound to 127.0.0.1:7002 and has no tracked reverse proxy or
supported Open WebUI global navigation-link mechanism. Open WebUI Actions are
message-level server-side extensions; they are not a safe substitute for
server-side route authorization and do not provide a general owner-only
launcher. Theme JavaScript must not become an authority-bearing navigation
layer.

The reusable fail-closed policy contract is in
integrations/operator-access/policy.py. It accepts only a trusted proxy
assertion plus an owner group, rejects household-only identities, and validates
the forwarded path. It does not itself authenticate users or forward traffic;
those remain responsibilities of the selected private proxy.

## Required smallest implementation

- a private reverse-proxy route to the native Agent Zero endpoint;
- server-side owner/group authorization independent of launcher visibility;
- preserved Agent Zero native authentication;
- WebSocket, streaming, upload, download, and long-lived-session forwarding;
- a dedicated-tab launcher added through a supported Open WebUI mechanism when
  one exists for the deployed version;
- no new Agent Zero mounts, credentials, Docker socket, host root, or public
  listener.

Until that route and its trusted identity source are selected, the correct
state is staged rather than dogfood-green. The existing bounded MCP bridge
remains the default operator path and is unaffected.

Upstream references: https://docs.openwebui.com/features/extensibility/
and https://github.com/agent0ai/agent-zero.
