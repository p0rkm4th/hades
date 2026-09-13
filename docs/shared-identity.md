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

Implementation is deliberately deferred until HADES multi-user support is
complete. Keep this directory staged and inactive; do not create accounts,
attach application containers, or change login providers as part of the
single-owner deployment.

## Migration order

1. Run `scripts/prepare-shared-identity.sh` locally. It creates a private
   secrets directory with separate random values for the JWT secret and key
   seed, then prompts for the LLDAP admin password without echoing it. Never
   commit these files.
2. Start LLDAP and create the owner account through its administrator
   interface. The owner chooses the username and password; neither is placed in Git or
   sent through HADES chat.
3. Attach only the Grocy container to the identity network and configure
   Grocy's `LdapAuthMiddleware` with a read-only bind account.
4. Enable Open WebUI LDAP authentication while retaining local login during
   the migration window. Verify the existing owner chats before changing the
   default login path.
5. Verify manual Grocy login and Open WebUI login with the same directory
   account, then record the result in private acceptance evidence.

Hermes continues to use its service/API credential; it does not need direct
access to the identity database. Household data remains canonical in Grocy.

## Safety constraints

- Do not disable the current Open WebUI login until LDAP login succeeds.
- Do not expose LDAP port 3890 or the LLDAP admin UI publicly.
- Use LDAPS or a private trusted network before sending passwords across
  hosts.
- Do not copy or attempt to reverse password hashes from Open WebUI.
- A user-password cutover requires an explicit owner-controlled setup step.
