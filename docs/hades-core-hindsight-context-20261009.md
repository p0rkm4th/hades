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

## User-authored-only retain candidate

A disposable overlay candidate passed the existing memory-intent and
live-state suppression contracts, then changed automatic retention to send
only user text to Hindsight. The [paired artifact](../benchmarks/hades-core-memory-user-only-retain-plain-first.json)
records the exact temporary overlay hash. In its single sample, HADES still
missed immediate cross-session recall, took 28.41 seconds to drain, and needed
10.70 seconds for settled recall. Hindsight still issued three local model
calls. This did not materially improve readiness over the baseline, so the
candidate was discarded. The sample does not measure broader memory quality;
no change was promoted.

## Chunks-mode and synchronous-retain candidate

A second disposable candidate combined Hindsight 0.10.3's documented chunks /
plain-retrieval profile, `retain_async=false`, `include_chunks=true`, and a
two-second wait on the provider instance's local retain queue when that queue
reported unfinished work. The [single-sample artifact](../benchmarks/hades-core-memory-chunks-sync-plain-first-20261009.json)
records the temporary overlay hash and configuration. PLAIN recalled the
synthetic fact immediately (2.34 s). HADES missed immediately (1.50 s), then
recalled after the Hindsight queue drained in 1.03 s (2.24 s). The fact was
available through a direct Hindsight query 20 ms after the HADES turn, so the
remaining miss is in the provider-turn readiness path, not simply an omitted
chunks flag. The candidate's local-queue wait did not bridge the asynchronous
automatic writer to the fresh-session provider. This profile also changes
memory semantics and has no quality qualification. Reject it; no product code
was promoted. The result narrows the next experiment to whether server-side
retain operation IDs can be observed and joined across provider instances
without waiting on the user-facing reply path.

## Privacy gate for operation-aware readiness

The pinned Hindsight v0.10.3 source adds terminal operation retention, but its
configuration defaults `HINDSIGHT_API_OPERATION_RETENTION_DAYS` to `0`, which
keeps operation rows indefinitely. Retain operation rows can include the
submitted payload, so an operation-aware path must not be promoted with an
unbounded payload journal. For any v0.10.3 deployment candidate, set a bounded
positive retention window and verify the database backend supports the
upstream cleanup routine; do not log operation IDs or payloads. This is a
candidate-upgrade gate, not a claim about the currently configured production
Hindsight 0.9.2 runtime. See the [v0.10.3 source release](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.3),
the exact [`config.py` revision](https://github.com/vectorize-io/hindsight/blob/eb6df499d35300e5b2f3f029b2e6adda04ed90f8/hindsight-api-slim/hindsight_api/config.py),
and the [operation API contract](https://github.com/vectorize-io/hindsight/blob/eb6df499d35300e5b2f3f029b2e6adda04ed90f8/skills/hindsight-docs/references/developer/api/operations.md).

## Native per-item extraction strategy opportunity

The exact Hindsight v0.10.3 source supports named per-item retain strategies:
the Hermes provider adds its configured `retain_strategy` to each retained
item, and Hindsight applies hierarchical overrides such as
`retain_extraction_mode` for that item. This may allow a bank to keep concise
semantic extraction as its default while selected automatic turns use the
chunks mode that was fast in the diagnostic replay. It is only a source-level
opportunity so far; HADES has not configured or tested this mixed profile.
The next candidate should keep explicit saves on concise extraction, apply the
chunks strategy only to automatic turns if Hindsight's API supports that
boundary cleanly, then compare immediate recall, paraphrase, correction,
irrelevant recall, and subject isolation. See the exact [`Hermes provider`
source](https://github.com/vectorize-io/hindsight/blob/eb6df499d35300e5b2f3f029b2e6adda04ed90f8/hindsight-integrations/hermes/__init__.py)
and [strategy resolver](https://github.com/vectorize-io/hindsight/blob/eb6df499d35300e5b2f3f029b2e6adda04ed90f8/hindsight-api-slim/hindsight_api/config_resolver.py).

## Bank-scoped readiness candidate, compared by retain profile

A temporary HADES prefetch adapter queried only `pending` and `processing`
`retain` operations for its already-authenticated subject bank, capped its
wait at 1.25 seconds, requested chunks, and logged only aggregate state and
elapsed time. The disposable Hindsight service was configured with a
one-day terminal-operation retention window; expiration itself was not
exercised. In two single-sample counterbalanced runs using Hindsight's
chunks/plain-retrieval profile, HADES recalled the fresh synthetic fact in
both orders (2.99–3.35 seconds); operation visibility took 0.35 seconds when
the bank was already clear. This shows a promising readiness path for that
profile only. The synthetic tests do not qualify semantic memory quality,
corrections, or owner preference.

The same adapter with normal concise retention did not solve the problem. It
waited its 1.25-second cap while retain remained active, then missed the
immediate cross-session fact in 33.10 seconds. Hindsight drained in 16.21
seconds, and a later HADES recall succeeded in 10.01 seconds. A direct
post-turn probe then found the synthetic marker in one `world` result, with
zero returned chunks; that probe occurred after the slow HADES turn and does
not establish availability at the time of the miss. This sample also recorded
Hindsight extractor calls of 15.30 and 24.94 seconds, so model contention
remains a material part of the delay. **Do not promote this adapter or chunks
profile:** the former does not fix concise-mode readiness; the latter changes
memory behavior and still needs realistic quality and correction evaluation.

Artifacts: [chunks, PLAIN first](../benchmarks/hades-core-memory-operation-aware-chunks-plain-first-20261009.json),
[chunks, HADES first](../benchmarks/hades-core-memory-operation-aware-chunks-hades-first-20261009.json),
[concise failure](../benchmarks/hades-core-memory-operation-aware-concise-plain-first-20261009.json),
and [concise post-turn source probe](../benchmarks/hades-core-memory-operation-aware-concise-chunk-probe-plain-first-20261009.json).
All retain aggregate timings/statuses only; they contain no submitted operation
payload or raw conversation text.

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
