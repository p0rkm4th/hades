# Home Assistant preparation boundary

Status: **PREPARATION COMPLETE / OWNER GATE**.

Home Assistant is not provisioned or contacted by HADES. The intended first
integration is the maintained Home Assistant MCP endpoint (`/api/mcp`) or the
read-only REST API, using a user-approved token and an explicit entity
allowlist. HADES must not discover or expose the whole Home Assistant
instance by default.

## Proposed first slice

- Read selected sensor, climate, light, presence, and device availability
  entities.
- Preserve the source entity ID, retrieval time, and unavailable/stale state.
- Return a clear partial result when an entity or the Home Assistant endpoint
  is unavailable.
- Keep service calls disabled initially; observation is the first milestone.
- Use the built-in Assist MCP API first where its scope is sufficient. Broader
  LLM APIs require administrator access in Home Assistant.

## Explicit exclusions

The default allowlist must exclude locks, garage doors, alarm/security
controls, cameras, door access, and other physical-security or high-impact
entities. Any later low-risk control must be separately selected, confirmed,
and tested with an owner-approved workflow.

## Owner authorization checklist

Before connecting anything, obtain:

```text
Home Assistant URL:
Connection path: REST / MCP
Token owner and purpose:
Selected entity IDs:
Read-only confirmation: YES
External exposure/TLS path:
Staleness expectation:
```

Home Assistant's official REST API uses `Authorization: Bearer TOKEN`; its
official MCP server is exposed at `/api/mcp` and also requires authentication.
Tokens belong only in private deployment configuration and must never enter
this repository, CI logs, or public acceptance evidence.

## Acceptance requirements

The first owner slice must verify through HADES UI and the canonical Home
Assistant state:

1. a selected entity read;
2. unavailable-device handling;
3. stale/partial-result messaging;
4. reload persistence of conversation evidence; and
5. refusal to access an excluded security-sensitive entity.

References: [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/),
[Home Assistant MCP server](https://www.home-assistant.io/integrations/mcp_server),
and [Home Assistant authentication](https://developers.home-assistant.io/docs/auth_index/).
