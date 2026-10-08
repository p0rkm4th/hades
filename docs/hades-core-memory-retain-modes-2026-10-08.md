# HADES memory retain-mode experiment — 2026-10-08

## Scope and method

This was a synthetic local comparison of the current Hindsight 0.10.2 image
against two candidate bank-wide settings. It was not owner dogfood or a release
qualification. The matched stack used Hermes 0.21.5, Ollama 0.40.1,
Qwen3.6:35b Q4_K_M for conversation, Qwen3:14b Q4_K_M for Hindsight, 65,536
context, temperature 0.1, top-p 0.95, and a fresh disposable Hindsight volume
for every paired invocation. The two orders were run for each one-case setting.

The tested settings were:

| Setting | Retain behavior | Derived observations |
| --- | --- | --- |
| Current | `concise` | enabled |
| Candidate A | `chunks` | enabled |
| Candidate B | `chunks` | disabled |

The aggregate artifact is
[`hades-core-memory-retain-modes-20261008.json`](../benchmarks/hades-core-memory-retain-modes-20261008.json).
It contains timings, counts, and marker booleans only; no prompt or answer
text was persisted.

## Results

| Setting | Background drain, two orders | Immediate recall | Settled recall |
| --- | ---: | --- | ---: |
| Current | 57.7 / 62.8 s | marker missed; 0 generations | marker found; 10.1 / 10.2 s |
| `chunks`, observations enabled | 17.2 / 17.2 s | marker missed; 0 generations | marker found; 9.7 / 9.6 s |
| `chunks`, observations disabled | 2.0 / 2.0 s | marker missed; 0 generations | marker found; 2.3 / 2.3 s |

For `chunks` with observations disabled, a broader paired memory replay then
used five synthetic owner-memory cases. On the HADES side, both the ordinary
observation recall setting and a one-run `all` recall setting had the same
marker results: core-51 0/1, core-52 0/1, core-53 1/1, core-54 1/1, and core-55
1/1. The PLAIN side also missed core-51 and core-52. Those two misses therefore
do not establish a HADES-specific regression, but they show that raw chunks
alone did not make these prompts reliably retrievable in this corpus.

The current `concise` setting was also replayed across the same five cases.
HADES had the same marker counts as the chunks/no-observation run. Its
background drain took 116.5 seconds in that arm. The synthetic automatic
recall missed its marker after 31.4 seconds, while PLAIN returned the marker in
1.8 seconds. Same-chat topic-switch turns took 25–30 seconds on HADES during
background work, compared with sub-two-second PLAIN turns in this run. These
single-run timings are evidence of a serious candidate HADES tax, not stable
latency estimates.

HADES completed the direct explicit save/correction cases, and the topic-switch
case returned its marker under both tested modes. The checks are marker-based;
they do not rate answer quality or owner preference.

## Decision

Do not change the general Hindsight bank configuration based on this experiment.
Disabling observation extraction reduced the background drain from roughly
one minute to two seconds, but the five-case marker results did not improve and
the automatic-recall marker still failed. That speed gain is not enough to
justify dropping derived observations across the owner's general memory.

The natural-recall route fix in commit `0eea38b7` keeps explicit memory requests
fail-closed while allowing natural personal-history turns to reach Hindsight's
bounded prefetch wait. In the current concise run that produced a model answer,
but did not recover the new automatic fact within the target latency. This
reduces the early zero-generation dead end; it does not resolve the memory
readiness or retrieval-quality problem.

## Automatic recall variant probes

Three additional fresh-volume, plain-first probes varied the HADES recall
budget and type filter. The complete aggregate-only measurements and safe score
diagnostics are in
[`hades-core-recall-variant-probes-20261008.json`](../benchmarks/hades-core-recall-variant-probes-20261008.json).

| HADES profile | Immediate HADES recall | Marker | Idle drain | Settled HADES recall | PLAIN marker |
| --- | ---: | --- | ---: | ---: | --- |
| `mid`, observations | 28.9 s | missed | 43.6 s | 10.0 s | found in 1.8 s |
| `low`, observations | 27.4 s | missed | 42.5 s | 10.3 s | found in 1.8 s |
| `mid`, all types | 28.6 s | missed | 43.5 s | 10.3 s | found in 1.8 s |

In each HADES run, one batch retain was pending and one retain was processing
before recall. The expected fact was not visible in the bank after the
immediate turn, then became visible after the idle barrier. That points to
write readiness as the first issue to diagnose. These one-sample probes do
not support promoting `low` or all recall types.

Score rows in the artifact come from the settled lookups after idle, not the
immediate lookup. Semantic scores were high while cross-encoder scores were
much lower, but result text was not retained, so candidate identity is
unknown. Hindsight v0.10.2 uses cross-encoder relevance as its primary score
and multiplies it by recency, temporal, and proof-count boosts; see the pinned
[score calculation](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/engine/search/reranking.py#L187-L205)
and [combined-score assignment](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/engine/search/reranking.py#L288-L303).

## Next evidence needed

- The one-pass safe score diagnostic is recorded in
  [`hades-core-recall-score-diagnostic-20261008.json`](../benchmarks/hades-core-recall-score-diagnostic-20261008.json).
  It reproduced a 28.9-second immediate HADES miss versus a 1.8-second PLAIN
  hit. The score rows describe HADES recall after the 43.6-second idle drain,
  when HADES found the marker in 10.0 seconds; before idle the expected fact
  was not visible and retain operations were active. Do not use settled score
  values to explain the immediate miss. Ordinary-turn timings were also
  single samples and do not establish a latency win.
- Repeat with counterbalanced order and capture only safe per-stage timings for
  operation visibility, provider prefetch, and inference. Retain-only state
  must remain fail-closed. The one-pass `low` probe is too weak to change
  HADES config.
- Compare concise extraction with observations disabled separately from raw
  `chunks`; do not infer that switching off observations is equivalent to
  disabling fact extraction.
- Add repeats and human review before changing owner-bank settings.
- Keep automatic recall latency, operation drain time, and same-chat latency as
  separate measurements.
- Revisit after the full comparative corpus and direct Scotty dogfood; neither
  is complete.
