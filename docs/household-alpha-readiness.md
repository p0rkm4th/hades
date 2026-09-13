# Household Alpha readiness

This is a public-safe readiness summary. Accounts, credentials, URLs, owner
data, prompts, and deployment-specific identifiers belong in private
operations evidence.

## Current assessment

Production identity migration is in progress and the existing owner path
remains healthy, but Household Alpha is not declared. Production Hermes remains
on the known-good baseline; finance and privileged household capabilities are
still excluded.

## Verified in isolated staging

| Capability | Status | Evidence boundary |
|---|---|---|
| Synthetic owner plus two household users | PASS + PERSISTENCE | LLDAP login, stable Open WebUI subjects, roles retained after restart |
| Conversation isolation | PASS + PERSISTENCE | Lists and guessed direct chat access reject the other user |
| Personal-memory isolation | PASS + PERSISTENCE | Mobile WebUI → Hermes → per-subject Hindsight retain/recall rendered successfully for Alpha; prior cross-user backend checks remain green |
| Shared household state | PASS + PERSISTENCE | Mobile WebUI rendered the shared Grocy list and the canonical API matched all returned rows |
| LDAP group propagation | PASS | Directory memberships synchronize and expand into downstream headers |
| Model visibility | PASS | Supported Open WebUI model access record grants household-group read access |
| Finance and Agent Zero exclusion | PASS | Household-scoped sessions receive neither privileged tool; mobile DOM finance probe returned no private value |
| User-specific settings | PASS + PERSISTENCE | Distinct themes/effects survive reload and WebUI restart; rendered Alpha settings and API agree |
| Account revocation | PASS operationally | Ordered Open WebUI-first, directory-second bridge invalidates existing sessions |
| Identity recovery | PASS synthetic rehearsal | Quiesced LLDAP database restored into a separate pinned container |

## Remaining gates

- Complete the final owner-facing regression and readiness audit.
- Confirm the documented ordered revocation procedure and settings isolation
  after the controlled restart.
- Retire the temporary administrator recovery credential only after the
  independent recovery path is documented and verified.
- Browser DOM acceptance is substantially covered: mobile rendered login,
  private-chat sidebar isolation, household model visibility, memory
  retain/recall, shared Grocy read and mutation/cross-user read, finance
  exclusion, revocation, and Alpha's settings persistence all pass in
  disposable staging. The remaining browser hardening is limited to
  additional Grocy purchase/consume variations. Temporary providers and
  gateways are cleaned up after each run.
- Automatic directory event synchronization is not implemented; operators
  must use the ordered revocation bridge until that architecture is approved.

## Owner gate

The remaining gate is operational acceptance, not a new owner authorization:
the production synthetic matrix and final owner regression must remain green
before onboarding a real household user.
