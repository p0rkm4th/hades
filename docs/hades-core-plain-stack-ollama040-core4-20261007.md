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

## Counterbalanced reset replay

A further three-repeat replay used the same release, model digest, GPU,
65,536-token Ollama server context, 512-token output cap, and empty API toolsets.
This runner now aborts unless Ollama's loaded context matches the requested
context; the earlier startup-default behavior had silently loaded 4,096 tokens
despite sending `num_ctx=65536` in the request. The corrected run captured
18/18 content-bearing turns per stack, 18 provider generations per stack, and
zero schemas/calls for both.

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median TTFT | 1,170 ms | 1,169 ms |
| Median total latency | 1,457 ms | 1,603 ms |
| Median input tokens | 719.5 | 722.5 |
| Mean serialized message bytes | 3,113 | 3,095 |

The paired medians are close on this four-case ordinary-chat slice. HADES was
1 ms faster to first content and 145 ms slower to completion; the difference
is within observed generation variation and does not establish a product
preference. No response text was retained for quality review. The artifact
[`hades-core-owner-subset-pair-v3-20261007.json`](../benchmarks/hades-core-owner-subset-pair-v3-20261007.json)
contains metric-only records and passed the public redaction check. The
benchmark control now rejects a mismatched loaded context, and the public
metric serializer renames count/role fields that the conservative scanner
would otherwise mistake for raw content.

## Expanded conversation replay

On 2026-10-07, the seeded `conversation-v1` subset ran for three repeats
through the isolated Ollama 0.40.0 endpoint on `127.0.0.1:11435`. Both arms
used Hermes 0.21.5 source `f97608f178d1ffeca59860195ab7da295f7c8e5f`, the same
Qwen3.6 35B Q4_K_M digest above, verified 65,536-token loaded context,
disabled reasoning, and a provider-enforced 512-token output cap. The request
order alternated by case and repeat. API toolsets were empty in both profiles.

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Content-bearing turns | 48/48 | 48/48 |
| Median TTFT | 1,025 ms | 1,054 ms |
| Median total latency | 1,792 ms | 1,545 ms |
| Provider generations | 48 | 46 |
| Tool schemas exposed / calls emitted | 0 / 0 | 0 / 0 |
| Median input tokens | 743.5 | 754 |

On all three repeats of `core-08`, HADES returned content on the pantry to
traceback topic-switch turn without a provider request; PLAIN used one. The
artifact retains that count but no response text, so it does not establish
whether either response was more useful or natural. Across this small synthetic
subset HADES had 29 ms higher median TTFT and 247 ms lower median total time.
That aggregate is sensitive to output length and the direct HADES responses;
it is not a general latency win or an owner-preference result. No owner review
or task-quality grading was collected.

The metrics-only artifact
[`hades-core-owner-conversation-v1-paired-20261007.json`](../benchmarks/hades-core-owner-conversation-v1-paired-20261007.json)
records the exact Hermes/model/runtime versions and confirms the loaded
context. It passed the public benchmark-redaction and owner-subset artifact
checks. This remains synthetic chat-only evidence; memory, tools, coding,
Open WebUI, production parity, and direct Scotty dogfood are still unqualified.
