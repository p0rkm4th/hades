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

## Independent technical work status

- **In progress:** Clean-machine reconstruction is now the active independent
  workstream. The public version manifest, host/filesystem contract,
  operator-input template, idempotent test-mode installer, non-mutating doctor,
  install validator, and rerunnable disposable rehearsal are present. Two
  independent pristine Fedora guests now pass the credential-free contract
  rehearsal and synthetic restore checks. A real supported systemd guest with
  generated private deployment records and canonical backup bundle is still
  required for full-stack evidence.
- **Added:** The reconstruction contract now injects an interruption after
  preparation and verifies that a rerun preserves prepared state. Invalid
  private Compose, mutable image pins, and unsafe secret permissions fail
  before target mutation; bounded upgrade and preservation-first decommission
  rules are canonicalized in `docs/upgrade-decommission.md`.
- **Added:** The credential-free backup→destroy→restore drill preserves stable
  Alpha/Beta subject IDs, memory-bank mappings, conversation marker, and Grocy
  stock. It does not substitute for private encrypted off-host recovery.

- **Complete:** The credential-free Qwen multi-user long-context lane is
  complete: the
  repeatable Alpha/Beta/Gamma harness passes 24/24 bounded turns, including
  corrections, topic switches, abandoned mutations, pronouns, and recall.
  Authenticated HADES-session acceptance remains an owner-authenticated
  end-to-end gate, not an unrecorded independent defect.
- **Complete:** A fresh synthetic web and recipe capture records model, tool,
  continuation, and total timings. Both workflows are below the repeated
  roughly-30-second optimization threshold; model/continuation is the bounded
  future target and no adapter rewrite is justified.
- **Covered:** Isolated Grocy authoring edge cases and canonical reconciliation
  are covered;
  pre-write connection failures return `FAILED`, while ambiguous outcomes
  remain `OUTCOME UNKNOWN` and are never blindly replayed. Reopen only for a
  newly demonstrated mutation defect.
- **Documented:** Candidate-only Hermes residuals are classified against the
  stable HADES qualification suite; production remains on 0.14.0 and no
  candidate-only upstream/provider failure is a HADES release blocker.
- **Added:** A public configuration-drift guard now checks the tracked compose
  set and reconstruction-manifest coverage.

Completed independent evidence now includes the synthetic homelab and Home
Assistant read-only fixtures, mixed-domain memory/web/operator composition
contract, cross-domain conversation dogfood, source-of-truth contradiction
harness, reconstruction manifest and drift guard, static security audit,
transient-error memory hygiene, Hermes qualification classification, stable-v1
readiness-map validation, and long-context current-turn preservation
regressions.
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
