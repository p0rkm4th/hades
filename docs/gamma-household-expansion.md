# Gamma household / self-service checkpoint

Gamma's synthetic household acceptance is complete for the current bounded
scope. Beta remains frozen at `daily-driver-reliability-beta`; the Beta pack is
regression coverage, not an active campaign.

## Green lanes

- Shared Grocy shopping-list and household attribution contracts remain green;
  Grocy is canonical and private memory is not used as inventory history.
- Synthetic selective finance sharing is private-by-default, operation-time
  revocable, Actual-shaped, and contains no shadow ledger or owner finance.
- Self-service uses only approved templates, bounded resources, policy-owned
  placement, explicit confirmation, an owner/grant registry, and a constrained
  Proxmox broker. The authenticated DOM proved create, status, share, revoke,
  household visibility, restart, and delete. Household A could see and manage
  one shared workload; Household B could not; revocation removed access.
- Synthetic cross-domain dogfood and the privilege-collapse matrix pass. Each
  domain retains independent authorization and partial failure semantics.

## Boundaries

- Self-service production rollout remains gated to synthetic identities and
  approved templates. Public exposure, arbitrary templates, raw Proxmox
  administration, and critical-host actions remain unavailable.
- Finance sharing is synthetic-only. Real accounts, providers, and owner data
  remain separately authorized.
- Local voice is prepared but deferred pending owner device/actor wiring,
  packaging/licensing acceptance, and owner-visible latency testing.
- Home Assistant is read-only policy-green but owner-gated pending the live URL,
  token, selected entity allowlist, and exposure path.

## Regression evidence

The affected Beta subsets and Gamma contracts pass:

```text
scripts/test-cross-domain-dogfood.sh
scripts/test-finance-sharing-policy.sh
scripts/test-self-service-contract.sh
scripts/test-self-service-registry.sh
scripts/test-homelab-control-executor-contract.sh
scripts/test-local-voice-dogfood.sh
scripts/test-home-assistant-readonly-adapter.sh
scripts/test-home-assistant-fixture.sh
```

No persistent self-service workload remains after the disposable DOM tests.
