# Hindsight memory context profile comparison — 2026-10-09

This is a focused synthetic diagnostic, not owner dogfood or a production
configuration decision. The paired artifacts are
[`PLAIN first`](../benchmarks/hades-core-memory-ctx8k-user64k-plain-first-fixed.json)
and
[`HADES first`](../benchmarks/hades-core-memory-ctx8k-user64k-hades-first.json).
Both use fresh disposable Hindsight volumes and one paired sample; the stack
order is counterbalanced.

## Profile and validity

- Hermes 0.21.6, Ollama 0.40.2, Qwen3.6 35B Q4_K_M, and the same host GPU.
- The interactive model was loaded and verified at 65,536 context for both
  arms. Hermes 0.21.6 refused the 16,384-context profile before generating a
  turn, requiring at least 64,000 tokens. The 16K attempts are incomplete and
  excluded from the comparison.
- Hindsight 0.10.3 used its supported
  `HINDSIGHT_API_LLM_OLLAMA_NUM_CTX=8192` setting. The Ollama staging process
  used context 65,536, two parallel requests, and up to two loaded models.
  This isolates a smaller Hindsight context while retaining Hermes' required
  interactive context; it does not reproduce the inactive local Ollama unit's
  16K default or prove deployed runtime configuration.
- The synthetic scenario stores a personal fact, then asks for it from a new
  Hermes session. User answers and memory text are not retained in the JSON.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Ordinary chat total, PLAIN-first / HADES-first | 2.18 s / 9.29 s | 2.51 s / 1.99 s |
| Immediate cross-session recall | Correct in 2/2 | Missed in 2/2 |
| Settled cross-session recall | Not applicable | Correct in 2/2, 11.62–12.03 s |
| Hindsight background drain | Not applicable | 26.48–26.49 s |
| Prompt tokens on automatic recall | 3,366–3,370 | 726–729 |
| Tool schema exposure per recall | 1 schema, 3,449 bytes | 0 |
| User-facing generations on automatic retain | 2 | 1 |

Ordinary-chat timing is strongly order-sensitive: PLAIN took 9.29 seconds
after the HADES-first arm, despite per-arm runtime normalization. Treat these
two samples as evidence of order/cold-state sensitivity, not as a latency win
for either stack. The automatic-memory result is consistent across both
orders: PLAIN recalls the synthetic fact immediately; HADES does not. HADES
eventually recalls it after background Hindsight work drains, but exceeds the
simple-memory target. Its smaller prompt and absent memory tool schema are
measurable reductions in turn context; they do not compensate for the missed
fact in this scenario.

The 8K Hindsight model residency observation was 11.66 GB VRAM, while the
interactive model was reported at 12.91 GB when resident. The HADES immediate
recall turn observed the interactive model as not resident. This profile
therefore did not eliminate model contention. It also does not establish that
8K is a better Hindsight quality setting; owner-quality review remains open.

## Native Hermes prefetch check

Two earlier opposite-order probes temporarily disabled HADES' direct
`prefetch` override and no-op queue override, allowing Hermes 0.21.6's native
Hindsight queue behavior. They are
[`HADES first`](../benchmarks/hades-core-memory-native-prefetch-hades-first.json)
and
[`PLAIN first`](../benchmarks/hades-core-memory-native-prefetch-plain-first.json).
HADES missed the immediate new fact in both runs. After the fact became
canonical and Hindsight's queue drained in 27.4–27.8 seconds, a fresh-session
HADES query still missed it. The queued result did not reach the new session;
its prompt remained near the no-memory baseline. This rejects native
next-turn prefetch as a replacement for HADES' authenticated current-query
recall on cross-session use. These were temporary benchmark-only patches, not
production changes.

## Harness corrections and limits

An initial 16K run was invalid because Hermes rejected the provider context
before generation. A later valid-context sample completed all measured turns
and Hindsight drain but hit a `KeyError` while serializing runtime-normalization
metadata. The serializer now preserves that metadata; only successful reruns
are linked above. The measurements do not qualify general memory quality,
correction behavior, production, or owner preference.

Next, investigate a current-query Hindsight path that can expose a newly saved
fact before the background extraction/consolidation queue finishes, while
preserving the authenticated subject-bank boundary. Keep the 8K context cap as
a benchmark candidate only until both immediate recall and memory quality are
qualified.
