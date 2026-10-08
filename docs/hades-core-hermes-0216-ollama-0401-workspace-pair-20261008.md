# Hermes 0.21.6 / Ollama 0.40.1 workspace comparison (2026-10-08)

## Setup

Two order-balanced synthetic multi-file coding escalation tasks compared clean Hermes Agent 0.21.6 with the same Hermes version plus the current HADES `sitecustomize` overlay. Both used Ollama 0.40.1, the same Qwen3.6 35B model digest and 65,536-token context, reasoning disabled, and the same rootless Docker sandbox image with networking disabled. This measures one narrow workspace path, not general chat.

## Result

| Measure | Plain Hermes | HADES overlay |
|---|---:|---:|
| Median task elapsed | 32.2 s | 56.3 s |
| Median provider calls per task | 8.5 | 9.5 |
| Median tool results per task | 11 | 11 |
| Independent fixture tests and diff checks | 2/2 | 2/2 |
| Diagnosis invalid tool results | 0 | 2 |
| Diagnosis turns changing workspace | 2 | 0 |

On this small sample, HADES was about 75% slower at the full task level while producing the same median number of tool results. The result is a strong reason to inspect overlay overhead and diagnosis behavior, not a general user preference finding.

The benchmark-only host workspace verification mapping passed native verification in one HADES repeat and left the other `unverified`; this does not qualify it for production.

## Limits

This is two runs per arm on one synthetic multi-file discount bug fixture. Generation variance is material. The direct Hermes route excludes Open WebUI persistence and deployed gateway authentication. No human reviewed answer quality or naturalness, and this does not qualify long coding tasks, Git commit behavior, ordinary chat, or Scotty's preference. The benchmark artifact contains only aggregate and per-run metadata, with no prompts, responses, tool arguments, or filesystem paths.

See [`benchmark artifact`](../benchmarks/hades-core-hermes-0216-ollama-0401-workspace-pair-20261008.json) for the sanitized measurements.
