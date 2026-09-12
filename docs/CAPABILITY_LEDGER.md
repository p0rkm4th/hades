# HADES Capability Ledger

This is a sanitized project-level record of verified capability. Detailed
owner prompts, URLs, account identifiers, runtime topology, and canonical
state checks remain in the private acceptance record.

Last reviewed: 2026-09-12

| Capability | Status | Component / revision | Sanitized evidence | Limitation |
|---|---|---|---|---|
| Owner conversation | PASS + PERSISTENCE | Open WebUI 0.11.1, Hermes 0.14.0 | Authenticated mobile owner chat returned a response and retained it after reload. | Model latency and capabilities depend on the local model. |
| Durable memory | PASS + PERSISTENCE | Hindsight with Hermes memory provider | Owner UI retain/recall and correction returned the current canonical Hindsight fact in a fresh mobile conversation; reload/restart evidence was preserved. | Hindsight is contextual memory, not live domain truth. |
| Web search | PASS | SearXNG with Hermes provider | SearXNG health and basic query path pass; provider is configured from the repository seed. | Detailed owner search rendering remains deployment-specific. |
| Adaptive model capability notice | PASS | Open WebUI extension and Hermes deployment overlay | Tool-capable and completion-only local models are presented with distinct capability messaging and routing behavior. | Completion-only models cannot use HADES tools. |
| HADES themes/effects | PASS + PERSISTENCE | Open WebUI extension assets | Authenticated Tailscale mobile DOM verification confirmed native Settings ordering, all HADES selectors, Odysseus Neon plus Rain canvas/classes, and reload persistence. | Effects remain HADES-owned styling layered onto upstream UI. |
| Restart/recovery | PASS | HADES runtime composition | Core health endpoints recovered after controlled service restarts without losing accepted state. | External integrations are not included in this result. |
| Hermes compatibility overlay | PARTIAL | `hermes/sitecustomize.py` | Deployment overlay is now represented in source for review and documented as a compatibility layer. | Smoke coverage and upstream replacement review remain in progress. |
| Agent Zero runtime | PASS | Agent Zero v2.12, pinned container image | Private loopback deployment is healthy; real Agent Zero UI produced `A0-READY` with local qwen3:8b. | Delegated context persistence and broader operator tasks remain future work. |
| Agent Zero delegation | PASS | Agent Zero + Hermes MCP adapter | Official Agent Zero API contract and private one-tool MCP bridge are connected; bounded owner-path success, safe busy-state failure, and mobile DOM rendering were verified. | Persistent delegated context and broader operator tasks remain future work; keep the operator bounded and private. |
| Household / Grocy runtime | PASS | Grocy v4.7.1, pinned LinuxServer image | Private loopback deployment is healthy with persistent synthetic database storage. | Broader pantry edge cases remain future hardening. |
| Household / Grocy | PASS | Grocy + Hermes | HADES owner-API add, remove, correction/re-add, quantity handling, intake confirmation, consume, recipe fulfillment available/shortage branches, recipe add-missing merge, browser workflows, canonical verification, and restart persistence were verified. | Additional pantry edge cases and local-model wording remain future hardening; Grocy remains authoritative. |
| Memory + household composition | PASS | Hindsight + Grocy | A remembered recipe fact was retained, corrected, recalled in a fresh mobile DOM conversation, and combined with live Grocy fulfillment without changing canonical Grocy state; reload evidence was preserved. | Broader domain combinations remain future work; Grocy remains authoritative for live state. |
| Homelab read-only integration | PARTIAL | Proxmox / NetBox / Uptime Kuma | Credential-independent preparation, least-privilege templates, source-of-truth boundaries, acceptance prompts, and failure rules are documented. | Runtime reads remain owner-gated; no real homelab endpoint has been contacted. |
| Finance read-only integration | PARTIAL / OWNER GATE | Plaid Transactions Sync design | Credential-independent read-only architecture, secret-safe placeholders, freshness/coverage rules, pending-versus-posted handling, and acceptance prompts are documented. | Provider, accounts, environment, retention, and webhook authorization remain owner-gated; no real data is present. |
| Home Assistant | PREPARATION COMPLETE / OWNER GATE | Official Home Assistant REST/MCP paths | Credential-free read-only design, selected-entity allowlist, security-sensitive exclusions, staleness rules, and owner acceptance contract are documented. | No runtime integration is provisioned; URL, token, selected entities, and exposure path require owner authorization. |

Private detailed evidence: the deployment acceptance record maintained outside
this repository. This ledger deliberately contains no owner data or secrets.
