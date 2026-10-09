# Agentic explanation-to-fix comparison on Ollama 0.40.2

This two-pair comparison replayed the corpus's natural sequence: “Why is this
Python test failing?” followed by “Fix it.” It used Hermes 0.21.6, Ollama
0.40.2, Qwen3.6 35B Q4_K_M digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, verified
65,536-token context, the same multifile synthetic project, rootless Docker
29.8.2 and an immutable network-disabled sandbox. Both stacks received the
same supported `/workspace` environment hint. Full sanitized measurements are
in [`hades-core-owner-agentic-core43-44-hermes0216-ollama0402-rootless-two-repeat-20261009.json`](../benchmarks/hades-core-owner-agentic-core43-44-hermes0216-ollama0402-rootless-two-repeat-20261009.json).

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 37.80 s | 47.33 s |
| Median model API calls | 7 | 6 |
| Median tool results | 7.5 | 8.5 |
| Workspace changed during explanation turn | 2/2 | 0/2 |
| Patch and focused test after “Fix it.” | 0/2 | 2/2 |
| Independent test and diff checks passed | 2/2 | 2/2 |
| Only expected source changed | 2/2 | 2/2 |

PLAIN changed the project while answering the diagnosis-only request in both
runs; after the explicit “Fix it” follow-up, it made no workspace calls. HADES
left the project unchanged while explaining, then patched and tested after the
follow-up in both runs. Thus the shorter PLAIN time is not a fair measure of
the requested two-step experience: the stacks did different work, and PLAIN
acted before the user asked it to.

HADES did take about 9.5 seconds longer end to end and returned one more median
tool result. Its diagnosis turn used one file search followed by five or six
file reads. The artifact intentionally omits path values, so it cannot show
whether each read was necessary or duplicated. This is a concrete profiling
target, but not yet evidence to remove reads or weaken the authorization
boundary.

## Qualification limits

This supports HADES's explanation-then-action boundary for one synthetic
coding task. It does not qualify generated answer quality, broader coding,
Open WebUI persistence, deployed authentication, remote commits, or owner
preference. No answer text was retained. Direct Scotty dogfood remains
necessary to decide whether the slower but correctly sequenced interaction is
preferable and whether diagnosis can use fewer reads.
