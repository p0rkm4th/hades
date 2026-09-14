# Homelab read-only integration plan

This is preparation only. No homelab endpoint, credential, scan, or runtime
integration is present in the HADES test deployment.

## Authority boundaries

| Domain | Canonical source | Planned HADES access | Write authority |
|---|---|---|---|
| Virtualization | Proxmox VE | API reads for nodes, guests, status, and resources | None |
| Inventory/topology | NetBox | REST `GET` reads for approved objects | None |
| Availability | Uptime Kuma | Published status-page data or metrics, where intentionally exposed | None |
| Host operations | Dedicated restricted SSH account, only if later approved | Explicitly scoped read commands | None |

Hindsight may supply remembered labels or locations, but live status always
comes from the relevant canonical system. HADES must report stale, unavailable,
or partial data rather than infer health.

## Credential-independent preparation

Before any future integration is enabled, run
[`scripts/check-homelab-readonly-config.sh`](../scripts/check-homelab-readonly-config.sh)
with the owner-approved values in a protected environment. The preflight only
checks that all required values have the expected shape; it never contacts a
homelab endpoint and never prints credential values. It exits with status `2`
when the owner gate is still incomplete and fails with status `1` for invalid
configuration.

### Proxmox VE

Create a dedicated service identity and API token with privilege separation and
the built-in `PVEAuditor` role at the narrowest required path. Start with read
requests for `/cluster/resources`, node status, and guest configuration/status.
Do not grant VM, node, storage, task, or user-management write privileges.

Required private placeholders:

```dotenv
HADES_PROXMOX_URL=https://proxmox.example.invalid:8006/api2/json
HADES_PROXMOX_TOKEN_ID=svc-hades-ro@pve!readonly
HADES_PROXMOX_TOKEN_SECRET=<private>
```

### NetBox

Use a current v2 API token with write access disabled and an expiry. Scope the
owning user or group to the approved read objects; object-based permissions
can further constrain visibility. Begin with sites, devices, interfaces, and
IP prefixes only if those are the owner-approved inventory domains.

```dotenv
HADES_NETBOX_URL=https://netbox.example.invalid
HADES_NETBOX_TOKEN=<private-v2-token>
```

### Uptime Kuma

Prefer a deliberately published status page or metrics endpoint for read-only
availability summaries. Kuma's internal Socket.IO API is not a stable
third-party integration surface, so it must not be adopted as a hidden
administrative dependency. Never use a push token or authenticated write path
for HADES reads.

```dotenv
HADES_UPTIME_KUMA_URL=https://status.example.invalid
HADES_UPTIME_KUMA_STATUS_SLUG=<owner-approved-slug>
```

## Owner acceptance prompts

Once credentials are explicitly supplied, verify through the HADES owner path:

- “What’s running in the lab?”
- “What’s down?”
- “Where does `<owner-approved host or service>` live?”
- “What’s wrong with the lab?”
- “Show me the source and freshness of that answer.”

Each result must include source, retrieval time/freshness, and a clear failure
state when a source is unavailable. A request such as “restart that server”
must remain an authorization-boundary test and must not perform a write.

## Remaining owner gate

The exact endpoints, approved inventory scope, service identities, tokens, and
allowed network path require owner authorization. Until then, HADES should not
probe or connect to real homelab services.

References: [Proxmox API-token monitoring example](https://pve.proxmox.com/pve-docs/pve-admin-guide.pdf),
[NetBox REST API authentication and read-only tokens](https://netbox.readthedocs.io/en/stable/integrations/rest-api/),
[Uptime Kuma API documentation and stability warning](https://github.com/louislam/uptime-kuma/wiki/API-Documentation/692198f84f3675a53a8ece7eb91a6a84566ee98e).
