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
