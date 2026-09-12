# Initial Upstream Evaluation

This public-safe selection record summarizes the upstream integration direction.
Deployment versions, private endpoints, credentials, accounts, model choices,
and acceptance results belong in private operations documentation.

## Hermes → Open WebUI

Hermes documents a supported API gateway with `API_SERVER_ENABLED`,
`API_SERVER_PORT`, and `API_SERVER_KEY` profile settings. Its documented
connection uses an OpenAI-compatible `/v1` URL, which keeps Open WebUI as the
interface and Hermes as the intelligence/execution owner.

Source: <https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/open-webui.md>

## Open WebUI

Open WebUI documents Docker deployment and standard OpenAI-compatible provider
connections. The owner interface should connect to Hermes through that protocol;
HADES should not create or fork another chat frontend.

Sources:

- <https://docs.openwebui.com/deployment/>
- <https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/>

## Hindsight

The Hindsight upstream project documents `hindsight-mcp` as an MCP server with
predefined tools for MCP-compatible agents. This is the preferred integration
direction to investigate after Hermes and Open WebUI are available. Hindsight
will provide durable context only; it must not become a shadow source of
current household, finance, or homelab truth.

Source: <https://github.com/hindsight-ai/hindsight-ai/blob/main/README.md>

## Grocy

Grocy is selected as the authoritative household system for pantry, groceries,
consumption, inventory, and recipes. Integration selection remains pending a
private HADES repository and an inspection of maintained MCP/capability/plugin
options before falling back to Grocy's supported API.

Source: <https://github.com/grocy/grocy>

### MCP candidate

The selected maintained Grocy MCP package is deployed privately against an
isolated synthetic Grocy instance with a narrowly scoped API key. It exposes
explicit read/write tools for products, stock, shopping lists, consumption,
inventory, and recipes; HADES allowlists only the required owner workflows.
Grocy's own OpenAPI description confirms API-key authentication through the
`GROCY-API-KEY` header. Deployment-local compatibility overrides are documented
in `docs/grocy.md` and are not owner-data or architecture dependencies.

## Agent Zero

Agent Zero is now deployed as a separate loopback-only container with a
dedicated persistent volume and no host-home mount, Docker socket, or shared
unrestricted credentials. Hermes delegates through a one-tool bounded MCP
adapter and relays evidence back to the owner; safe busy/upstream failure
handling has also been exercised. A2A is not used for the Hermes bridge.

Source: <https://github.com/agent0ai/agent-zero>

## Decision

Proceed with the upstream protocol path in this order:

1. Hermes gateway and local inference.
2. Open WebUI connection to Hermes.
3. Hindsight MCP integration.
4. Real owner-path vertical-slice acceptance.
5. Agent Zero and Grocy only after the slice is proven.

No custom HADES agent core, planner, memory database, chat frontend, or
universal adapter is justified by this evaluation.

## Deployment boundary

Keep deployment-specific facts, private network topology, local filesystem
paths, credentials, account identities, model inventory, and owner acceptance
evidence outside this repository. Use the example environment and configuration
files as templates, and verify the selected upstream versions in the target
deployment before rollout.
