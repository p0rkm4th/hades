# Shared identity boundary

The current HADES deployment does not have a shared user database: Open WebUI
uses its own application database, Hermes uses service credentials, and Grocy
uses its own local users. A Grocy API key is not a browser login and must not be
repurposed as one.

The supported migration path is a private LDAP directory. The staged
`deploy/lldap.compose.yaml` file provisions LLDAP with persistent data and
file-backed secrets, but does not alter the existing applications or expose an
LDAP port to the LAN.

## Roadmap status

The identity foundation is now being evaluated in an isolated staging
deployment. Production remains on local Open WebUI authentication; no owner
account, production conversation, Grocy instance, or Hermes credential was
changed. The staged LLDAP instance contains only synthetic directory data and
is reachable through its loopback administration UI and private Docker network.

The first staging contract is proven: Open WebUI's supported LDAP endpoint
authenticates two synthetic users, provisions distinct Open WebUI subjects,
and returns the same subject for each user on repeated login. The isolated
staging path separately proves conversation isolation, Hindsight namespace
isolation, shared Grocy behavior, and per-user settings persistence. It does
not prove production cutover or production authorization. Open WebUI bearer
tokens are not live-checked against LDAP. The accepted revocation contract is
therefore a coordinated operation that removes the application account before
the directory account; the supported bridge also verifies that the old bearer
token is rejected and that both records are gone. Automatic directory-event
synchronization is not implemented and remains a separate future architecture
decision.

The HADES-built Open WebUI 0.11.4 candidate also passed fresh LLDAP sign-in
for synthetic owner and household accounts on the pinned LLDAP image. Their
Open WebUI subject IDs remained distinct and unchanged after a WebUI restart
and fresh LDAP login. On an empty WebUI database, the first LDAP account is
created as `admin` and the next as `pending`, without regard to their LLDAP
groups. A reversed-order replay made the household account `admin` and the
owner account `pending`. This is Open WebUI's first-account bootstrap behavior,
not group-based authorization. On a new deployment, authenticate and verify
the intended owner as the first account before allowing household sign-in;
confirm the resulting owner mapping and keep subsequent household accounts
pending until their identity and access are reviewed. Existing production
state was not involved in these tests.

The same candidate acceptance promoted the synthetic household account only
after its fixture group was verified, uploaded a private text file through
Open WebUI's authenticated file API, read it back as the owner, and confirmed
the household account could not retrieve it. The file survived a WebUI
restart. The served HADES theme CSS/JS and finance/receipt upload assets
matched their tracked source bytes exactly. This verifies API upload and static
asset delivery; it does not yet verify the rendered theme or browser file
picker.

## Migration order

1. Run `scripts/prepare-shared-identity.sh` locally. It creates a private
   secrets directory with separate random values for the JWT secret and key
   seed, then prompts for the LLDAP admin password without echoing it. Never
   commit these files.
2. Start LLDAP and create the owner account through its administrator
   interface. The owner chooses the username and password; neither is placed in Git or
   sent through HADES chat.
   On a fresh Open WebUI database, make the owner the first LDAP login and
   verify the account receives the intended administrator role before any
   household login. LDAP groups do not control Open WebUI's first-account role.
3. Attach only the Grocy container to the identity network and configure
   Grocy's `LdapAuthMiddleware` with a read-only bind account.
4. Enable Open WebUI LDAP authentication while retaining local login during
   the migration window. Verify the existing owner chats before changing the
   default login path.
5. Verify manual Grocy login and Open WebUI login with the same directory
   account, then record the result in private acceptance evidence.
6. For deprovisioning, run `scripts/revoke-directory-user.sh` with protected
   operator tokens. It removes the Open WebUI account first, removes the LDAP
   account second, and verifies both records are gone. The bridge can continue
   if a prior interrupted run already removed the application account;
   automatic directory event synchronization remains a future architecture
   decision.

For capability-scoped group propagation, enable Open WebUI's supported LDAP
group-management and group-creation settings, configure the directory's
group-membership attribute, and verify the resulting local group membership
before using `{{USER_GROUPS}}` or `{{USER_GROUP_IDS}}` in a downstream
connection header. An empty expanded header is not evidence that a user has no
capabilities; it may indicate that group management was not enabled.

The historical disposable staging proof used LLDAP 0.6.3 with Open WebUI
0.11.1; those versions are evidence of the identity contract, not the current
rebuild target. The current public pins are maintained in
[`config/versions.env`](../config/versions.env) and the reconstruction
manifest. The staging Open WebUI container was not connected to production
model, Hermes, Hindsight, Grocy, or Agent Zero services. Its synthetic users
are not owner accounts and must not be promoted into production.

## Subject propagation design

Open WebUI supports per-connection custom headers with server-side
`{{USER_ID}}` expansion. The HADES overlay accepts the resulting
`hades-user-<stable-subject>` session key and passes only the validated suffix
as Hermes' provider `user_id`. The supported Hindsight provider can then use
`bank_id_template: hades-user-{user}` to select a separate bank per subject.
This path is server-side: neither model text nor a user-supplied display name
selects a memory bank. It remains unenabled in production until the header,
template, and synthetic Hindsight cross-user tests pass together.

Hermes continues to use its service/API credential; it does not need direct
access to the identity database. Household data remains canonical in Grocy.

## Safety constraints

- Do not disable the current Open WebUI login until LDAP login succeeds.
- Do not expose LDAP port 3890 or the LLDAP admin UI publicly.
- Use LDAPS or a private trusted network before sending passwords across
  hosts.
- Do not copy or attempt to reverse password hashes from Open WebUI.
- A user-password cutover requires an explicit owner-controlled setup step.
- A newly provisioned LDAP user may be created as `pending` by Open WebUI;
  promote it through the supported admin path only after verifying the
  directory identity and intended group membership. Keep it at `pending`
  until that check is complete; do not set every new LDAP account to `user`.
- A promoted Open WebUI `user` may still have an empty model catalog. Grant
  read access to the HADES model only after verifying that same account's
  `hades-household` membership in LLDAP. This model grant enables chat; HADES
  still derives owner-only tools from its trusted stable-subject policy.
- After the user signs in again, verify that `hermes-agent` appears and a
  harmless authenticated turn succeeds. During offboarding, remove the model
  grant and application account before revoking the LLDAP identity with
  `scripts/revoke-directory-user.sh`.

The current HADES template does not automatically synchronize LLDAP groups
into Open WebUI groups. Until that contract is deliberately enabled and
validated, assign household model access to the verified individual user
through Open WebUI's supported model-access controls; do not infer access from
the display name or email suffix.
