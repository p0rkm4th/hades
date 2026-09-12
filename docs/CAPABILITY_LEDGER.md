# HADES Capability Ledger

This is a sanitized project-level record of verified capability. Detailed
owner prompts, URLs, account identifiers, runtime topology, and canonical
state checks remain in the private acceptance record.

Last reviewed: 2026-09-12

| Capability | Status | Component / revision | Sanitized evidence | Limitation |
|---|---|---|---|---|
| Owner conversation | PASS + PERSISTENCE | Open WebUI 0.11.1, Hermes 0.14.0 | Authenticated mobile owner chat returned a response and retained it after reload. | Model latency and capabilities depend on the local model. |
| Durable memory | PASS + PERSISTENCE | Hindsight with Hermes memory provider | Owner UI recall returned normalized Hindsight results; canonical memory and reload were verified. | Hindsight is contextual memory, not live domain truth. |
| Web search | PASS | SearXNG with Hermes provider | SearXNG health and basic query path pass; provider is configured from the repository seed. | Detailed owner search rendering remains deployment-specific. |
| Adaptive model capability notice | PASS | Open WebUI extension and Hermes deployment overlay | Tool-capable and completion-only local models are presented with distinct capability messaging and routing behavior. | Completion-only models cannot use HADES tools. |
| HADES themes/effects | PASS + PERSISTENCE | Open WebUI extension assets | Supported themes and effects were verified in mobile DOM and after reload. | Effects remain HADES-owned styling layered onto upstream UI. |
| Restart/recovery | PASS | HADES runtime composition | Core health endpoints recovered after controlled service restarts without losing accepted state. | External integrations are not included in this result. |
| Hermes compatibility overlay | PARTIAL | `hermes/sitecustomize.py` | Deployment overlay is now represented in source for review and documented as a compatibility layer. | Smoke coverage and upstream replacement review remain in progress. |
| Agent Zero delegation | UNPROVEN | Not provisioned | No owner-path delegation evidence yet. | Local deployment is the next milestone. |
| Household / Grocy | UNPROVEN | Not provisioned | No synthetic household workflow has been run yet. | Grocy must remain the canonical household system. |
| Memory + household composition | UNPROVEN | Hindsight + Grocy | No cross-domain owner workflow has been run yet. | Must combine memory context with live Grocy state. |
| Homelab read-only integration | UNPROVEN | Proxmox / NetBox / Uptime Kuma | No runtime integration is provisioned. | Existing credentials and endpoints, if used, remain owner-gated. |
| Finance read-only integration | BLOCKED BY OWNER GATE | Approved provider not provisioned | No real account authorization is present. | Owner must authorize the selected provider; no finance writes are permitted. |
| Home Assistant | UNPROVEN | Not provisioned | No runtime integration is provisioned. | Selected-entity access and credentials require owner authorization. |

Private detailed evidence: the deployment acceptance record maintained outside
this repository. This ledger deliberately contains no owner data or secrets.
