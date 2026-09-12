# Agent Zero delegation adapter

This is a deliberately small stdio MCP adapter for the documented Agent Zero
api_message endpoint. It exposes one bounded delegation tool and keeps Agent
Zero subordinate to Hermes/HADES.

Required environment:

AGENT_ZERO_URL=http://127.0.0.1:7002
AGENT_ZERO_API_KEY=<private Agent Zero runtime token>

The adapter does not expose host paths, Docker, Proxmox, finance, credentials,
or HADES administration. Keep the service loopback/private and use the
preview/authorization boundaries of the delegated task.
