# Ordinary chat comparison on Hermes 0.21.6 — 2026-10-08

## Result

A three-repeat replay of core-01 through core-04 completed 18 content-bearing
turns on each stack using the same local Qwen3.6 35B Q4_K_M model, Ollama
0.40.1, 65,536 loaded context, RTX 3080 Ti Laptop GPU, temperature 1.0, seed
23, and 512-token output limit. Hermes 0.21.6 commit
`818c13be1dc4fd28987e1e881a9408224afd4535` was used in both arms. The captured
artifact retains request sizes, timing, token counts, and tool counts, not
prompts or answers.

Both arms returned content on all turns, made one provider generation per
turn, exposed zero tool schemas, and emitted zero tool calls. Median TTFT was
1,068 ms for PLAIN and 1,082 ms for HADES. Median total time was 1,897 ms for
PLAIN and 1,760 ms for HADES. Across the 18 matched turn pairs, median
HADES-minus-PLAIN deltas were **+7 ms TTFT** and **+61 ms total**. The paired
total-time result is the better latency comparison here; the lower per-stack
HADES median coincided with shorter HADES responses (745 vs. 851 completion
tokens overall), whose quality was not reviewed. This replay therefore shows
no material ordinary-chat latency difference and no extra tool overhead.

Median prompt tokens were 719.5 PLAIN and 732.5 HADES. HADES adds a small
system-context cost in this slice, with no observed tool use to justify it.
The result warrants keeping the ordinary-chat path thin; it does not show an
owner preference or an answer-quality improvement.

## Limits

This is a synthetic replay of four short chat cases. It does not cover memory,
domain tools, Open WebUI, coding, production parity, naturalness, or direct
Scotty dogfood. It adds no new corpus case IDs and does not reduce the count of
unreplayed cases.

## Evidence

- Metrics-only artifact: [`hades-core-owner-conversation-v1-hermes0216-ollama0401-core4-three-repeat-20261008.json`](../benchmarks/hades-core-owner-conversation-v1-hermes0216-ollama0401-core4-three-repeat-20261008.json)
- Paired runner: [`benchmark-hades-owner-subset.py`](../scripts/benchmark-hades-owner-subset.py)
