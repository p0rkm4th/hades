# HADES consolidation checkpoint

Date: 2026-09-12. This is a historical consolidation report, retained for
provenance. The current verified state is maintained in
[`CAMPAIGN_STATE.md`](../CAMPAIGN_STATE.md) and the capability ledger; do not
use this report's next-action or authorization language as the current
checkpoint. It does not authorize real finance, homelab, smart-home,
destructive, or multi-user changes.

## Current capabilities and founding closures

Conversation, Hindsight memory, Grocy household workflows, bounded Agent Zero
delegation, memory-plus-household composition, and synthetic Actual finance
reads are PASS + PERSISTENCE or better in the owner acceptance record. Their
finite founding contracts are closed; wording sensitivity, broader operator
tasks, and additional edge cases are hardening work.

Production is healthy on Hermes 0.14.0 and Open WebUI 0.11.5. The owner-facing
runtime remains pinned and was not upgraded during this campaign.

## Hermes upstream decision

The current stable tagged upstream is Hermes Agent v0.21.2 (v2026.9.11),
confirmed from the upstream release listing. A clean isolated checkout passed
390 focused A2A, Hindsight, API-server, and gateway tests, and a normal
Open-WebUI conversation passed against a clean upstream gateway. The clean
checkout initially lacked the declared optional MCP extra; after installing
the exact upstream MCP dependencies, a deterministic synthetic provider drove
tool search, MCP invocation, and post-tool continuation, with the MCP process
and Hermes agreeing on the canonical readiness marker. This is strong
isolated-contract evidence, not permission to replace the known-good
production runtime; a full synthetic owner-contract matrix and rollback
rehearsal remain before migration.

The HADES overlay is retained for now. Its behaviors are narrowly
classified in `docs/hermes-overlay-inventory.md`: model/domain policy,
completion-only isolation, dynamic MCP reconciliation, Hindsight normalization,
streaming safeguards, and startup discovery. No behavior has sufficient clean
upstream owner-path evidence to delete safely yet. The next deletion target is
dynamic tool reconciliation after an upstream staging owner run proves native
discovery parity. The overlay is not a HADES core, planner, registry, or
generalized runtime.

## Agent Zero A2A decision

The pinned Agent Zero image's native A2A server was enabled only in a separate
disposable container. Its tokenized FastA2A endpoint accepted a standard
JSON-RPC `message/send` request and returned the expected bounded synthetic
response. Hermes v0.21.2's native client expects a different agent-card and
transport shape when pointed at that endpoint; the direct interoperability
probe failed while the native Agent Zero request passed. Retain the one-tool
private MCP bridge. Re-evaluate when a matching card/transport contract and
authenticated lifecycle are available without widening authority.

## Domains and gates

Homelab remains preparation-complete: Proxmox, NetBox, and Uptime Kuma are
defined as separate read-only authorities, but endpoints and credentials are
owner-gated. Home Assistant is preparation-complete with an explicit entity
allowlist and security-sensitive exclusions. Actual Budget is selected for
synthetic finance integration; real files, provider credentials, sync, and
finance writes remain owner-gated. LLDAP/shared identity remains deferred
until the multi-user milestone.

## Recovery and security

The temporary plaintext test administrator recovery file, duplicate database copies, and
browser cookie artifacts were retired after authenticated admin use, synthetic
non-admin dogfood, restart, and database-health checks. One protected private
database backup remains until the owner confirms the temporary password has
been replaced. No recovery material is tracked in Git.

## Historical next action

Run a clean Hermes v0.21.2 synthetic owner-contract matrix against isolated
Hindsight, Grocy, SearXNG, Agent Zero, and Open WebUI endpoints; classify each
overlay behavior from observed results; then prepare a rollback-safe migration
only if the owner contract remains green. Independently continue homelab
credential-free adapter design and component-specific backup drills.
