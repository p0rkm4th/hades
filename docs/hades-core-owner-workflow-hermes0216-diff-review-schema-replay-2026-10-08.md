# Hermes 0.21.6 workspace diff-review replay — 2026-10-08

## Why this replay was run

The preceding two-pair replay showed that HADES had removed the broad homelab short circuit from the review turn, but one HADES attempt to call `terminal` during a read-only review was rejected as an invalid tool. Hermes had been shown five schemas while HADES authorized only `read_file` and `search_files`. HADES now exposes only the schemas allowed on read-only turns. The authenticated owner/rootless runtime contract passes with that matching catalog; household subjects still receive no workspace tools.

## Matched workflow result

Two order-balanced synthetic five-turn workflows (`core-25`, `core-26`, `core-28`, `core-31`) ran on committed HADES source `99e58598ce620458a0551de5787de8e7b9f92ef0`. Both arms used Hermes 0.21.6, Ollama 0.40.1, Qwen3.6:35b Q4_K_M with digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified 65,536-token context, and the same immutable rootless sandbox image. Model cache was unloaded and identically warmed before each arm. The sanitized record retains timing and tool metadata, not prompts or response text.

| Measure | PLAIN | HADES |
|---|---:|---:|
| Median task time | 55.35 s | 66.67 s |
| Median model API calls per task | 15.5 | 15.0 |
| Median tool results per task | 13.0 | 10.5 |
| Focused tests passed | 2/2 | 2/2 |
| Intended source only | 2/2 | 2/2 |
| Verified clean commits | 2/2 | 2/2 |
| Explicit diff-review tool calls | 2/2 | 0/2 |
| Diff inspected during commit turn | 0/2 | 2/2 |

The invalid-tool failure disappeared. However, HADES did not make a tool call in either explicit review turn; in one it read the changed file, and in the other it made no tool call. It inspected the diff later during commit in both runs. So the catalog mismatch is fixed, but the requested review sequence is still missing. HADES was 11.32 seconds slower at the median in this small two-pair sample. The comparison is synthetic and does not measure answer quality or owner preference.

Hermes 0.21.6 includes a hardened native `tools.working_diff.collect_working_diff` helper used by its `/diff` surfaces. A next bounded investigation is whether HADES can expose that read-only capability for the authenticated workspace while preserving the existing shell-denial boundary. Do not infer that this helper is already integrated into HADES.

## Status and artifacts

The workspace follow-up routing now reaches authorized tools and makes clean commits in 2/2. Read-only tool schemas match their authorization. The explicit diff-review UX is not qualified, the HADES arm remains slower in this sample, and owner preference remains unassigned. This is not deployed Open WebUI acceptance or broad coding usability qualification.

Sanitized measurements: [`hades-core-owner-workflow-hermes0216-99e58598.json`](../benchmarks/hades-core-owner-workflow-hermes0216-99e58598.json).
