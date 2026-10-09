# HADES Core comparative owner corpus

The campaign corpus is [`hades-core-owner-corpus-v2.json`](../benchmarks/hades-core-owner-corpus-v2.json): 55 sanitized, multi-turn owner-pattern cases across ordinary conversation, follow-ups, memory, Grocy, homelab, research, workspace/coding, agentic use, authority, and failures. Cases are paraphrases seeded from documented dogfood prompt families, not raw transcripts. Preference labels remain unassigned until direct owner review.

The corpus records 26 cases with direct synthetic replay evidence and 29 without a direct replay. This is partial coverage, not a pass rate. The current ordinary-chat comparison is the five-repeat core-4 pair in [`hades-core-plain-stack-hermes0216-core4-2026-10-08.md`](hades-core-plain-stack-hermes0216-core4-2026-10-08.md). That comparison uses Hermes 0.21.6 and Ollama 0.40.1 in both arms, 30 turns per arm, no tools, and no response-text retention. It found no material latency difference; it does not establish answer quality or owner preference. A three-repeat 48-turn-per-stack conversation-v1 replay after the user-authored routing repair also found no material median ordinary-chat latency difference and zero tool schemas across model-backed HADES turns. The earlier one-repeat diagnostic exposed an intermittent assistant-output influence on capability routing. See [`hades-core-user-authored-routing-context-2026-10-08.md`](hades-core-user-authored-routing-context-2026-10-08.md). The separate three-repeat recovery-v1 replay covers missing-capability answers and topic repair with no tools or source data; it found short deterministic no-model responses for six HADES turns, while the remaining model-backed pairs were modestly slower by median. See [`hades-core-recovery-v1-comparison-2026-10-08.md`](hades-core-recovery-v1-comparison-2026-10-08.md). Neither comparison assigns owner preference.

The replay script is [`benchmark-hades-owner-subset.py`](../scripts/benchmark-hades-owner-subset.py). It captures timing, token and tool metadata while excluding prompts and answers from output records. `test-benchmark-hades-owner-subset-redaction.py` checks output redaction and child-process environment filtering. Use the full seeded corpus for follow-up comparisons; preserve unsuccessful runs and report sample counts.

## Current gaps

- 29 of 55 cases still lack a direct replay.
- No owner preference labels have been collected.
- Existing chat-only comparisons do not assess naturalness or factual quality.
- Tool-backed synthetic comparisons do not establish deployed Open WebUI behavior or owner-visible performance.
- HADES and PLAIN STACK must be rechecked against the same staged upstream/runtime when candidates change.

The latest matched Hermes 0.21.6 workspace-to-commit replay is recorded in [the native diff report](hades-core-owner-workflow-hermes0216-native-diff-replay-2026-10-08.md). Context-aware commit routing and authenticated native Git diff evidence now support the synthetic same-chat workflow: HADES passed tests and made clean source-only commits in 2/2 runs, while exposing no tools during the diff-review turn. HADES median task time was 66.19s vs PLAIN 46.70s, so the small replay does not show a net usability win. No human answer-quality review, direct Scotty preference, deployed UI acceptance, or broad coding qualification was collected.

The corpus remains a testing instrument. It does not establish that HADES is preferred, and direct Scotty dogfood remains a release gate.
