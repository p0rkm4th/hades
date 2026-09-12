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
| HADES themes/effects | PASS + PERSISTENCE | Open WebUI extension assets | Authenticated Tailscale mobile DOM verification confirmed native Settings ordering, all HADES selectors, Odysseus Neon plus Rain canvas/classes, and reload persistence. | Effects remain HADES-owned styling layered onto upstream UI. |
| Restart/recovery | PASS | HADES runtime composition | Core health endpoints recovered after controlled service restarts without losing accepted state. | External integrations are not included in this result. |
| Hermes compatibility overlay | PARTIAL | `hermes/sitecustomize.py` | Deployment overlay is now represented in source for review and documented as a compatibility layer. | Smoke coverage and upstream replacement review remain in progress. |
| Agent Zero runtime | PASS | Agent Zero v2.12, pinned container image | Private loopback deployment is healthy; real Agent Zero UI produced `A0-READY` with local qwen3:8b. | Delegated context persistence and browser-DOM acceptance remain open. |
| Agent Zero delegation | PARTIAL | Agent Zero + Hermes MCP adapter | Official Agent Zero API contract and private one-tool MCP bridge are connected; a clean bounded HADES owner-API delegation returned `A0-HADES-READY`, and the earlier busy state was surfaced as an error. | Keep the operator bounded and private; browser-DOM success and persistent context acceptance remain open. |
| Household / Grocy runtime | PASS | Grocy v4.7.1, pinned LinuxServer image | Private loopback deployment is healthy with persistent synthetic database storage. | Browser-DOM acceptance remains open. |
| Household / Grocy | PARTIAL | Grocy + Hermes | HADES owner-API add, remove, correction/re-add, bounded stock-intake preview plus explicitly confirmed apply, canonical consume, recipe fulfillment available/shortage branches, recipe add-missing merge, and combined Grocy/Hermes restart persistence were verified against Grocy's API. | Broader pantry and browser-DOM workflows remain open; local-model apply wording remains sensitive. |
| Memory + household composition | PARTIAL | Hindsight + Grocy | A synthetic recipe-fixture fact was retained and recalled through HADES, combined with live Grocy fulfillment, and corrected in a later turn without changing the canonical Grocy recipe. | Browser-DOM/new-session acceptance remains open; Grocy remains authoritative for live state. |
| Homelab read-only integration | PARTIAL | Proxmox / NetBox / Uptime Kuma | Credential-independent preparation, least-privilege templates, source-of-truth boundaries, acceptance prompts, and failure rules are documented. | Runtime reads remain owner-gated; no real homelab endpoint has been contacted. |
| Finance read-only integration | PARTIAL / OWNER GATE | Plaid Transactions Sync design | Credential-independent read-only architecture, secret-safe placeholders, freshness/coverage rules, pending-versus-posted handling, and acceptance prompts are documented. | Provider, accounts, environment, retention, and webhook authorization remain owner-gated; no real data is present. |
| Home Assistant | UNPROVEN | Not provisioned | No runtime integration is provisioned. | Selected-entity access and credentials require owner authorization. |

Private detailed evidence: the deployment acceptance record maintained outside
this repository. This ledger deliberately contains no owner data or secrets.
