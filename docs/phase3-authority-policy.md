# Phase 3 authority policy input

`integrations/automation/phase3_authority_policy.py` reads an operator-managed
JSON policy file from disk on every `Phase3Runner` authority lookup. When
`HADES_EPSILON_PHASE3_AUTHORITY_POLICY_FILE` is set, the Hermes Phase 3 UI uses
the same file instead of the legacy environment grant snapshot. File edits
therefore take effect on the next operation without restarting the service.

Start from [`config/phase3-authority-policy.example.json`](../config/phase3-authority-policy.example.json).
An entry names a stable authenticated Open WebUI subject and explicitly lists
its active state, role, and resource grants:

```json
{
  "schema": 1,
  "subjects": {
    "<stable-subject-id>": {
      "active": true,
      "role": "household",
      "resources": ["grocy.household"]
    }
  }
}
```

The file must be a regular non-symlink file owned by the service user with
exact mode `0600`, valid schema version 1, and only the fixed resource names
`hades-core.health`, `grocy.household`, and `backup.evidence`. Owners receive
only the grants explicitly listed in their entry; there is no implicit union.
Unknown subjects, inactive entries, unsafe permissions, malformed policy, or
an unavailable file fail closed. The runner resolves policy before reserving
a run and reloads it immediately before the canonical read.

`active` is an explicit HADES policy bit. It is not yet synchronized from
LLDAP/Open WebUI account state: the deployed identity path does not provide a
verified directory-event or active-account lookup. The supported account
deprovision procedure must not be treated as automatically updating this file
until that synchronization exists. Keep scheduled Phase 3 execution disabled
until the policy file is configured and current-account revocation is covered
by the integrated service contract.

## Live scheduled-run authority source

The optional `Phase3LldapAuthority` source resolves each runner lookup against
LLDAP instead of trusting the static active bit. It reads
`config/phase3-directory-authority.example.json` as an operator-managed,
mode-0600 mapping from stable Open WebUI subject IDs to exact LLDAP user IDs,
and from exact LLDAP group names to an explicitly selected role and fixed
resource grants. Unmapped subjects have no authority. A missing directory
user, query error, invalid response, unsafe input, or network failure never
falls back to the static policy or a cached grant.

Configure all of the `HADES_EPSILON_PHASE3_DIRECTORY_AUTHORITY_FILE`,
`HADES_EPSILON_PHASE3_LLDAP_URL`, and
`HADES_EPSILON_PHASE3_LLDAP_READER_PASSWORD_FILE` inputs together. The reader
password and mapping file must be owned by the Epsilon service user and have
exact mode `0600`. Plain HTTP is accepted only on loopback; remote LLDAP
endpoints must use verified HTTPS. The service authenticates for every
authority lookup and verifies that its account belongs to
`lldap_strict_readonly` and not to `lldap_admin` or
`lldap_password_manager`. Thus an account deletion or group-membership change
is visible to the next runner authority check. Group-to-role and resource
mapping remains an explicit private operator input; directory membership alone
does not invent HADES grants. This resolver reads current LLDAP account
existence and groups; it does not query Open WebUI's local account-disable
flag. The tracked LLDAP digest currently identifies v0.6.3, whose [tagged
GraphQL `User` schema](https://github.com/lldap/lldap/blob/v0.6.3/schema.graphql#L974-L999)
exposes identity, profile, attributes, and groups but no active/disabled
field. The current integration therefore cannot verify an Open WebUI-only
disable, and there is no LLDAP disable field available to query on this pin.

The Server Health Watch source is separately configured with
`HADES_EPSILON_HEALTH_URL`. It must point to the operator-selected canonical
HADES health endpoint and return a recognized boolean `status` or `UP`/`DOWN`
`state`. No endpoint is assumed by default: when this input is absent, the
source returns `SOURCE_UNAVAILABLE` without probing a guessed localhost port.
Keep Server Health Watch, and any Weekly Summary scope containing health,
disabled until that endpoint has been validated.

For immediate Phase 3 revocation, remove the user's mapped HADES authorization
group in LLDAP or remove the stable subject from the protected
directory-authority mapping. The next scheduled execution performs an uncached
group lookup and denies the run. Deleting the mapped LLDAP user also denies
access, but group removal is the narrower routine action. Verify the resulting
denial on a disposable acceptance target before enabling schedules. Do not
treat disabling only the Open WebUI account as revocation for Phase 3.

The live provider applies to scheduled runner execution only. The staged Hermes
surface may continue using the static policy input for preview/creation; the
runner independently checks current LLDAP identity and grants before source
reads and result access. Do not enable schedules until the service principal,
stable-subject mapping, exact production groups, and service filesystem
permissions are configured and validated on a disposable systemd target.

The isolated Phase 3 SQLite database contains private automation ownership,
idempotency, audit, and result records. In the default single-user mode,
`Phase3Store` creates a parent directory with mode `0700` and a database with
mode `0600`. Production Hermes and Epsilon use different Unix users and must
share this one Phase 3 database, not the broader Phase 2 Hermes automation
database. Provision a dedicated group containing only those service
processes; set `HADES_EPSILON_PHASE3_STATE_GROUP` and the same
`HADES_EPSILON_PHASE3_STATE_FILE` in both services. The directory must be
`root:<group>` mode `2770`, the database `<service-user>:<group>` mode `0660`,
and both services must use `UMask=0007` and a narrow writable path. Use
`SupplementaryGroups=<group>` in each systemd unit instead of changing the
accounts' general group membership. `Phase3Store` refuses a missing group,
wrong group, symlink, unsafe mode, or private database that would need its
permissions widened. Back up and migrate existing Phase 3 rows into this new
path; do not point it at the shared Phase 2 database or broaden access to
profile state.
