# Conversation and follow-up comparison on Ollama 0.40.2 — 2026-10-09

## Method

Three alternating-order repeats covered eight synthetic owner-pattern cases
with 48 turns per stack. Both stacks used Hermes 0.21.6 commit
`818c13be1dc4fd28987e1e881a9408224afd4535`, Ollama 0.40.2, Qwen3.6 35B
Q4_K_M digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`,
65,536 verified loaded context, the same RTX 3080 Ti Laptop GPU, temperature
1.0, seed 23, and 512-token output cap. The gateway runner retained request
metrics only, not prompts or answer text.

All 96 turns returned content. Both stacks made 48 provider generations,
exposed zero tool schemas, and emitted zero tool calls.

## Results

Median TTFT was 1,084 ms PLAIN and 1,075 ms HADES. Median total latency was
1,615 ms PLAIN and 1,706 ms HADES. Median prompt size was 748 tokens PLAIN
and 752 HADES. HADES returned 7,757 answer characters versus 7,355 for PLAIN;
without response-text review, length is not a quality signal.

This run shows similar first-token timing and about 91 ms higher HADES median
completion time on this narrow chat-only subset. It does not establish whether
that difference is perceptible or whether either assistant's answers are
better.

## Limits

The cases are synthetic and cover only eight of the 55 corpus IDs. No answer
quality, naturalness, or owner preference was collected. There was no live
memory or domain data, Open WebUI/frontend, coding/action workflow, or
production parity check. The measured HADES system instructions are part of
the stack comparison. This does not qualify the full corpus or usability.

## Evidence

- Metrics-only artifact: [`hades-core-owner-conversation-v1-hermes0216-ollama0402-3repeats-20261009.json`](../benchmarks/hades-core-owner-conversation-v1-hermes0216-ollama0402-3repeats-20261009.json)
- Paired runner: [`benchmark-hades-owner-subset.py`](../scripts/benchmark-hades-owner-subset.py)
