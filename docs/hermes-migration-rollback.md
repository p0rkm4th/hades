# Hermes migration and rollback runbook

This is a public-safe operator runbook. It contains no deployment addresses,
credentials, sessions, or backup artifacts. Production remains pinned until
all private gates below pass.

## Preconditions

1. Record the current Hermes version, image/package revision, overlay revision,
   and service configuration in the private deployment record.
2. Create and checksum a private encrypted backup of the Hermes profile and
   each authoritative dependency according to `backup-restore.md`.
3. Confirm the rollback artifact is readable in an isolated staging namespace.
4. Run the current production smoke check and retain its output.
5. Verify the candidate's declared optional dependencies, focused upstream
   tests, normal conversation, MCP tool-search/tool-call contract, and ACP
   contract.

## Candidate rehearsal

Run the candidate with a disposable profile and synthetic provider. Verify:

```text
health endpoint
normal Open WebUI conversation
tool search -> tool call -> post-tool continuation
Hindsight retain/recall contract
bounded Agent Zero failure and success
Grocy read/mutation contract against synthetic state
reload and clean process restart
```

No candidate process may point at production Hindsight, Grocy, Agent Zero,
SearXNG, Open WebUI, or owner credentials.

## Production change window

1. Announce a short maintenance window in the private operator record.
2. Stop Hermes gracefully and confirm its process has exited.
3. Install or activate the candidate while preserving the prior revision and
   overlay in a recoverable location.
4. Start Hermes and wait for health before opening owner traffic.
5. Run smoke checks, then perform the owner UI/canonical-state acceptance
   matrix. A response that merely says an action succeeded is not sufficient.
6. Keep the prior artifact until reload, service restart, and acceptance all
   pass.

## Rollback triggers and procedure

Rollback immediately if health fails, the owner UI cannot complete a normal
conversation, a tool result is fabricated or not canonical, persistence fails,
or any integration crosses its authorization boundary.

1. Stop the candidate gracefully.
2. Restore the prior Hermes package/revision, overlay, and private profile
   configuration.
3. Start the prior service and wait for health.
4. Run the smoke check and a harmless owner read workflow.
5. Verify canonical state and reload persistence.
6. Record the failure and preserve logs privately for diagnosis.

Do not delete the candidate or prior backup until the incident review and
acceptance evidence are complete.

## Current disposition

The candidate now passes isolated normal conversation, native MCP, ACP,
Hindsight exact-bank retain/recall, synthetic Grocy read/mutation, disposable
SearXNG search, bounded Agent Zero bridge success/failure, synthetic
read-only Actual Budget integration, a fresh disposable Open WebUI
owner-facing path, authenticated restart health, and profile
backup/extraction evidence. The remaining production-shaped gap is an
owner-preserving migration rehearsal against a disposable copy of the
existing WebUI state, proving that conversations, settings, and Hindsight
history remain attached to the existing owner identity. Real Agent Zero was
deliberately not connected; its bounded bridge contract is proven with a
loopback fixture, while native A2A remains a separate compatibility decision.
Therefore no production migration is authorized by this document.

## Owner-state rehearsal note

On 2026-09-13 a disposable copy of the production Open WebUI data was made
via the container's data path; SQLite integrity was `ok`, with 43 users and
142 chats in the copy. A Hermes 0.21.2 detached launch was then attempted
against the isolated candidate profile. It initialized its MCP children and
wrote a startup record claiming 8643, but no reachable 8643 listener was
observed from the host, so the rehearsal was stopped before any WebUI traffic
or data migration. Production WebUI and Hermes remained healthy throughout.
The next rehearsal must use a supervised/foreground launch with an explicit
listener assertion before starting the cloned WebUI.
