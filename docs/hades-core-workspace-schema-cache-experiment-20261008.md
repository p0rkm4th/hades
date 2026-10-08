# Workspace schema cache experiment — 2026-10-08

## Question

Does keeping HADES' workspace tool schema unchanged between diagnosis and an explicit action improve chat-to-work performance enough to justify the extra model-visible schemas during diagnosis?

## Method

Two order-balanced repeats per run used Hermes 0.21.6, Ollama 0.40.1, Qwen3.6 35B digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, 65,536 context, reasoning disabled, and the same rootless Docker 29.8.2 daemon and immutable sandbox image. Each synthetic coding task asked “Why is this Python test failing?” and then “Fix it.” Both arms used the same project fixture and workspace hint. Independent tests and diff checks followed each task.

The **dynamic** run exposed two schemas during diagnosis and five during action. The **stable** run exposed the same five workspace schemas throughout the coding turn, while Hermes' `valid_tool_names` restricted diagnosis to `read_file` and `search_files`. The runtime test also submitted a synthetic `patch` call during diagnosis to Hermes' native validator; it returned an unknown-tool result and did not dispatch the call.

The runs were separate two-repeat samples, not a same-process, randomized strategy trial. They are useful diagnostic evidence, not a definitive performance estimate. Per-turn elapsed timing was corrected in the benchmark harness before these runs.

## Results

| Measure | Dynamic schemas | Stable schemas |
|---|---:|---:|
| HADES median diagnosis-to-fix task | 41.85s | 34.82s |
| HADES median diagnosis phase | 21.93s | 25.83s |
| HADES first action request, median | 14.86s | 4.07s |
| Action request cached prompt tokens | 0 in both repeats | 4996 median |
| Diagnosis schemas exposed | 2 (3662 bytes) | 5 (10529 bytes) |
| HADES diagnosis workspace edits | 0/2 | 0/2 |
| HADES independent tests passed | 2/2 | 2/2 |

In the stable-schema run, the first action generation reused about 5,000 prompt tokens and took about four seconds, compared with about fifteen seconds and zero cached tokens in the dynamic run. The diagnosis phase cost about four seconds more, while the complete diagnosis-plus-fix task was about seven seconds faster in these samples. No HADES diagnosis edit occurred in either run. PLAIN STACK edited during diagnosis in one dynamic and both stable repeats, despite the prompt asking only why the test failed.

## Decision

Keep stable workspace schemas for HADES coding conversations, with read-only `valid_tool_names` enforced until the owner explicitly asks for an action. The action-turn cache gain outweighed the diagnosis cost in this common escalation pattern, and the native validator plus focused runtime test preserve the execution boundary.

This does not establish that five schemas are preferable for a standalone code explanation. The overall task timing also varies with local model cache state. Keep the experiment visible in future owner-corpus scoring, including cases that stop after diagnosis.

## Artifacts and limits

- Dynamic sanitized run: [`hades-core-workspace-schema-dynamic-v1.json`](../benchmarks/hades-core-workspace-schema-dynamic-v1.json)
- Stable sanitized run: [`hades-core-workspace-schema-stable-v1.json`](../benchmarks/hades-core-workspace-schema-stable-v1.json)
- Both artifacts record exact tested overlay, policy-module, and benchmark-script hashes. Provider bodies, prompts, tool arguments, and file contents are not retained.
- Two repeats per strategy; one synthetic geometry fixture; direct AIAgent path; no Open WebUI, broad task corpus, or owner preference labels.
