# Home Assistant preparation boundary

Status: **READY FOR TOKEN / OWNER GATE**.

Home Assistant is not provisioned or contacted by HADES. The credential-free
preflight is complete and fails closed when configuration is absent. A reusable
read-only REST MCP adapter now exists at
`integrations/home-assistant-readonly/server.py`; it exposes only
`home_assistant_read` and `home_assistant_selected_states`, and requires an
explicit non-sensitive entity allowlist. The intended first live integration is
the maintained Home Assistant MCP endpoint (`/api/mcp`) or this read-only REST
path, using a user-approved token. HADES must not discover or expose the whole
Home Assistant instance by default.

## Proposed first slice

Before any future integration is enabled, run
[`scripts/check-home-assistant-readonly-config.sh`](../scripts/check-home-assistant-readonly-config.sh)
with the owner-approved values in a protected environment. The preflight only
checks endpoint shape, token presence, and a conservative entity allowlist; it
never contacts Home Assistant and never prints credential or entity values. It
exits with status `2` when the owner gate is incomplete and status `1` for
invalid or security-sensitive configuration.

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
entities. The policy also rejects garage/door/alarm names exposed through
`switch`, `button`, or `input_boolean` domains. Any later low-risk control must
be separately selected, confirmed, and tested with an owner-approved workflow.

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

The shared synthetic response-contract check also covers selected-entity
metadata, unavailable-state reporting, partial results, and the read-only
invariant without contacting Home Assistant.

[`scripts/test-home-assistant-fixture.sh`](../scripts/test-home-assistant-fixture.sh)
adds a disposable loopback REST fixture for the first integration slice. It
covers ordinary lights, temperature, and purifier reads; an unavailable and
stale sensor; excluded lock and camera entities; and rejection of writes. The
fixture proves that excluded entities are rejected before any request reaches
the backend, and is exercised in public CI without a Home Assistant token or
real endpoint.

The adapter policy contract is exercised by
[`scripts/test-home-assistant-readonly-adapter.sh`](../scripts/test-home-assistant-readonly-adapter.sh).
It is intentionally transport-agnostic in public evidence: live URL, token,
entity selection, and endpoint exposure remain owner gates.

References: [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/),
[Home Assistant MCP server](https://www.home-assistant.io/integrations/mcp_server),
and [Home Assistant authentication](https://developers.home-assistant.io/docs/auth_index/).
