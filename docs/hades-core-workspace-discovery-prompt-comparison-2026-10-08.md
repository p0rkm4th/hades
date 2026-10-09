# HADES workspace discovery prompt comparison

Date: 2026-10-08  
Tested code revision: `75038dc0d88166a594c5fa0d348ebd3c244f93db`

## Method

Two runs of the same synthetic two-turn coding task compared clean Hermes
0.21.6 (PLAIN STACK) and the HADES overlay. Both used Ollama 0.40.1,
Qwen3.6:35b digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, a
verified 65,536-token context, reasoning disabled, and the same rootless Docker
29.8.2 daemon with immutable image
`docker.io/nikolaik/python-nodejs@sha256:339e5b5a859e23b7cbf0e6fb5376a29cfbc8115af58317cf1b5bc118a04e4fe1`.
The HADES prompt now tells the agent not to repeat `search_files` after it has
returned relevant paths. The benchmark artifact stores sanitized timings and
tool metadata, not prompt bodies, responses, or fixture file contents.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 31.50s | 36.93s |
| Median provider calls per task | 7 | 6 |
| Median tool results per task | 7.5 | 6 |
| Diagnosis workspace changes | 1/2 | 0/2 |
| Independent focused tests passed | 4/4 | 4/4 |

HADES was 5.44 seconds slower at the median while using fewer model calls and
tool results. It stayed read-only through both diagnosis turns. PLAIN STACK
modified the fixture during diagnosis once, so the task outcomes are not fully
equivalent; speed alone does not make that behavior preferable. The HADES
prompt change is retained as a small guidance improvement, but this sample
does not isolate its causal effect because there is no paired pre-change run
under the same valid image and environment.

## Limits

This is a two-repeat synthetic fixture through direct Hermes AIAgent instances,
not Open WebUI or deployed-gateway acceptance. It does not measure answer
quality, naturalness, household behavior, Git commits, or owner preference.
Treat latency as diagnostic evidence only. An earlier clean comparison artifact
contains a malformed sandbox image digest; its result remains historical and
should not be used as a reproducible baseline until rerun.

Artifact: [sanitized benchmark data](../benchmarks/hades-core-workspace-discovery-prompt-v1-20261008.json).
