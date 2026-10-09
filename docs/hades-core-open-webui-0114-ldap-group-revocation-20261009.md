# Open WebUI 0.11.4 LDAP group revocation — 2026-10-09

## Finding

The exact upstream 0.11.4 candidate image
`sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`
passed initial LDAP login and group synchronization. A disposable test then
removed a user's only LLDAP group and performed a fresh LDAP login. The user
kept the stale `hades-household` membership in the Open WebUI database.

The cause is in upstream `backend/open_webui/routers/auths.py`: group sync is
guarded by `if ENABLE_LDAP_GROUP_MANAGEMENT and user_groups`, although the
native `Groups.sync_groups_by_group_names` function removes existing
memberships when called with an empty list. As a result, revoking the final
directory group bypasses the native reconciliation function.

## Smallest staged repair

`webui/ldap_group_sync_compat.py` removes only the non-empty-list guard. It
fails the image build if upstream changes the expected source, and is
idempotent if already applied. The existing upstream membership reconciler
continues to add and remove memberships; the adapter lets it process an empty
authoritative group list. Delete the adapter when upstream invokes that
reconciler for empty LDAP group results.

## Verification

The patched HADES image was built from the immutable official Open WebUI
0.11.4 base
`ghcr.io/open-webui/open-webui@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f`.
Its local immutable image ID is
`sha256:86b448b4ae005c7971f96930f8a52677ed788d8f726dfe679367cd2046e4650e`.
The build used the tracked HADES Dockerfile and adapter. This local image has
no external build attestation and remains a staging candidate.

`scripts/test-open-webui-ldap-group-sync-candidate.py` passed against that
exact image and the pinned LLDAP 0.6.3 image
`sha256:90b849059c42ed8f92b95624ae71e38ca137a994736c68fb25dd167f2bbc9808`:

- Synthetic Alpha and Beta authenticate as ordinary users and retain stable,
  distinct Open WebUI subjects.
- Both receive the two configured directory groups.
- Removing Beta from one group and logging in again removes only that group;
  Alpha remains unchanged.
- Removing Beta's final group and logging in again clears all local group
  memberships.
- The full Open WebUI candidate acceptance also passes private-chat isolation
  and persistence, Channels membership and persistence, anonymous denial,
  owner browser theme/upload smoke, and non-admin membership boundaries.

The test exercises synchronization at the next LDAP login. It does not
implement live directory-event synchronization or invalidate an already-issued
session immediately when a group changes. The accepted account-revocation
procedure still removes the Open WebUI account and invalidates its sessions
before deleting the LLDAP account. Production LDAP group management remains
disabled; do not enable group-based access based on this staging result alone.

## LDAP to first browser chat — 2026-10-09

The disposable candidate test now continues past LDAP group sync through the
actual Open WebUI browser login. Against the same exact candidate image, it
configured a local synthetic OpenAI-compatible model and explicitly granted
read access to the two verified Alpha/Beta accounts. The test confirmed the
model appeared in Beta's authenticated model catalog, then used Playwright to
log both users in through the LDAP username/password form. Both completed
separate chats that remained present after browser reload; the Beta page did
not contain Alpha's private response marker. The same run confirmed distinct
stable subjects, ordinary-user roles, expected initial group memberships, and
single/final group revocation after fresh LDAP login. Playwright 1.63.0 and the
synthetic backend were used; no production identity or service was involved.

This verifies the documented two-step onboarding contract: confirm the LDAP
identity and household group, then assign that verified Open WebUI user
explicit model read access. LDAP group membership alone does not grant a model
or automatically remove a preexisting per-user model grant. The same run then
used the documented `scripts/revoke-directory-user.sh` procedure to remove
Beta's Open WebUI account before its LDAP identity; the existing Beta bearer
token was rejected afterward. Offboarding must continue to use this account
revocation sequence, as documented in [`shared-identity.md`](shared-identity.md).

No production service, identity, chat, or volume was used. The Docker network,
containers, volume, identity files, and synthetic users were removed after
each test.

## Existing-token role revocation — 2026-10-09

The separate disabled-role session contract also passed against the exact
patched candidate image above. A disposable account received an authenticated
token; an admin changed its Open WebUI role to `pending`; the same preexisting
token then received HTTP 401 from both `/api/v1/users/user/info` and
`/openai/chat/completions`. The completion request was rejected before the
completion handler. The disposable container was removed after the run.

This verifies immediate rejection after an explicit Open WebUI account-role
disable. It does not make LDAP group changes invalidate an active session, and
it does not replace the documented account-revocation procedure for removing
an account from service.
