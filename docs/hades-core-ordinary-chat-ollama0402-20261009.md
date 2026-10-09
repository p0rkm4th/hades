# Ordinary conversation comparison on Ollama 0.40.2 — 2026-10-09

Five order-balanced PLAIN STACK/HADES repeats used Hermes Agent 0.21.6
(`818c13be1dc4fd28987e1e881a9408224afd4535`), staged Ollama 0.40.2, and
`qwen3.6:35b` Q4_K_M manifest digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`. Both
arms used the same local Ollama process, GPU, 65,536-token context, sampling
seed 23, temperature 1, 512-token output cap, prompts, and persistent gateway
per arm. The provider proxy applied and verified generation controls on every
request. A warmup ran for each stack before measurement. The HADES arm loaded
the overlay from source revision `28f58c1dfb0853e993876c4bf9d0437a559a59ed`.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Content-bearing turns | 30/30 | 30/30 |
| Median TTFT | 1,033 ms | 1,049 ms |
| Median total latency | 1,989 ms | 1,752 ms |
| Model generations | 30 | 30 |
| Tool schemas exposed | 0 | 0 |
| Tool calls | 0 | 0 |
| Prompt tokens | 23,050 | 22,685 |
| Completion tokens | 1,720 | 985 |
| Mean captured request bytes/generation | 3,169 | 3,093 |

Both stacks met the ordinary-chat median latency targets. HADES's median TTFT
was 16 ms slower; its median completion was 237 ms faster, alongside 43% fewer
completion tokens. Since response text is intentionally not retained, this
does not show whether the shorter HADES answers were more useful, too terse, or
preferred. No human quality or owner-preference review was collected.

The comparison uses the same benchmark runner as the 0.40.1 five-repeat
comparison, verified by identical runner SHA-256
`1df3621ed516cd64a9fca8816557d9be9b6b066d47f033831c5c1306e601c0be`. The
HADES overlay source revision changed between those runs, so this report
compares PLAIN STACK against HADES on 0.40.2 only; it does not attribute
cross-run differences to the Ollama runtime upgrade.

The sanitized measurements are in
[`hades-core-owner-conversation-hermes0216-ollama0402-core4-five-repeat-20261009.json`](../benchmarks/hades-core-owner-conversation-hermes0216-ollama0402-core4-five-repeat-20261009.json).
The initial 0.40.2 load at 4,096 context was rejected by the harness before
corpus turns ran; the accepted run set and verified 65,536 context explicitly.

This is a synthetic ordinary-chat subset, not a full corpus or owner
qualification. It does not cover memory, domain tools, Open WebUI, coding,
action escalation, or production runtime parity.
