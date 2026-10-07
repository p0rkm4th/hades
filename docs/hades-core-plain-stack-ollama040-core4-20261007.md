# PLAIN STACK comparison on Ollama 0.40.0 — 2026-10-07

Ran three counterbalanced repeats of the seeded `core-4` conversation subset
through persistent Hermes 0.21.5 gateways. Both arms used the same staged
Ollama 0.40.0 process, Qwen3.6 35B Q4_K_M model digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, 65,536
loaded context, disabled reasoning, and a verified 512-token output cap.
Ollama was bound to `127.0.0.1:11445` with cloud disabled. Each profile used
Hermes' custom local OpenAI-compatible provider and empty API toolsets; PLAIN
had no HADES overlay. The HADES arm used the matching HADES overlay and its
ordinary-chat routing. Requests were serialized and arm order alternated.

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Successful content turns | 18/18 | 18/18 |
| Median TTFT | 1,180 ms | 1,202 ms |
| Median total latency | 1,629 ms | 1,795 ms |
| Provider generations | 18 | 18 |
| Tool schemas exposed / calls emitted | 0 / 0 | 0 / 0 |
| Median input tokens | 755.5 | 749.5 |
| System-message bytes | 3,041 | 3,008 |

HADES' medians were 22 ms slower to first content and 166 ms slower to
completion in this sample. Both met the ordinary-chat targets. The request
capture found no extra generation, tool call, or tool-schema cost. These
measurements do not isolate middleware time from model-output variation and do
not establish an owner preference; the answer text was not retained for human
quality review. The sample supports a small ordinary-chat cost on this path,
not a usability qualification.

The metrics-only artifact is
[`hades-core-owner-subset-hermes0215-ollama040-core4-v1.json`](../benchmarks/hades-core-owner-subset-hermes0215-ollama040-core4-v1.json).
Its run used local campaign commit `59a06fda3ff09331a8f542d508918f4ea0f8fadf`.
The exercised overlay and runner files are byte-identical to the sanitized
review snapshot at `66a345165050769497a52d1039ad3de644a62e72`; only campaign
notes and a stale test assertion differ between those trees. The artifact's
Hermes path was replaced with the release commit identifier before publication.

The staged Ollama process was stopped after the run and loopback port 11445
was verified closed. No production state changed. Memory, household/domain
tools, coding, computer use, Open WebUI, and direct Scotty preference remain
unmeasured by this comparison.
