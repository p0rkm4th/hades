# Backup and restore contract

This public procedure is deployment-neutral. Actual backup destinations,
private paths, encryption keys, host identities, and retention settings are
owned by the private infrastructure repository and the operator.

## Component coverage

| Component | Authority / reconstructability | Canonical backup / restore |
|---|---|---|
| Phase 3 automation | Workflow definition is reconstructable; execution state is persistent | Export workflow definitions and verify through the configured runner |
| LLDAP | Identity authority; must preserve stable subject mapping | Use the documented database export and protected identity-secret backup |
| Open WebUI | User, chat, and settings state | Database backup with matching deployment configuration |
| Hindsight | Memory authority and user-bank mappings | Database export plus stable subject mapping |
| Grocy | Canonical shared household inventory | Database backup plus configured API/input contract |
| Actual Budget | Financial authority; owner-gated | Use native export/backup and owner-controlled encryption custody |
| Hermes | Reconstructable code/config plus provider-specific state | Back up permitted state and regenerate protected provider configuration |
| Agent Zero | Optional owner-gated state | Back up only when enabled and include encrypted-state custody policy |
| SearXNG | Reconstructable search service; minimal persistent state | Recreate from pinned config; retain only explicitly required settings |
| HADES private configuration | Explicit private inputs; never public source | Protected encrypted export with owner-controlled key custody |

### Recovery objectives

RPO/RTO values are operator decisions and must be recorded in private
deployment configuration. Public examples do not set a real deployment's
recovery objectives.

| Component | RPO assumption | RTO assumption |
|---|---|---|
| Phase 3 automation | Operator-defined | Operator-defined |
| LLDAP | Operator-defined | Operator-defined |
| Open WebUI | Operator-defined | Operator-defined |
| Hindsight | Operator-defined | Operator-defined |
| Grocy | Operator-defined | Operator-defined |
| Actual Budget | Owner-defined | Owner-defined |
| Hermes | Reconstructable from pinned source | Operator-defined |
| Agent Zero | Owner-defined | Owner-defined |
| SearXNG | Reconstructable from pinned source | Operator-defined |
| HADES private configuration | Owner-controlled encrypted copy | Owner-defined |

## Restore sequence

1. Provision a clean supported host from the public reconstruction contract.
2. Generate or provide explicit private inputs through protected files.
3. Restore identity and authority-bearing state first.
4. Restore conversation, memory, household, and optional state using each
   component's canonical mechanism.
5. Validate identities, permissions, ownership, health, and application reads.
6. Reboot and repeat functional checks before accepting recovery.

A successful backup command is not proof of a successful restore. A repository
backup check is not proof that all application, host, or VM state is covered.
Local custody is not independent off-site disaster recovery.

## Private mount inventory

Deployment-specific paths, ownership, mount options, encryption state, and
retention locations are kept in private `hades-infra` records.

## Live deployment mount inventory

The public repository intentionally contains no live mount paths or host
assignments. Operators should maintain the following inventory in their
private deployment records and verify it before backup or restore:

| State class | Private record must include |
|---|---|
| Database state | Canonical service, quiesce/online-snapshot method, owner, and restore check |
| Identity material | Database, signing/encryption material, permissions, and stable subject mapping |
| Configuration | Reconstructable files versus private inputs, with source and mode |
| Media/assets | Persistent assets required to render restored conversations or workflows |
| Backup artifact | Timestamp, digest, encryption/custody, retention, and restore target |

These records are deployment-specific and must not be copied into public
fixtures or documentation.
