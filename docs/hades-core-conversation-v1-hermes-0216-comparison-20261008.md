# Conversation and follow-up comparison on Hermes 0.21.6 — 2026-10-08

## Method

Three alternating-order repeats covered eight synthetic conversation cases
with 48 turns per stack. Both stacks used Hermes 0.21.6 commit
`818c13be1dc4fd28987e1e881a9408224afd4535`, Ollama 0.40.1, Qwen3.6 35B
Q4_K_M digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`,
65,536 verified loaded context, the same RTX 3080 Ti Laptop GPU, temperature
1.0, seed 23, and 512-token output cap. The gateway runner captured request
metrics but retained no prompts or answer text.

All 96 turns returned content. PLAIN made 48 provider generations; HADES made
45. On three repeated pantry-expiry requests, HADES returned its bounded
canonical-source-unavailable response without a model call. Those are useful
failure-behavior observations, not comparable model latency samples.

## Results

Across 42 paired model-backed turns outside the pantry case, paired median
HADES-minus-PLAIN deltas were **+5.3 ms TTFT** and **+22 ms total**. Per-stack
medians were 1,088/1,804 ms PLAIN and 1,092/1,904 ms HADES. HADES was lower in
16/42 TTFT pairs and 17/42 total-time pairs. Each stack made one provider
generation per compared turn; both exposed zero tool schemas and made zero
tool calls. Median prompt size was 743.5 tokens PLAIN and 755.5 HADES.

The ordinary and follow-up slice therefore shows near-equal timing with a
small HADES context cost and no observed tool overhead. The pantry fallback
is fast and truthful for an unavailable source, but this fixture has no live
Grocy; it does not establish household task completion. HADES responses were
shorter overall (7,730 vs. 8,250 characters), but answers were not reviewed,
so this is not treated as a quality improvement.

## Limits

The cases are synthetic and cover only eight of the 55 corpus IDs. There was
no answer-quality or naturalness review, no owner preference, no live memory
or domain data, no Open WebUI/frontend, and no production parity check. This
run adds no new corpus case IDs and does not reduce the unreplayed count.

## Evidence

- Metrics-only artifact: [`hades-core-owner-conversation-v1-hermes0216-ollama0401-conversation-v1-three-repeat-20261008.json`](../benchmarks/hades-core-owner-conversation-v1-hermes0216-ollama0401-conversation-v1-three-repeat-20261008.json)
- Paired runner: [`benchmark-hades-owner-subset.py`](../scripts/benchmark-hades-owner-subset.py)
