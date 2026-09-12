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

The current leading candidate is [`rusty4444/grocy-mcp`](https://github.com/rusty4444/grocy-mcp),
an MIT-licensed MCP server with explicit read and write tools for products,
stock, shopping lists, consumption, inventory, and chores. Its repository is
active and documents a read-only live test against Grocy 4.6.0. It remains
uninstalled until a Grocy endpoint and narrowly scoped API key are authorized;
the public demo must not be used for writes. Grocy's own OpenAPI description
confirms API-key authentication through the `GROCY-API-KEY` header.

## Agent Zero

Agent Zero remains deferred until the Hermes/Open WebUI owner path is proven.
The official project documents a Dockerized Linux desktop, MCP/A2A support, and
an isolated persistent volume. The smallest compliant HADES deployment would
be a separate loopback-only Agent Zero container with a dedicated project and
no host-home mount, Docker socket, or shared unrestricted credentials. Hermes
would delegate one bounded objective through a supported integration and relay
evidence back to the owner. No Agent Zero process or credentials have been
created.

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
