# HADES automation view/control contract

The HADES-owned abstraction in `integrations/automation/contracts.py` is the
boundary for future n8n-backed automation UX. It is deliberately a projection
and preview layer, not a scheduler, queue, workflow database, or replacement
for n8n.

## Current contract

- `hades-automation/v1` is the public schema.
- n8n remains canonical for workflow and execution state.
- HADES ignores n8n workflows whose template is not in the explicit catalog;
  unrelated n8n projects cannot break or enter the HADES inventory.
- HADES exposes template, purpose, trigger, status, latest result, and
  operation-time allowed actions plus explicit approval state; technical n8n
  IDs are not in the public projection.
- A subject can see a workflow only through current owner/group sharing.
  Sharing never grants finance, private memory, credentials, Agent Zero,
  Proxmox, or other authority.
- The first catalog is read-only: server health, backup verification, weekly
  household summary, and low-inventory summary.
- Preview requires an explicit confirmation and validates the template,
  interval, resource allowlist, read-only property, and subject groups.
- Run, pause, resume, and delete are confirmation-gated control operations;
  each rechecks current inventory and sharing before calling an approved
  runner adapter. A revoked or stale subject cannot use a cached view.
- An unapproved workflow remains inspect-only, even for its owner; discovery
  never implies product approval.
- Revocation is checked against the current subject when inventory or a future
  control operation is requested; cached semantic recommendations are not
  authority.

The in-memory gateway is test-only. The private n8n runner is external to this
module and currently holds only an inactive read-only canary; no production
schedule or workflow execution is enabled by this module.

`N8NHttpGateway` is the read-only integration boundary for a future approved
runner. It uses bounded authenticated metadata reads, maps only explicit HADES
tags, and strips workflow nodes, credentials, and execution payloads before
they reach HADES. Control calls remain unavailable until an approved runner
adapter is selected.

The deployment must not equate HADES household sharing with native n8n editor
sharing. Native n8n sharing can grant editors use of credentials embedded in a
workflow. HADES must use a dedicated least-privilege runner identity and its
own deterministic sharing policy; n8n UI/editor sharing is not an authority
source for HADES users.

## Product gate

The first candidate remains `weekly-household-summary`, using only authorized
Grocy household and shared-service reads. Manny/Orc approval is still required
to select a runner, notification recipient, schedule, retention, and owner
actor. Until that decision is recorded, the contract stays preparation-only.
