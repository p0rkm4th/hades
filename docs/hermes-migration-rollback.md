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

The candidate passes isolated normal conversation, native MCP, ACP, Hindsight
exact-bank retain/recall, synthetic Grocy read/mutation, disposable SearXNG
search, bounded Agent Zero bridge success/failure, synthetic read-only Actual
Budget integration, a fresh disposable Open WebUI owner-facing path,
authenticated restart health, and profile backup/extraction evidence. The
owner-preserving rehearsal against a disposable copy of existing WebUI state
also passed: existing account identity and chat history remained attached and
a candidate chat persisted in the clone. Production promotion is still
deferred because the later controlled live attempt could not authenticate the
owner for burn-in; Hermes 0.14.0 remains the baseline. Real Agent Zero was
deliberately not connected; its bounded bridge contract is proven with a
loopback fixture, while native A2A remains a separate compatibility decision.

## Owner-state rehearsal note

On 2026-09-13 a disposable copy of the production Open WebUI data was made
via the container's data path; SQLite integrity was `ok`, with 43 users and
142 chats in the copy. A Hermes 0.21.2 detached launch was then attempted
against the isolated candidate profile. It initialized its MCP children and
wrote a startup record claiming 8643, but no reachable 8643 listener was
observed from the host, so the rehearsal was stopped before any WebUI traffic
or data migration. Production WebUI and Hermes remained healthy throughout.
The detached-launch issue was corrected by using an explicit supervised
foreground launch and a fresh candidate API key. The follow-up rehearsal
authenticated the preserved Luna account with the same account ID and admin
role, rendered existing chat history in the clone, completed a candidate chat
through the WebUI, and verified the resulting marker in the clone database.
The clone, temporary credential, candidate gateway, and candidate container
were removed afterward. This proves WebUI identity/chat continuity. A
separate read-only production Hindsight check confirmed the existing
`hades-owner` bank and zero pending operations, while the candidate overlay
resolved the actual private owner subject to owner scope without querying that
bank from the candidate.

The pinned Agent Zero image was also booted with a fresh disposable volume and
loopback-only port. Its real API was healthy but rejected the synthetic bridge
credential with HTTP 401; the image-managed API token was not available as a
safe staging secret. The candidate container and volume were removed, and no
production Agent Zero credential or state was used. The bounded MCP bridge is
therefore the validated candidate substitute; native A2A/real-runtime
validation remains a separate follow-up, not a reason to weaken the bounded
bridge or connect production credentials during staging.

## Promotion decision

The isolated Hermes 0.21.2 matrix is promotion-ready for a controlled,
rollback-backed production change window. The subsequent controlled attempt
and its rollback are recorded below; production currently remains on Hermes
0.14.0.

## Preflight backup correction

The older migration backup directory contained two zero-byte artifacts and is
not sufficient by itself. Before any change window, a fresh private preflight
set was created from the live containers: Open WebUI and Grocy SQLite copies
passed `quick_check`, the Hindsight PostgreSQL custom-format dump was created
through its container namespace and passed `pg_restore --list`, the Hermes
profile and service unit were non-empty, and a SHA-256 manifest verified all
artifacts. The zero-byte legacy artifacts remain historical evidence only and
must not be used for rollback.

## Controlled promotion result

On 2026-09-13, production Hermes was briefly started with Hermes 0.21.2,
Gemma 12B, the retained HADES policy overlay, and a clean runtime working
directory. Hermes health and immediate composition checks passed. The owner
regression could not authenticate the existing owner using the available
protected bootstrap credential, so the rollback rule was applied instead of
continuing burn-in without owner proof. The original unit and profile were
restored from the validated preflight set, Hermes 0.14.0 was explicitly
restarted, and its health plus WebUI health returned successfully. No
application database or owner identity was changed.

Production decision: Hermes 0.21.2 is deferred, not accepted. A future retry
requires a verified current owner authentication/session path, followed by
the owner regression checklist. The preserved 0.14.0 runtime remains the
daily-driver baseline.
