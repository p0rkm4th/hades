# Recovery subset on Ollama 0.40.2 — 2026-10-09

Three order-balanced PLAIN STACK/HADES repeats used Hermes Agent 0.21.6
(`818c13be1dc4fd28987e1e881a9408224afd4535`), staged Ollama 0.40.2, and the
same Qwen3.6 35B Q4_K_M manifest digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c` at a
verified 65,536-token context. The recovery subset contains recipe correction,
missing workspace/source, unavailable inference/backup status, and topic
repair turns. Both arms had no domain, workspace, research, or operator tools;
this tests how they respond when the requested data/action is unavailable.
Sampling seed, temperature, output cap, benchmark runner, prompt sequence, and
local provider runtime were matched.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Content-bearing turns | 30/30 | 30/30 |
| Median TTFT | 1,160 ms | 1,136 ms |
| Median total latency | 1,920 ms | 2,058 ms |
| Model generations | 30 | 24 |
| Tool schemas/calls | 0 / 0 | 0 / 0 |
| Prompt tokens | 22,433 | 19,093 |
| Completion tokens | 1,206 | 1,792 |

HADES made six fewer model calls by answering `core-35` (read a project
configuration file without a workspace) and `core-37` (check backup status
without a configured source) directly, at median 15 ms and 23 ms respectively.
This is useful missing-capability behavior, not successful file or backup
access. Across the full subset, HADES's median response took 138 ms longer and
produced more completion tokens, so fewer generations did not make the whole
subset faster.

The slowest clear HADES recovery friction was `core-38` (summarize a status
result and distinguish missing fields from healthy values): median 2,351 ms
versus 1,516 ms for PLAIN STACK, with 152 HADES completion tokens versus 48.
The corrected recipe flow was close in median latency (`core-06`: 2,561 ms
HADES, 2,376 ms PLAIN; `core-40`: 2,331 ms HADES, 2,374 ms PLAIN), but HADES
produced more completion tokens in both. The generated text was not retained,
so correctness, naturalness, and whether that additional explanation helped
remain unreviewed.

This report is scoped synthetic evidence only: no production data/service was
used, no response text or owner preference was retained, and the subset has no
domain tools. The HADES overlay changed since the previous 0.40.1 recovery
run, so cross-run differences are not attributed to Ollama. Full sanitized
measurements are in
[`hades-core-owner-recovery-v1-hermes0216-ollama0402-3repeats-20261009.json`](../benchmarks/hades-core-owner-recovery-v1-hermes0216-ollama0402-3repeats-20261009.json).
