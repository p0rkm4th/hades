# Current-source Grocy read comparison (2026-10-08)

## Method

Ran three counterbalanced repeats for each of three read scenarios against the
same authenticated loopback synthetic Grocy fixture. The six source-health
conditions were an available fixture and a simulated HTTP 503. PLAIN used one
allowlisted native Hermes MCP read tool; HADES used its direct canonical Grocy
read path. Both used Hermes 0.21.5, Ollama 0.40.1, Qwen3.6:35b Q4_K_M digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, and
65,536 effective context verified by the runner. All fixture calls were
authenticated GETs; no writes were made. The per-turn public artifact omits all
prompt and answer strings and retains only timings, counts, and outcome labels.

## Results

| Scenario | Source | PLAIN median | PLAIN generations | HADES median | HADES generations |
|---|---|---:|---:|---:|---:|
| Expiry read | Available | 5.63 s | 3 | 0.040 s | 0 |
| Expiry plus saved recipe use | Available | 7.41 s | 3–4 | 0.041 s | 0 |
| Named recipe feasibility | Available | 7.54 s | 4 | 0.051 s | 0 |
| Expiry read | HTTP 503 | 6.25 s | 3, 3, 6 | 0.037 s | 0 |
| Expiry plus saved recipe use | HTTP 503 | 9.64 s | 4–6 | 0.040 s | 0 |
| Named recipe feasibility | HTTP 503 | 6.61 s | 3, 3, 6 | 0.048 s | 0 |

Manual source checks on the synthetic fixture found HADES correctly reported the
missing egg for the saved pancake recipe in all three available feasibility
runs. PLAIN was fully correct in one of three; two answers contradicted the
fixture shortage. Both stacks identified the available expiry dates and the
saved recipe that uses the expiring eggs. On all nine unavailable-source HADES
turns, it said the data was unavailable and that it made no change. PLAIN
ultimately reported the 503 in all nine, but made repeated model/tool attempts;
one answer invented an endpoint and advised sending a key there. The fixture
contained only a synthetic key, and no request was sent to that invented URL.

This is strong task-specific evidence that HADES direct canonical reads add
visible value here: substantially faster, fewer unnecessary model/tool
round-trips, consistent recipe feasibility, and safer failure wording. It does
not establish Scotty's preference or general quality. The manual source review
was not performed by the owner. Preserve the bounded read path on this evidence;
continue to qualify it with owner dogfood and production source provenance.

## Limits

One synthetic fixture, three repeats per scenario, one model/runtime/hardware
configuration. No real household data, mutations, owner review, or deployed
parity was involved. Full sanitized measurements are in
[`hades-core-grocy-read-current-ollama0401-20261008.json`](../benchmarks/hades-core-grocy-read-current-ollama0401-20261008.json).
