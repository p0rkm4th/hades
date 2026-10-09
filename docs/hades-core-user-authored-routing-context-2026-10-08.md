# User-authored routing context check

Date: 2026-10-08

## Finding and repair

HADES built capability-routing context from recent assistant messages as well
as user messages. An assistant answer could therefore contribute words that
activate a domain route on a short follow-up, even when the user did not ask
for that capability. The model still receives the full conversation; only the
separate HADES routing context now uses recent user-authored turns.

The regression test supplies a follow-up after an assistant message containing
current-information and web-search language. The bounded routing context keeps
the earlier user request and current follow-up but excludes the assistant
message, so the live-web intent rule does not match. Long-history and
multi-user synthetic boundary checks also pass.

## Paired replay

The replay used Hermes 0.21.6 commit `818c13be1dc4fd28987e1e881a9408224afd4535`,
Ollama 0.40.1, Qwen3.6 35B Q4_K_M digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, a verified
65,536-token loaded context, the RTX 3080 Ti Laptop GPU, temperature 1.0, seed
23, and a 512-token output cap. Both stacks used isolated Hermes profiles,
loopback Ollama, alternating order, and no API toolsets. One repeat covered
eight conversation cases and 16 turns per stack. The report stores aggregate
metadata only, without prompts or answers.

Before the change, one replay exposed a web-search schema on the vague
follow-up in `core-05` turn 4. That request carried 766 bytes of tool schema
and 9,094 bytes of model payload, with 6,199 ms TTFT. A separate pre-change
repeat did not expose that schema, so this is an intermittent, history-shaped
failure in a small sample rather than a stable latency estimate. After the
change, all 15 model-backed HADES turns exposed zero schemas; the same
`core-05` follow-up carried 3,781 bytes and had 1,295 ms TTFT. PLAIN had no
schemas in either run.

After the change, a three-repeat `conversation-v1` replay completed 48 turns
per stack with content on all turns. PLAIN had 48 provider generations; HADES
had 45 because each repeat's first `core-08` pantry-expiry turn returned the
bounded deterministic response that canonical Grocy was unavailable, without
invoking the model. Those three unavailable-service fallbacks are not counted
as ordinary model-backed comparisons. Neither stack emitted tool calls. All
45 model-backed HADES requests exposed zero tool schemas.

Across the 45 model-backed paired turns, the median HADES-minus-PLAIN deltas
were **+23.6 ms TTFT** and **−38.4 ms total time**. HADES was faster in 12/45
TTFT pairs and 25/45 total-time pairs. Per-stack median TTFT was 1,073 ms PLAIN
and 1,073 ms HADES; median total time was 1,693 ms PLAIN and 1,707 ms HADES.
These medians show no meaningful ordinary-chat latency advantage for either
stack in this slice. HADES answers were shorter in aggregate, but answer
quality was not reviewed, so that is not counted as an improvement.

The initial one-repeat runs remain useful as a focused before/after diagnosis:
an intermittent assistant-history phrase activated the web schema once before
the filter, and no web schemas appeared in the first post-change replay. The
three-repeat replay strengthens the post-change tool-exposure evidence; it is
still a small synthetic comparison, not a preference study.

## Evidence and limits

- Before: [`before-user-intent-filter`](../benchmarks/hades-core-owner-conversation-v1-hermes0216-ollama0401-before-user-intent-filter-20261008.json)
- After: [`user-intent-filter`](../benchmarks/hades-core-owner-conversation-v1-hermes0216-ollama0401-user-intent-filter-20261008.json)
- Three-repeat after: [`user-intent-filter-3repeats`](../benchmarks/hades-core-owner-conversation-v1-hermes0216-ollama0401-user-intent-filter-3repeats-20261008.json)
- Focused test: [`test-long-conversation-boundary.sh`](../scripts/test-long-conversation-boundary.sh)

This verifies one targeted routing repair and one post-change synthetic
conversation replay. It does not establish general answer quality, owner
preference, complete corpus coverage, deployed Open WebUI behavior, or a stable
latency improvement. No preference labels were assigned.
