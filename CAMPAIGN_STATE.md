# HADES Campaign State

This public-safe checkpoint records project direction, not deployment state.
Private runtime details, credentials, accounts, hostnames, addresses, chat
history, and owner data belong in the deployment environment and are never
recorded here.

## CURRENT OBJECTIVE

Build an owner-usable HADES composition from mature upstream systems while
preserving source-of-truth boundaries and least privilege.

## COMPLETED MILESTONES

- Established an independent HADES repository and composition doctrine.
- Evaluated Hermes, Open WebUI, Hindsight, Grocy, Agent Zero, and read-only
  homelab/finance integration surfaces.
- Added Open WebUI theme/effect extension assets without creating a frontend
  fork or a HADES-native agent core.
- Documented adaptive model capability behavior: tool-capable models may use
  HADES integrations; completion-only models must be clearly identified and
  must not receive tool payloads.

## OWNER-VERIFIED WORKFLOWS

Private deployment acceptance is maintained outside this public repository.
The public acceptance file contains only workflow definitions and evidence
requirements.

## CURRENT DEPLOYED COMPONENTS / VERSIONS

Deployment-specific versions, image digests, endpoints, and model choices are
intentionally maintained in private operations state.

## LOCAL COMPONENTS PROVISIONED BUT NOT OWNER-ACCEPTED

- Agent Zero is deployed privately with a dedicated volume and pinned image;
  its standalone UI/model smoke path passes. A one-tool private MCP adapter is
  now connected, correctly surfaces upstream failure, and has returned a clean
  bounded success through the HADES owner API. Browser-DOM owner acceptance
  and persistent delegated context remain open.
- Grocy is deployed privately with a dedicated persistent volume and pinned
  image; its HTTP path passes. The HADES API owner path now successfully calls
  the canonical stock and shopping-list tools against synthetic data. Add,
  remove, and correction/re-add turns have been verified against Grocy's
  canonical shopping-list API; an earlier mutation survived a Grocy restart
  and was recovered by a fresh HADES query. Browser-DOM and broader household
  acceptance remain open. Repeated-add duplication was found, fixed in the
  active MCP deployment, and regression-tested as quantity folding.

## REAL OWNER GATES

- Real Finance/Plaid account authorization is owner-gated.
- Existing Proxmox, NetBox, Uptime Kuma, or Home Assistant credentials are
  owner-gated if those systems are to be connected.
- Destructive infrastructure authority and new privileged host access remain
  prohibited without explicit authorization.

## PENDING OWNER GATES

- Authorize and provision each external integration independently.
- Capture owner-UI plus canonical-system verification in private acceptance
  records before enabling writes.

## ARCHITECTURAL DISCOVERIES

- Existing mature systems remain preferred over new HADES subsystems.
- Hindsight supplies context, not canonical household, finance, or homelab
  state.
- Agent Zero is a bounded subordinate operator, not a second HADES brain.
- Ambiguous data-bearing artifacts must be preserved until their ownership is
  known.

## OPEN DEFECTS

- Grocy owner turns require intent-scoped tool narrowing for the local Qwen
  model; the narrow shopping workflow passes, while broader household
  workflows remain unverified.

## HERMES OVERLAY STATUS

- The deployment compatibility overlay is source-represented at
  `hermes/sitecustomize.py` and remains intentionally narrow.
- It handles local model routing, Hindsight retain/recall normalization,
  explicit-memory tool narrowing, streaming handoff, and related weak-model
  compatibility behavior.
- It is not a HADES runtime, planner, router framework, or new core.

## CAPABILITY LEDGER

See `docs/CAPABILITY_LEDGER.md` for the sanitized verified capability state.

## NEXT ACTION

Wire the bounded Agent Zero deployment through a supported integration path and
prove one success plus one safe failure through the HADES owner UI; then run
synthetic Grocy workflows through HADES and verify canonical state after reload.
