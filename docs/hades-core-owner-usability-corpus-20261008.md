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

The latest phase-tagged Hermes 0.21.6 workspace-to-commit replay is recorded in the [phase profile report](hades-core-owner-workspace-review-phase-profile-20261009.md). All four stack/repeat arms passed independent test, diff, intended-source scope, commit, and clean-worktree checks. PLAIN STACK median task time was 42.03s; HADES was 64.89s and used more calls (13.5 vs 9) and tool results (9 vs 4). The focused-test stage is the clearest current friction: HADES made repeated searches and reads before running the test, while PLAIN ran the terminal once. HADES also spent 12.11s median in diff review, of which 3.50s was captured at the provider boundary; the remaining time is not yet attributed to an internal stage. This new replay pairs sampling seeds by phase and therefore should not be read as a direct before/after comparison against earlier runs.

The earlier stable-catalog candidate removed an invalid schema mismatch but had zero explicit diff-review tool calls. The later [environment-cache paired rerun](hades-core-owner-workspace-env-cache-rerun-20261009.md) has one review-stage call in both stacks and passes both commits, though HADES remains slower. Neither result includes human answer-quality review or direct Scotty preference; no deployed UI acceptance or broad coding qualification has been collected.

A five-repeat prompt-guidance candidate then instructed HADES to read `README.md` or `Makefile` directly when the test command was unknown. This reduced median HADES model calls to 11 versus 14 for PLAIN and focused-test terminal calls to 6 versus 9, but HADES remained slower (61.35s versus 52.11s) and committed only 4/5 tasks versus PLAIN's 5/5. The model still searched or reread during three of five HADES focused-test turns. It also attempted a terminal call during one read-only diff-review turn; Hermes rejected the attempt with the executable allowlist empty. The prompt candidate is rejected. See the [five-repeat experiment report](hades-core-owner-workspace-guidance-five-repeats-20261009.md).

The first [environment-cache paired rerun](hades-core-owner-workspace-env-cache-rerun-20261009.md)
used a fresh package-manager home in each arm and is useful as a cold-start
profile. The follow-up [persistent-PM rerun](hades-core-owner-workspace-persistent-pm-rerun-20261009.md)
kept an isolated prewarmed package store across arms: both stacks passed both
commits, while HADES remained 7.17 seconds slower by median. HADES used more
tool results, with repeated discovery during focused tests and extra terminal
work around one commit. Neither run provides owner preference evidence.

The corpus remains a testing instrument. It does not establish that HADES is preferred, and direct Scotty dogfood remains a release gate.

The [Git environment profile](hades-core-owner-workspace-diff-review-git-environment-profile-20261009.md)
traces the two-pair replay's slow diff-review setup to Hermes' hardened native
Git collector. That replay uses a fresh package-manager home per arm and
overstates the cold-start cost for a persistent profile: the installed
Hermes 0.21.6 candidate collected tracked and untracked changes in 2.65 s
cold and about 2.44 s warm. A context-local HADES adapter now selects the Git
environment once per collection; a disposable fixture produced identical
diffs while reducing the collector median from 2.42 s to 0.49 s. The real
rootless workspace contract and a two-pair full workflow rerun both passed.
HADES remains slower at task level, and the disposable profiles still include
cold package-manager startup. This evidence is not owner preference or a
production measurement.
