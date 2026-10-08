# Workspace prompt stability experiment — 2026-10-07

## Question

Does replacing HADES' phase-specific workspace instructions with one compact instruction shared across diagnosis and action improve the workspace escalation path or reduce prompt/cache overhead?

## Method

Two repeats per condition compared PLAIN STACK and HADES on the same synthetic multi-file geometry diagnosis followed by the natural follow-up “Fix it.” Both used Hermes 0.21.5, Ollama 0.40.0, the same Qwen3.6 35B Q4_K_M model, 65,536-token context, hardware, rootless Docker sandbox, workspace hint, and native verify-on-stop ledger. HADES retained dynamic schemas and its read-only diagnosis gate. The candidate was a shared 689-character instruction; the baseline used 666 characters for diagnosis and 1,025 for action.

This was a diagnostic sample, not an owner usability qualification. The candidate block followed the baseline block, so cross-condition cache/order effects remain possible. The full per-run sanitized measurements are in [the JSON artifact](../benchmarks/hades-core-workspace-prompt-stability-multifile-20261007.json); raw prompts, responses, arguments, and local paths are not published.

## Results

| Condition | PLAIN median task time | HADES median task time | PLAIN model calls / tool results | HADES model calls / tool results | Verified final tasks |
|---|---:|---:|---:|---:|---:|
| Phase-specific prompt | 27.3 s | 45.0 s | 8.5 / 8.5 | 6 / 8 | 4/4 |
| Shared compact prompt | 33.6 s | 48.2 s | 10 / 19 | 8.5 / 11 | 3/4 |

The HADES diagnosis remained non-mutating in both baseline runs and both candidate runs. In the candidate runs, HADES made three invalid `terminal` tool attempts and one action run did not complete the fix. The measured HADES diagnosis prompt was about 4,038 tokens at baseline and 4,041 with the candidate; first-generation cached prompt tokens remained zero in both conditions. The compact text therefore did not demonstrate a prompt/cache or latency benefit in this sample, and task/tool outcomes were worse in the candidate sample.

## Decision

Reject the shared compact prompt as a product change. Keep the phase-specific prompt and existing safety gates. Do not infer a causal latency regression from two repeats; the evidence supports only that this candidate showed no demonstrated benefit and had worse task/call outcomes in this small sample.

Next, isolate the HADES first-generation cache miss and workspace action behavior with balanced repeats before changing prompt policy. Then compare on a broader, realistic owner corpus and collect Scotty's preference; this synthetic result does not establish that PLAIN STACK is preferred overall.
