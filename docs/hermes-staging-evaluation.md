# Hermes upstream staging evaluation

Status: staging evidence collected; production remains pinned.

## Candidate

The current upstream tagged release is [Hermes Agent v0.21.2, released as
`v2026.9.11`](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.9.11).
It was evaluated in an isolated checkout and Python environment under `/tmp`;
the production Hermes service and profile were not modified.

## Verified in the isolated environment

- Upstream CLI reports Hermes Agent `0.21.2` on Python 3.11.
- Upstream gateway help and key modules compile successfully.
- Native A2A schema, plugin, gating, and reason-roundtrip tests: **117 passed**.
- Hindsight provider, API-server toolset, and normalization tests: **97
  passed** after installing the declared `hindsight-client==0.6.1` staging
  dependency.

These are upstream contract tests, not owner acceptance. No staging process
was pointed at production Grocy, Hindsight, Agent Zero, or owner credentials.

## Compatibility disposition

| HADES behavior | Initial disposition | Reason |
|---|---|---|
| Hindsight provider loading and async retain support | Re-test against upstream | The candidate has native Hindsight provider tests and a declared client dependency. |
| API-server streaming/tool lifecycle | Re-test against upstream | The candidate API-server suite passes, but the real Open WebUI stream contract still needs staging. |
| Native Agent Zero A2A | Retain MCP bridge for now | Hermes `0.21.2` contains native A2A support and its focused suite passes, but the deployed Agent Zero A2A server is disabled. Enabling it would require a new authenticated exposure and owner-visible lifecycle contract. |
| HADES model-intent routing | Retain for now | This is deployment policy for local models and domain tools, not generic Hermes functionality. |
| HADES Grocy tool reconciliation | Retain for now | It compensates for the deployment's dynamic MCP discovery boundary and must be tested against the candidate before removal. |
| Hindsight result normalization / explicit-memory narrowing | Retain for now | These are HADES owner-contract safeguards; remove only after a real staged owner workflow proves upstream parity. |
| Completion-only model isolation | Retain for now | This is an HADES safety policy independent of upstream version. |

## Decision

Do not upgrade production yet. The next safe step is an isolated runtime
profile with synthetic/non-authoritative service endpoints, followed by the
owner-contract matrix in the campaign directive. If that passes, prepare a
rollback-safe migration and delete only compatibility behavior proven
obsolete. If it fails, record the exact contract and keep production pinned.
