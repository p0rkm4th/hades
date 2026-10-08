# PLAIN/HADES ordinary conversation comparison on Hermes 0.21.6

## Purpose and controls

This is a five-repeat regression subset for the staged Hermes 0.21.6 HADES
candidate. It compares PLAIN and HADES under the same candidate runtime; it is
not a comparison against the production Hermes version.

Both profiles used the exact Hermes source commit
`818c13be1dc4fd28987e1e881a9408224afd4535`, Ollama 0.40.1, Qwen3.6 35B
Q4_K_M digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`,
the RTX 3080 Ti Laptop GPU, and a verified loaded context of 65,536 tokens.
Temperature 1.0, seed 23, and a 512-token output cap were applied at the local
provider boundary. Profiles were warmed once and request order was alternated.
Inference was loopback-only with cloud disabled. The artifact stores aggregate
measurements only, not prompts, responses, or credentials.

The `core-4` subset has four ordinary owner-pattern cases and follow-ups: a
greeting, arithmetic, an explanation plus “Why?”, and an explanation plus
“Examples?”. Each profile completed 30 measured turns across five repeats.
Neither profile had API toolsets enabled; both emitted zero tool calls and zero
tool schemas.

## Results

| Measure | PLAIN | HADES |
| --- | ---: | ---: |
| Content-bearing turns | 30/30 | 30/30 |
| Provider generations | 30 | 30 |
| Median TTFT | 1,127 ms | 1,135 ms |
| Median total time | 1,919 ms | 1,677 ms |
| Median prompt tokens | 723.5 | 727.5 |
| Mean serialized input bytes | 3,100 | 3,067 |
| Tool schemas / calls | 0 / 0 | 0 / 0 |

The median paired HADES-minus-PLAIN deltas were **+2 ms TTFT** and **−2 ms
total time**; HADES was faster in 13/30 TTFT pairs and 15/30 total-time pairs.
The separate medians differ from the paired medians because per-turn and
repeat latency varies. This small subset shows no material ordinary-chat
latency or tool-catalog penalty from the HADES overlay on Hermes 0.21.6. HADES
responses totaled 4,770 characters versus 5,650 for PLAIN; without a quality
review, the shorter replies cannot be called an improvement.

## Limits and status

This is a synthetic chat-only subset, not the 50–60 task corpus. It does not
measure memory, domain tools, coding, Open WebUI, deployed parity, answer
quality, naturalness, or Scotty preference. It qualifies only the ordinary
conversation latency and tool-exposure checks for the staged 0.21.6 candidate.
Keep 0.21.6 as a staging candidate pending the broader corpus, focused action
coverage, and owner review.

Artifact: [sanitized five-repeat metrics](../benchmarks/hades-core-owner-conversation-hermes0216-ollama0401-core4-five-repeat-20261008.json).
