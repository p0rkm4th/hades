# PLAIN/HADES recovery-v1 comparison on Hermes 0.21.6

Date: 2026-10-08

## Scope and controls

This three-repeat synthetic replay covers seven recovery and topic-repair cases
with 30 turns per stack. It intentionally provides neither domain/workspace
tools nor source data, so it measures how each stack responds when requested
capabilities are unavailable. It is not action-success or owner-quality
acceptance.

Both stacks used Hermes 0.21.6 source commit
`818c13be1dc4fd28987e1e881a9408224afd4535`, Ollama 0.40.1, Qwen3.6 35B
Q4_K_M digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`,
verified 65,536 context, the RTX 3080 Ti Laptop GPU, temperature 1.0, seed 23,
and a 512-token cap. Requests were loopback-only, serialized, and order-balanced.
Metrics retain no prompts or answers.

## Results

Both stacks returned content on all 30 turns and emitted no tool calls or tool
schemas. PLAIN made 30 provider generations; HADES made 24. On three turns
each, HADES returned its deterministic unavailable-source response for a
project-file read (`core-35`) and backup-status request (`core-37`), with no
provider call. Those six bounded responses are reported separately from the
model-backed timing pairs; they are not scored as failures merely for stating
that the source was unavailable.

Across the 24 common model-backed pairs, the median HADES-minus-PLAIN deltas
were **+50.8 ms TTFT** and **+164.9 ms total time**. HADES was faster in 7/24
TTFT pairs and 11/24 total-time pairs. Per-stack medians across all turns were
1,124 ms TTFT / 2,121 ms total for PLAIN and 1,152 ms / 2,129 ms for HADES;
these include HADES' six fast deterministic responses and should not be read
as model-only latency.

## Interpretation and limits

The unavailable-source paths complete quickly without a model generation, but
this synthetic comparison did not review their answer wording. Model-backed
HADES turns were modestly slower by paired medians and exposed no extra tools.
HADES answers were shorter in aggregate; without human quality review, that is
not evidence of better answers. No owner preference was collected.

This covers only seven seeded recovery cases on one local model/runtime pair.
It does not test actual Grocy/homelab/workspace reads, action execution,
deployed authentication, or the full 55-case corpus.

Artifact: [sanitized three-repeat metrics](../benchmarks/hades-core-owner-recovery-v1-hermes0216-ollama0401-3repeats-20261008.json).
