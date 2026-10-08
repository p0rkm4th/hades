# Current-source owner-pattern conversation replay (2026-10-08)

## Method

Replayed the existing `conversation-v1` synthetic subset through persistent,
isolated Hermes gateways: eight corpus case IDs, three repeats, 48 turns per
stack. PLAIN and HADES used the same Hermes Agent 0.21.5 source, Ollama 0.40.1,
Qwen3.6:35b Q4_K_M digest, RTX 3080 Ti, 65,536-token context verified loaded
by Ollama, temperature 1.0, seed 23, and 512-token output cap. Pair order was
counterbalanced by case and repeat. The proxy retained only aggregate request
sizes, counts, timings, and provider metadata. The benchmark did not persist
prompts or responses.

## Results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Content-bearing turns | 48/48 | 48/48 |
| Provider generations | 48 | 45 |
| Median TTFT, all turns | 1,063.7 ms | 1,066.2 ms |
| Median total, all turns | 1,601.9 ms | 1,453.6 ms |
| Median prompt tokens, all turns | 763.5 | 769 |
| Tool schemas / tool calls | 0 / 0 | 0 / 0 |

HADES made no provider request for the first `core-08` turn in each repeat
(`Help me check the pantry expiry list.`) because its fixture had no canonical
source. It returned a fast missing-source response, then answered the traceback
topic switch through the model. PLAIN generated on all six `core-08` turns.
Those three different execution paths are kept in the all-turn results and
called out separately; excluding all of `core-08` leaves 42 provider-backed
turns per stack, with median TTFT/total of 1,063.7/1,601.9 ms for PLAIN and
1,066.2/1,453.6 ms for HADES. Median prompt tokens on this slice were 763.5 and
760.5, respectively.

This replay shows no meaningful ordinary-chat TTFT difference in this small
synthetic sample. HADES's lower median total time is descriptive and does not
establish better answers: the runner did not collect answer quality,
naturalness, or owner preference. The missing-source fast path remains a
separate behavior requiring human review.

## Limits and status

This is not the complete 55-case corpus, a direct Scotty dogfood session, or a
production/Open WebUI parity test. Memory, domain tools, coding actions, and
operator work were not measured. No owner preference was assigned. The full
sanitized measurements are in
[`hades-core-owner-conversation-current-fa608b4-ollama0401-20261008.json`](../benchmarks/hades-core-owner-conversation-current-fa608b4-ollama0401-20261008.json).
