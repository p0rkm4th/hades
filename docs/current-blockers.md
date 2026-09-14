# Current blockers and owner gates

This is a concise, public-safe handoff list. It distinguishes work that needs
an owner decision or secret from defects that can be repaired independently.

## Requires owner or operator input

| Area | Current gate | What unblocks it |
|---|---|---|
| Hermes 0.21.2 production promotion | Owner-authenticated production rehearsal was not proven during the previous controlled attempt. Candidate HADES core is green, but qualification still has five host/update-shim/browser-environment failures plus an upstream FTS5 trace-observation test defect. | Provide a verified current owner authentication/session path and approve a rollback-backed rehearsal; separately disposition the non-HADES tests and upstream FTS5 observation contract. |
| Homelab read-only | No approved Proxmox, NetBox, or Uptime Kuma endpoints, credentials, inventory scope, or network path are configured. | Approve endpoints/scope and provision least-privilege read-only credentials. |
| Home Assistant read-only | No approved URL, token, entity allowlist, or exposure path is configured. | Approve the selected read-only entities and provide the scoped token/path. |
| Real finance | Production finance is intentionally inactive. | Approve the Actual Budget environment/budget, historical imports, retention, secret storage, and later live-sync provider. |
| Deterministic automation | No concrete n8n workflow, actor mapping, confirmation rule, or rollback contract is approved. | Approve one bounded workflow and its capability boundary. |
| Encrypted off-host recovery | Encryption key custody, off-host destination, retention, and plaintext-retirement policy are not selected. | Provide an operator-managed key and destination policy. |
| First real household user | Household Alpha is ready; onboarding needs the chosen real identity and credential flow. | Owner supplies or authorizes the intended identity/invitation. |

## Independent technical work still available

- The credential-free Qwen multi-user long-context lane is complete: the
  repeatable Alpha/Beta/Gamma harness passes 24/24 bounded turns, including
  corrections, topic switches, abandoned mutations, pronouns, and recall.
  Authenticated HADES-session acceptance remains an owner-authenticated
  end-to-end gate, not an unrecorded independent defect.
- Capture one fresh synthetic web and recipe turn with model, tool,
  continuation, and total timings; optimize only a repeatable human-visible
  slowdown or unnecessary loop.
- Isolated Grocy authoring edge cases and canonical reconciliation are covered;
  pre-write connection failures return `FAILED`, while ambiguous outcomes
  remain `OUTCOME UNKNOWN` and are never blindly replayed. Reopen this item
  only for a newly demonstrated mutation defect.
- Keep candidate-only Hermes residuals documented against the stable HADES
  qualification suite; production remains on 0.14.0.

Completed independent evidence now includes the synthetic homelab and Home
Assistant read-only fixtures, mixed-domain memory/web/operator composition
contract, cross-domain conversation dogfood, source-of-truth contradiction
harness, reconstruction manifest, static security audit, and long-context
current-turn preservation regression.
The fresh owner-UI web follow-up, recipe browser sequence, real integrations,
and recovery custody remain owner/operator gates rather than hidden defects.

The coordinated revocation bridge is accepted: it deletes the Open WebUI
account before the directory identity and verifies that the prior bearer token
is rejected. Automatic directory-event synchronization remains a documented
future architecture choice, not an actionable defect in the current ordered
procedure.

## Explicitly not blockers

- Household Alpha readiness is complete.
- Production Hermes remains healthy on the known-good 0.14.0 baseline.
- Finance is not missing implementation; it is deliberately authorization-gated.
- No production Hermes, finance, homelab, or Home Assistant mutation is pending
  without the corresponding approval.
