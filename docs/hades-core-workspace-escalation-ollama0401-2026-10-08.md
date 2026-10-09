# Workspace escalation on Ollama 0.40.1 (2026-10-08)

## Method

Ran four order-balanced synthetic multi-file diagnosis → explicit-fix pairs
through PLAIN and HADES. Both arms used Hermes 0.21.5, Ollama 0.40.1 from its
official Linux AMD64 archive (SHA-256
`a7aebbe3dd76ccf1351a56a3e57218ad486cb5f9a9938c58de87a37555e355d`), Qwen3.6
35B Q4_K_M (`a7eb95c5…`), the same loaded 65,536-token context, and an NVIDIA
RTX 3080 Ti. The rootless Docker 29.8.2 runtime used the same immutable sandbox
image in both arms; task containers had networking disabled. The synthetic
fixture was a multi-file geometry project. Repeat and provider-call seeds were
recorded by the harness.

The public artifact keeps only timings, counts, schema sizes, verification
status, and sanitized test-output markers. It contains no prompts, assistant
text, commands, file contents, tool arguments, transcripts, local paths, or
identity values.

## Results

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median diagnosis → fix time | 39.1 s | 50.3 s |
| Median provider generations | 9 | 7.5 |
| Median tool results | 11.5 | 10 |
| Diagnosis schemas / bytes | 8 / 12,590 | 2 / 3,662 |
| Action schemas / bytes | 8 / 12,590 | 5 / 9,575 |
| Median first provider content in diagnosis | 13.0 s | 8.5 s |
| Diagnosis changed the workspace before “Fix it.” | 2/4 | 0/4 |
| Action turn showed test-output markers | 2/4 | 3/4 |
| Independent fixture tests passed | 4/4 | 3/4 |

HADES took longer in all four paired runs; paired delays were 5.0–19.5 seconds
(median 12.7 seconds). Its smaller diagnosis catalog and read-only behavior
were useful on this task, and its first provider content arrived sooner. That
did not outweigh the slower completion. One HADES action made no expected source
change and failed independent verification. PLAIN changed the workspace during
diagnosis in two runs, before the user requested a fix; that is a sequencing
and authority failure despite passing final tests.

The 0.40.0 four-pair baseline also had slower HADES completion (49.2 s versus
41.1 s). These two small runs do not establish an Ollama-version effect. They
show that the HADES completion-time penalty persists on this fixture under
0.40.1. Keep the diagnosis boundary; investigate why the reduced catalog and
fewer median generations still do not make the full interaction faster.

This synthetic result is not a Scotty preference vote or a broad coding
qualification. No owner preference labels were collected.

Artifact: [sanitized four-pair measurements](../benchmarks/hades-core-workspace-escalation-ollama0401-v1.json).


## Current-source replay (2026-10-08)

A two-repeat replay used the same Hermes 0.21.5 source, Ollama 0.40.1, Qwen3.6 35B digest, loaded 65,536-token context, sandbox image, and counterbalanced sampling controls. The HADES source revision was `1c265d03a8b18c74545b20ae7aeb7c4e0bd1a00e`. Both stacks received the same workspace context hint. All four task runs changed only the intended source and passed independent tests.

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median diagnosis → fix time | 40.05 s | 49.99 s |
| Median model API calls per task | 9 | 7 |
| Median tool results per task | 10.5 | 9.5 |
| Diagnosis changed workspace before “Fix it.” | 1/2 | 0/2 |
| Independent fixture tests passed | 2/2 | 2/2 |

HADES remained about 9.94 seconds slower despite fewer median model calls and tool results. It returned its first diagnosis stream delta in about 0.3 seconds, while PLAIN took about 17.7–18.0 seconds; the overall action phase erased that progress. In HADES, the first fix-phase tool-call generations took about 15.75 and 15.09 seconds before producing tool-only calls. The available metrics do not establish why the model delayed those calls. The reduced HADES tool catalog and prompt size do not explain that action delay directly.

This replay strengthens the evidence that HADES preserves the diagnosis/action boundary on this fixture, while PLAIN violated it once. It does not establish owner preference, broad coding quality, Open WebUI persistence, Git commit behavior, or deployed gateway parity. It is a two-pair synthetic replay; do not infer a general latency or product-preference result from it.

Artifact: [sanitized current-source replay](../benchmarks/hades-core-workspace-escalation-current-ollama0401-20261008.json).


## Stream-onset and cache follow-up (current HADES source)

A two-repeat replay used the same geometry multi-file fixture, supported workspace context hint in both stacks, Hermes 0.21.5, Ollama 0.40.1, Qwen3.6 35B Q4_K_M (`a7eb95c5…`), and verified 65,536-token context. Temperature was 0.1, reasoning effort `none`, and the call seeds were paired. The run used the pinned rootless Docker 29.8.2 VFS sandbox image, with task containers on `network=none`. The HADES source revision was `2498f7a0a5a97402a3c957f3ca4c476e3b0b2364`. The provider proxy records only timing/count/byte aggregates for the first SSE event, content, recognized reasoning delta, and tool-call delta; no stream content is persisted.

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median diagnosis → fix time | 36.49 s | 45.85 s |
| Median model API calls per task | 8 | 6 |
| Median tool results per task | 7.5 | 8.5 |
| Independent tests / intended-source-only runs | 2/2 / 2/2 | 2/2 / 2/2 |
| Diagnosis changed workspace before “Fix it.” | 0/2 | 0/2 |

The first fix-phase tool-call generation is the clear latency split. PLAIN's first tool-call delta arrived in 1.66 and 1.78 seconds; Ollama reported 6,590/6,655 and 6,860/6,958 cached prompt tokens. HADES's corresponding tool-call deltas arrived in 15.21 and 15.50 seconds, with 0 cached tokens out of 6,269 and 6,406. Both stacks generated 61 completion tokens for those calls with the same paired seeds and reasoning setting. HADES's prompt was smaller and its workspace schema catalog was smaller (5 / 9,575 bytes versus 8 / 12,590 bytes), so raw prompt/schema volume does not explain the delay.

At the diagnosis-to-action boundary, PLAIN retained identical system text and nearly identical schema bytes; HADES changed its system text and almost the entire schema (29-byte common prefix). PLAIN then reused nearly all prompt tokens; HADES reused none. The first HADES fix request also emitted no recognized reasoning or visible content delta before the tool call. This establishes a strong association between lost prefix reuse and the delayed action call. It does not prove the cache miss accounts for all delay: Ollama does not expose reasoning internals on this route, and model-side prefill/scheduling remain possible contributors.

HADES finished the independent checks in both runs and neither stack mutated the fixture during diagnosis in this pass. HADES used fewer model generations but more tool results, and remained about 9.36 seconds slower. This is synthetic coding evidence, not owner preference.

The prior stable direct-schema experiment remains a no-go: it restored cached tokens but worsened end-to-end task time and increased invalid diagnosis calls. Do not simply expose the full mutable catalog at diagnosis. Next inspect whether Hermes 0.21.5 native deferred-tool search can keep a stable bridge schema across workspace phases while preserving the server-side authorization gate; if it adds too many search/tool rounds or weakens the read-only boundary, reject it.

Artifact: [sanitized stream and cache measurements](../benchmarks/hades-core-workspace-escalation-tool-delta-ollama0401-20261008.json).
