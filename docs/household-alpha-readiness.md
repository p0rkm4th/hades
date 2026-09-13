# Household Alpha readiness

This is a public-safe readiness summary. Accounts, credentials, URLs, owner
data, prompts, and deployment-specific identifiers belong in private
operations evidence.

## Current assessment

HADES is ready for a controlled production identity-migration rehearsal, but
Household Alpha is not declared. Production remains on the known-good local
Open WebUI authentication path. No owner account, conversation, memory bank,
Grocy instance, or Hermes production profile has been migrated.

## Verified in isolated staging

| Capability | Status | Evidence boundary |
|---|---|---|
| Synthetic owner plus two household users | PASS + PERSISTENCE | LLDAP login, stable Open WebUI subjects, roles retained after restart |
| Conversation isolation | PASS + PERSISTENCE | Lists and guessed direct chat access reject the other user |
| Personal-memory isolation | PASS + PERSISTENCE | WebUI → Hermes → per-subject Hindsight recall returns only the caller's fact |
| Shared household state | PASS + PERSISTENCE | Grocy remains canonical and shared across synthetic subjects |
| LDAP group propagation | PASS | Directory memberships synchronize and expand into downstream headers |
| Model visibility | PASS | Supported Open WebUI model access record grants household-group read access |
| Finance and Agent Zero exclusion | PASS | Household-scoped sessions receive neither privileged tool |
| User-specific settings | PASS + PERSISTENCE | Distinct themes/effects survive reload and WebUI restart |
| Account revocation | PASS operationally | Ordered Open WebUI-first, directory-second bridge invalidates existing sessions |
| Identity recovery | PASS synthetic rehearsal | Quiesced LLDAP database restored into a separate pinned container |

## Remaining gates

- Production LLDAP cutover must preserve Scotty's existing local login and an
  independently recoverable administrative path.
- The production owner subject must be mapped to the existing Hindsight bank
  without moving or mixing owner data.
- Production Open WebUI must be configured with the subject and capability
  headers only after a private migration rehearsal.
- Production Grocy identity mapping and the coordinated revocation procedure
  require private operational verification.
- Browser DOM acceptance is partial: mobile rendered login and private-chat
  sidebar isolation pass; rendered memory, Grocy, capability, and revocation
  workflows still need browser verification.
- Automatic directory event synchronization is not implemented; operators
  must use the ordered revocation bridge until that architecture is approved.

## Owner gate

The next production action requires an explicit owner-approved migration
window, backup identifiers, rollback target, and exact account mapping. Until
that gate is supplied, production stays on the accepted local-authenticated
path and synthetic staging remains the active acceptance environment.
