# Memory comparison context correction — 2026-10-08

## Why the earlier result is disqualified

The earlier memory comparisons recorded `num_ctx: 65536` in Hermes provider
requests and benchmark configuration. That did not establish Ollama's effective
runtime context. A post-turn `/api/ps` check showed that the interactive model
was loaded at 4,096 tokens. Those runs remain useful for their memory-readiness
observations, but they are not evidence about latency at a matched 65,536-token
context. The core-09 v10 report is marked accordingly.

The benchmark now makes an un-overridden, 7,000-word probe through Ollama's
OpenAI-compatible chat endpoint and requires both more than 5,000 prompt tokens
to be processed and `/api/ps` to report 65,536 for the loaded model. It also
captures `/api/ps` at each provider response boundary, requires every
generation to request 65,536, and fails if a resident model reports a different
context. A successful `/api/ps` read that finds the model absent is recorded
separately; HADES background memory inference can evict the chat model before
the response boundary. PLAIN must remain resident at the requested context.

## Qualified control and result

Artifacts: [`HADES-first`](../benchmarks/hades-core-memory-effective-context-hades-first-20261008.json) and [`PLAIN-first`](../benchmarks/hades-core-memory-effective-context-plain-first-20261008.json)

The run used Hermes 0.21.5, Ollama 0.40.1, Qwen3.6:35b Q4_K_M digest
`a7eb95c5…`, and Hindsight 0.10.2 with its immutable image pin. The model was
launched on the loopback-only staging service with
`OLLAMA_CONTEXT_LENGTH=65536`. The exact OpenAI chat-path probe processed 7,010
prompt tokens and `/api/ps` reported a 65,536-token loaded context. Every
measured Hermes provider generation in both stacks requested 65,536. PLAIN
turns reported the model resident at 65,536 at every response boundary.

Two one-pair runs used fresh disposable Hindsight state, one in each order.
Across both orders they produced:

| Turn | PLAIN | HADES |
| --- | ---: | ---: |
| Ordinary chat, TTFT / total | 7.45–7.65 / 7.90–8.14 s | 1.89–2.05 / 2.28–2.47 s |
| Automatic retain, total | 3.31–3.40 s, 2 generations, 1 memory tool call | 1.74–1.78 s, 1 generation, no tool call |
| Immediate recall, TTFT / total | 1.74–1.83 / 1.95–2.06 s, marker found both | 27.77–28.36 / 28.33–28.88 s, marker missed both |
| Recall after Hindsight became idle, TTFT / total | not run | 9.85–10.14 / 9.91–10.37 s, marker found both |

HADES's chat model was observed at 65,536 for ordinary chat and the post-idle
recall in both orders. It was not resident at the provider response boundary
after automatic retain or during immediate recall. Hindsight drained after
42.6–45.7 seconds. Its Qwen3:14b background inference loaded at its
model-supported 40,960 context and used up to about 15.4 GB VRAM. This is
repeated evidence of a substantial memory-readiness and shared-runtime cost; it
does not prove which internal Hindsight stage causes the delay.

## Limits and next check

These are two synthetic pairs, one in each order. They are descriptive, not
stable latency estimates, quality ratings, or owner preference. The PLAIN
memory tool schema contributed 3,449 bytes per generation and raised its
ordinary prompt to 3,425–3,433 tokens, while HADES exposed no tools and used
714–717 prompt tokens. That tool-surface difference is part of this stack
configuration and should be evaluated alongside a separate PLAIN chat-only
profile.

Repeat the memory pair in reverse order and replay core-09 explicit memory
under the effective-context control. Keep HADES automatic memory readiness as
an open product defect; do not infer that faster settled recall makes the
immediate miss acceptable.
