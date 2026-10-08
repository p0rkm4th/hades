# Current-context core-09 memory comparison — 2026-10-08

## Method

Ran one synthetic core-09 memory comparison in each stack order, with a fresh disposable Hindsight service/database for each invocation. The HADES source was `8a5923f764ccebdbf283f49a54147eb078b02418`; both arms used Hermes 0.21.5, Ollama 0.40.1, Qwen3.6 35B Q4_K_M (`a7eb95c5…`), temperature 0.1, top-p 0.95, and a configured 65,536-token context. Hindsight used the pinned v0.10.2 image (`sha256:d1840062…`), Qwen3:14B Q4_K_M, one LLM call at a time, concise retention, and observations enabled. HADES was owner-scoped for a synthetic owner identity.

The runner processed an un-overridden 7,010-token OpenAI-compatible context probe and observed 65,536 context in Ollama `/api/ps`. Each measured PLAIN Hermes provider generation requested 65,536, and its generation-boundary observation reported a resident 65,536 context. HADES's model-free local memory responses had no provider generation to sample; its model-mediated generations requested 65,536. Hindsight's separate 14B model reported a 40,960 runtime context. All run data was sanitized aggregate metadata; no assistant responses, prompts, memories, tool arguments, or database content were persisted in the artifacts.

The task included the core-09 synthetic `$3,000` save/natural recall, an automatic fresh-fact retain/recall, corrected-fact checks, and five synthetic preference/continuity cases. The two runs used fresh state and reversed stack order. This is a two-pair exploratory replay, not a human semantic review or owner preference test.

## Results

| Interaction | PLAIN STACK | HADES |
|---|---:|---:|
| Immediate automatic fresh-fact recall | 1.93–2.00 s; marker present in 2/2 | 47–52 ms; truthful pending response, marker absent in 2/2, no provider or tool calls |
| Explicit core-09 recall | 1.48–1.57 s; marker present in 2/2 | 36–37 ms; marker present in 2/2, no provider or tool calls |
| Explicit core-09 recall after Hindsight drained | 1.36–16.38 s; marker present in 2/2 | 59–83 ms; marker present in 2/2 |
| Ordinary-turn prompt / schemas | 3,433–3,437 tokens; one 3,449-byte schema | 720–723 tokens; zero schemas |
| Hindsight drain after HADES arm | Not applicable | 80.2–94.7 s |

PLAIN's post-drain core-09 latency varied sharply by stack order, so the range is shown instead of an aggregate. The runtime observations confirm its model was resident at the generation boundaries, but the benchmark does not isolate the source of the 16.38-second turn. Treat that sample as an order-sensitive observation, not a stable latency estimate.

HADES's fast explicit route returned the synthetic savings target in both runs without a model generation. This is evidence of a useful local-memory fast path for this exact synthetic fact. It does not qualify semantic quality or owner preference. In both runs, HADES's automatic fresh-fact turn arrived quickly but could not yet confirm the fact. The active retain was still pending and the expected memory was not visible at that time.

Each HADES run recorded 15 Hindsight-to-Ollama requests, including 14 `/api/chat` calls. Their cumulative provider elapsed time was 234–269 seconds; Hindsight's model reached 40,960 context and approximately 15.4 GB VRAM. The HADES idle barrier took 80–95 seconds. Those calls were mostly background work from the complete synthetic memory sequence, so they cannot be attributed to core-09 alone. The result does show that HADES memory adds a material asynchronous runtime cost and can evict the interactive model while that work is active.

Across the five supplementary cases, HADES had expected markers in 2/5 immediate answers in each order; PLAIN varied from 2/5 to 4/5. HADES's expected facts became visible after drain in 3/5 cases in both orders. Marker presence is a descriptive measure, not semantic correctness. The large order/sample variation and lack of human answer review prevent a broad memory-quality conclusion.

## Decision

Keep the current fail-closed pending response for automatic recall. Do not enable broad fast-retain or observations-off defaults on this evidence: the asynchronous work is expensive, but correction ordering and useful automatic recall still require stronger semantic qualification. Preserve the explicit authenticated memory route as a promising low-latency behavior; directly dogfood it with Scotty before claiming a product win.

Artifacts:

- [PLAIN-first current-context replay](../benchmarks/hades-core-memory-current-core09-plain-first-20261008.json)
- [HADES-first current-context replay](../benchmarks/hades-core-memory-current-core09-hades-first-20261008.json)

No production settings or services were changed. The disposable Ollama and rootless Docker services were stopped after both runs.
