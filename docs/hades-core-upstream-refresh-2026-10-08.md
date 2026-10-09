# HADES core upstream refresh — 2026-10-08

This execution-time check supersedes earlier release notes when version or
release status differs. It records authoritative release state and tracked
pins. A current upstream release is not evidence that HADES production runs
that version.

## Owner-facing and core runtime components

| Component | HADES production / candidate record | Latest stable checked 2026-10-08 | Decision |
|---|---|---|---|
| Open WebUI | Production contract 0.11.1; candidate built from review source `148b66e1` with image ID `sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`; tracked candidate pin aligned to 0.11.4 immutable base `ghcr.io/open-webui/open-webui@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f` | 0.11.4, published 2026-09-21 | **HOLD production; finish external build provenance, owner UI, LDAP/group, file-picker, and migration/rollback gates.** On 2026-10-08 the rebuilt image passed synthetic private-chat and Channels acceptance; see [`hades-core-open-webui-0114-candidate-acceptance-20261008.md`](hades-core-open-webui-0114-candidate-acceptance-20261008.md). No newer release was listed by the official Releases API. |
| Hermes Agent | Production 0.21.2; tracked candidate metadata in the campaign checkout still says 0.21.5; a separate review branch pins 0.21.6 source commit `818c13be1dc4fd28987e1e881a9408224afd4535` and SHA-256 `1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8` | 0.21.6, published 2026-10-08 | **QUALIFY in staging; HOLD production.** The release bundles dashboard auth hardening, Git-filter execution protection, and email sender validation. Its notes intentionally defer detailed changes since 0.21.5 until 0.22.0, so do not infer native capability from the large merge count. The upstream Git-spawn security regression passed 25/25 against exact candidate source. |
| Ollama | No current production runtime version was freshly verified or pinned in `config/versions.env`; candidate binary at `/mnt/shared/.../ollama-0.40.1` reports 0.40.1 | 0.40.1, published 2026-10-07 | **INVESTIGATE deployment provenance; USE 0.40.1 for staging comparison.** Release notes include Windows large-file handling, CLI onboarding, manifest symlink behavior, and removal of a carried Apple Metal patch now present upstream. The Linux x86_64 staging binary SHA-256 is `0f108cffa4c03c756298e6310030c01bfc2d18c21c6802ddb939b00aaa936f47`. |
| Hindsight | Configured immutable pin `sha256:84ab…9028`; local image OCI labels identify it as 0.9.2 / source `ebad478`. No Hindsight service was running in this environment, so deployed runtime parity is unverified. Prior staged Hermes plugin checkout was integration tag 1.2.1 (`d56c4ac`) with client/embed 0.10.2. | 0.10.3, published 2026-10-08 | **QUALIFY CANDIDATE; HOLD configured production pin.** Exact v0.10.3 image digest `sha256:b5da…e002` passed disposable API/worker recovery and authenticated HADES explicit-memory acceptance with Hermes 0.21.6 plus the exact v0.10.3 plugin source. Alpha retain/correction/fresh typo recall and Beta/Gamma isolation passed. A follow-up log capture found 33 failed retries from unrelated Hermes automatic title-generation tasks against the intentionally unavailable test model; it did not change the memory results, but ordinary-turn auxiliary behavior remains unqualified. Automatic provider retain/prefetch, semantic paraphrase, embedded-daemon mode, and integrated restart acceptance remain open; see [`hades-core-hindsight-0103-candidate-review-20261008.md`](hades-core-hindsight-0103-candidate-review-20261008.md). |

## Relevant comparative evidence

The same-day clean-worktree synthetic workspace escalation replay is recorded
in [`hades-core-workspace-escalation-comparison-20261008-clean-v2.md`](hades-core-workspace-escalation-comparison-20261008-clean-v2.md).
It used current Hermes 0.21.6 and Ollama 0.40.1 with matched model, context,
sampling, sandbox, and prompts. HADES preserved the explanation/action
boundary and exposed smaller tool schemas, but its median composed task was
slower than PLAIN STACK in two repeats. It is diagnostic evidence only, not
owner preference or a release qualification.

## Authoritative sources

- [Open WebUI v0.11.4](https://github.com/open-webui/open-webui/releases/tag/v0.11.4)
- [Hermes Agent v0.21.6](https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6)
- [Ollama v0.40.1](https://github.com/ollama/ollama/releases/tag/v0.40.1)
- [Hindsight v0.10.3](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.3)

## Next actions

1. Reproduce the workspace pair from a clean, reviewable source commit and
   expand the balanced subset; investigate the out-of-catalog mutation attempt
   and fix-turn tool loop.
2. Qualify Hermes 0.21.6 session continuity, MCP refresh, and authenticated
   multi-user UI against the exact candidate artifact. Deferred tool search
   and its owner/household Grocy authorization boundary passed the focused
   candidate runtime check; see
   [`hades-core-hermes-0216-tool-search-scope-review-20261008.md`](hades-core-hermes-0216-tool-search-scope-review-20261008.md).
3. Stage Hindsight 0.10.3 and test native Hermes plugin/process behavior for
   removable HADES compatibility code.
4. Identify and pin the actually deployed inference runtime before any
   production upgrade decision.

Production versions and services were unchanged by this audit and benchmark.
