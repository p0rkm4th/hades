# Operator Epsilon preparation

Epsilon is now the active roadmap milestone. This document still describes
preparation-only automation behavior: it does not enable a scheduler or
privileged operator workflow.

## Provider foundation

The bounded synthetic qualification is recorded in
`hades-infra/acceptance/epsilon-provider-throughput-20260921.md` and is
reproducible with `scripts/benchmark-epsilon-providers.py`. Fast is green at
soft concurrency three; Hypnos is reserved for specialized work because of
cold-start latency; Tartarus Deep is not currently qualified because its
GPU/runtime state falls back to a CPU-bound worker and exceeds the 45-second
probe budget. STT/TTS retains the accepted Delta evidence and limits.

Deep is not made a required Epsilon dependency while that qualification is
open.

## Deterministic automation

The first candidate is the read-only `weekly-household-summary` contract in
`config/epsilon-workflows/weekly-household-summary.json`. It is approval-gated,
uses household-scoped canonical reads only, has stable idempotency and
outcome-unknown timeout semantics, and excludes private finance, private
memory, credentials, homelab mutation, and Agent Zero. n8n is the intended
runner, but no n8n instance is currently deployed.

## Operator/browser boundary

The existing Agent Zero MCP adapter and Operator trusted-proxy policy remain
the only prepared operator surfaces. They are bounded, owner-authorized, and
read-only/task-limited. Existing contract tests cover input/output bounds,
unsafe-task rejection, timeout classification, proxy identity, owner-group
authorization, and route validation.

## Personal workspaces

The live authenticated Open WebUI currently exposes New Chat and private
Channels. It does not expose a separate workspace/project surface. Gamma
Channels and ordinary conversations remain the current daily-use primitives;
no replacement productivity suite is being introduced. A dedicated workspace
surface should be considered only after a concrete repeated workflow requires
it.
