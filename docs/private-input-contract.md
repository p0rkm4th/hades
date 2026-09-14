# Private input and secret contract

This is the public description of the values required to reconstruct a
production-capable deployment. Values are supplied through the operator input
file or a referenced `0600` file; no live value belongs in Git, CI, doctor
output, or reports. The operator owns rotation and backup custody.

| Input | Consumer | Required | Format / supply | Read permission | Regenerate / rotation | Backup |
|---|---|---:|---|---|---|---|
| `HADES_OWNER_BOOTSTRAP_ID` | LLDAP/Open WebUI policy | yes | stable synthetic or owner-selected subject ID in input file | installer/policy owner | do not regenerate during restore; rotate only with mapping plan | mapping metadata, not plaintext credential |
| LLDAP JWT secret, key seed, admin password | LLDAP | yes | three file-backed random values under `HADES_IDENTITY_SECRETS_DIR`, mode 0600, UID 1000 | LLDAP only | generated once; rotation requires identity restore/revocation procedure | encrypted canonical identity backup plus key policy |
| `HADES_HERMES_API_KEY` | Hermes/Open WebUI private record | yes | random file-backed or private environment reference | Hermes/WebUI service account | rotate with client configuration update | encrypted private secret backup |
| `HADES_HERMES_MODEL_ENDPOINT` | Hermes | yes | `http(s)` URL; local inference is optional and may be remote | Hermes | endpoint change is an operator migration | no, unless configuration backup requires the reference |
| Hindsight database/auth values | Hindsight | yes | private record/file-backed values | Hindsight and Hermes only | rotate with native database procedure | native PostgreSQL export plus secret policy |
| Grocy API key | Grocy adapter | yes | file-backed random value | adapter only | rotate after adapter update | encrypted secret backup if not reproducible |
| Agent Zero bounded credential | Agent Zero bridge | optional owner capability | file-backed scoped credential | Agent Zero bridge only | revoke/replace independently | encrypted private backup when state depends on it |
| SearXNG provider settings | SearXNG | optional | private settings file; search cache is not canonical | SearXNG only | regenerate from provider configuration | configuration only, not cache |
| `HADES_OPEN_WEBUI_COMPOSE_FILE`, `HADES_HINDSIGHT_COMPOSE_FILE`, `HADES_SEARXNG_COMPOSE_FILE`, `HADES_HERMES_SERVICE_FILE` | installer | yes | paths to four private runtime records | installer/root | source-controlled templates or explicit operator update | record itself, excluding embedded secrets |
| Actual endpoint/budget/credentials | finance adapter | owner-gated | explicit authorized environment and scoped references | finance adapter only | owner-controlled | only under authorized finance policy |
| homelab endpoint/credentials | Proxmox/NetBox/Kuma adapters | owner-gated | read-only URLs and credentials | homelab adapters only | owner-controlled | only under authorized policy |
| Home Assistant endpoint/token/entity allowlist | HA adapter | owner-gated | URL, scoped token, explicit entity IDs | HA adapter only | owner-controlled | only under authorized policy |

The installer never prints secret contents, copies them into the repository,
or regenerates stable identity material on rerun. A missing or placeholder
required value fails before target mutation. Live finance, homelab, Home
Assistant, household onboarding, Hermes promotion, and off-host recovery
custody remain intentionally outside autonomous reconstruction.
