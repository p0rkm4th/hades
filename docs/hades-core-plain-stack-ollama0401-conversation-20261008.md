# PLAIN/HADES ordinary conversation comparison on Ollama 0.40.0 and 0.40.1

## Purpose

Qualify the newly staged Ollama 0.40.1 runtime against the measured 0.40.0
control on ordinary chat and follow-up turns, using the same current HADES code
and a tighter sampling contract than earlier runs.

## Method

Both runs used Hermes Agent 0.21.5 at source
`f97608f178d1ffeca59860195ab7da295f7c8e5f`, HADES revision
`8e94ca331c187f0b7375b3ff57ff7445a9ad6e76`, the same Qwen3.6 35B Q4_K_M model
digest `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, and
the same NVIDIA RTX 3080 Ti Laptop GPU. Both reported the requested and loaded
65,536-token context. The harness applied temperature 1.0, seed 23, and a
512-token output cap at the loopback provider boundary on every request.

The `conversation-v1` subset contains eight synthetic owner-pattern cases,
three counterbalanced repeats, and 48 turns per stack. It exposes no domain,
workspace, research, or operator tools. Both stacks returned content in all 48
turns and emitted no model tool calls. In HADES, three `core-08` pantry turns
returned the established missing-source response without a model generation;
the equivalent PLAIN turns used the model. Following prior methodology, the
ordinary-chat timing comparison below excludes all six turns of `core-08` per
stack, leaving 42 model turns per stack.

Each profile had one warmup before measurement. This does not include model
cold-start, Open WebUI frontend, or production gateway latency.

## Results

| Runtime | Stack | Median TTFT | Median total | Median prompt tokens |
| --- | --- | ---: | ---: | ---: |
| Ollama 0.40.0 | PLAIN | 979 ms | 1,730 ms | 739.5 |
| Ollama 0.40.0 | HADES | 955 ms | 1,421 ms | 742.5 |
| Ollama 0.40.1 | PLAIN | 1,053 ms | 1,437 ms | 743.5 |
| Ollama 0.40.1 | HADES | 1,021 ms | 1,453 ms | 745.5 |

Within each runtime, paired median HADES-minus-PLAIN deltas were:

- Ollama 0.40.0: TTFT −71 ms, total −86 ms; HADES was faster on 31/42 TTFT
  pairs and 29/42 total-time pairs.
- Ollama 0.40.1: TTFT −15 ms, total −25 ms; HADES was faster on 25/42 TTFT
  pairs and 22/42 total-time pairs.

This subset shows no large ordinary-chat latency penalty from HADES middleware
on either runtime; paired median differences are small relative to task
duration. It does not measure answer quality, naturalness, or owner preference.
Across runtime versions, output-token totals differed despite the fixed
sampling controls, so total-time differences are not a clean runtime
performance estimate. TTFT shifted by tens of milliseconds and should be
treated as descriptive for these three repeats, not as evidence that 0.40.1 is
faster or slower in general.

## Decision

The current evidence supports keeping 0.40.0 as the established comparison
control and 0.40.1 as a staging candidate. The 0.40.1 ordinary-chat subset
passed the content, context, tool-exposure, and generation-count checks, but it
does not qualify production promotion or satisfy the wider 55-case owner
corpus. No answer-quality review or direct Scotty dogfood was collected.

Artifacts:

- [Ollama 0.40.0 seeded run](../benchmarks/hades-core-owner-conversation-ollama0400-seeded-20261008.json)
- [Ollama 0.40.1 seeded run](../benchmarks/hades-core-owner-conversation-ollama0401-seeded-20261008.json)

## Five-repeat HADES-versus-PLAIN replay

A follow-up at HADES source `ff9f0543b002a771fdb328072487d1475d780195`
repeated the same eight conversation cases five times on Ollama 0.40.1,
alternating stack order. It used the same Hermes 0.21.5 source, Qwen3.6:35b
digest, 65,536 loaded context, temperature 1.0, seed 23, and 512-token
generation cap. The artifact records 80 turns per stack; both produced
content on all turns and neither emitted model tool calls. PLAIN made 80
provider generations and HADES made 75; HADES handled the five first turns of
the missing-source pantry interruption without a model call. No domain tools
or data were available in either profile.

Excluding the ten `core-08` turns from each stack leaves 70 paired
model-mediated turns. Median TTFT was 1,060.9 ms for PLAIN and 1,092.2 ms for
HADES; the median paired HADES-minus-PLAIN delta was −58.2 ms (HADES lower in
44/70 pairs). Median total time was 1,867.6 ms for PLAIN and 1,556.0 ms for
HADES; the paired median delta was −162.2 ms (HADES lower in 53/70 pairs).
The separate medians and median paired deltas differ because task and repeat
latencies vary; both are retained. Tool schema count remained zero. Median
prompt size was 739.5 tokens for PLAIN and 742.5 for HADES.

HADES responses were shorter: median completion length was 34 tokens versus
41 for PLAIN on model-mediated turns; over all 80 turns, answer-character
totals were 11,562 for HADES and 16,585 for PLAIN. Shorter output may be a
conciseness benefit or missing explanation; this benchmark does not score
answer quality or naturalness. Thus the replay supports that current HADES
middleware does not add a material ordinary-chat latency or tool-catalog tax
in this warmed synthetic subset. It does not establish an owner preference,
answer-quality advantage, cold-start performance, or Open WebUI/deployed
parity.

Artifact: [five-repeat Ollama 0.40.1 PLAIN/HADES run](../benchmarks/hades-core-owner-conversation-ollama0401-seeded-repeat05-20261008.json).
