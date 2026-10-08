# HADES core-09 explicit-memory replay v10 — 2026-10-08

> **Context qualification correction (2026-10-08):** The v10 pair artifacts
> below requested a 65,536-token context, but Ollama `/api/ps` recorded 4,096
> tokens for measured generations. Do not treat their latency figures as a
> 65k-context comparison. The effective-context control is now implemented and
> its separate automatic-memory replay is recorded in
> [`hades-core-memory-context-correction-2026-10-08.md`](hades-core-memory-context-correction-2026-10-08.md).
> Core-09 was replayed under the effective-context control in both stack orders;
> see the [`full synthetic memory comparison`](hades-core-memory-full-comparison-2026-10-08.md).

## Scope

This is a focused synthetic comparison of explicit memory recall. It is not
owner dogfood, a full corpus result, or a usability release qualification.

The matched stacks used Hermes Agent 0.21.5, Ollama 0.40.1, Qwen3.6:35b
Q4_K_M (`a7eb95c5…`), 65,536 context, temperature 0.1, and top-p 0.95. Each
counterbalanced invocation used a fresh disposable Hindsight database and the
same pinned Hindsight 0.10.2 image (`d1840062…`). Hindsight used Qwen3:14b
Q4_K_M for background work. Rootless bridge networking could not reach its
host-bound accounting proxy in this environment, so these runs used the
benchmark's loopback-only host-network mode.

Artifacts record only allowlisted timings, counts, statuses, and expected
marker booleans. They do not contain assistant answers or provider payloads.

## Results

| Turn | PLAIN, plain-first | PLAIN, HADES-first | HADES, plain-first | HADES, HADES-first |
| --- | ---: | ---: | ---: | ---: |
| Ordinary greeting total | 15.50 s | 15.39 s | 10.19 s | 10.16 s |
| Core-09 immediate recall | 1.42 s, 1 generation | 1.46 s, 1 generation | 48 ms, 0 generations | 57 ms, 0 generations |
| Core-09 recall after idle | 15.39 s, 1 generation | 1.37 s, 1 generation | 81 ms, 0 generations | 118 ms, 0 generations |
| Core-09 expected marker | present | present | present | present |

Each cell is one synthetic observation. PLAIN's large post-idle latency swing
shows an order effect; do not read it as a stable 15-second memory latency.
HADES' deterministic response used the already-visible tagged explicit fact,
including while unrelated canonical-bank retain work was active. It avoided a
second model generation and returned the expected `$3,000` marker in both
orders.

The separate synthetic automatic-memory probe still found its expected marker
in PLAIN (2/2) and not in HADES (0/2). HADES returned without a model generation
while fresh canonical-bank memory work was processing. This remains an
unresolved memory-readiness tax; the explicit-bank fix does not claim to repair
canonical automatic-memory recall.

Hindsight background work drained after the HADES arm in 87.96 seconds and
101.26 seconds. The verified barrier checked both banks and required empty
pending/processing operation sets and no active proxy requests. Those times are
background processing, not response-path latency. They show that a general
canonical-memory recall can remain unavailable much longer than the desired
simple-memory target while Hindsight processes and consolidates recent turns.

The greeting comparison was also descriptive only. Both stacks made one model
generation; HADES used 723 prompt tokens with no exposed tool schemas, while
PLAIN used about 3,465 prompt tokens and one memory schema. No answer-quality
rating or owner preference label was collected.

## HADES behavior change

The memory-processing guard used to run before deterministic explicit-memory
lookup. A pending automatic retain in `hades-owner` therefore hid a tagged,
synchronous fact already visible in `hades-owner-explicit`. HADES now checks
the authenticated subject's explicit memory first. If there is no verified
explicit match, the pending guard still blocks a model or canonical-memory
fallback from guessing while relevant work is active.

The change is in `hermes/sitecustomize.py`; the explicit-memory route contract
now verifies the ordering and the tagged `$3,000` fact case. Commit
`79473979` contains that behavior change.

The same follow-up inspection found the bank setup helper still recognized
only the older `items`/`id` bank-list response. Hindsight 0.10.2 returns
`banks`/`bank_id`; treating that valid response as empty could issue a needless
bank create/update on every direct memory turn. The helper now accepts both
known schemas, paginates and validates totals, and fails closed on unknown or
incomplete responses. The focused contract test covers current, legacy, and
unknown schemas.

## Barrier correction

The earlier HADES lifecycle reader expected `/v1/default/banks` to return
`items` containing `id`. Hindsight 0.10.2 returns `banks` containing
`bank_id`; the old parser therefore reported zero banks and falsely declared
idle. The reader now validates this response shape and paginates before
checking each bank. This matches the pinned upstream
[Hindsight 0.10.2 API implementation](https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-api-slim/hindsight_api/api/http.py).

Do not use earlier v3–v7 “after idle” readings as settled-recall evidence. The
v10 artifacts below supersede them for this synthetic case. A first rerun using
the corrected parser and rootless bridge failed closed during setup because
the container could not reach the accounting proxy; no measured comparison was
written from that run.

## Artifacts and provenance

- PLAIN-first: `benchmarks/hades-core09-explicit-recall-v10-plain-first.json`
- HADES-first: `benchmarks/hades-core09-explicit-recall-v10-hades-first.json`
- Source revision used by both: `ed09905502e0b5379dabc7766e7a290204b44001`
- Both artifacts classify themselves as synthetic, with preference unassigned.

## Remaining gates

- Repeat more than once per order before treating these timings as stable.
- Add a focused canonical automatic-memory readiness comparison with a valid
  barrier and preserve the fail-closed behavior while facts are processing.
- Review answer quality and preference with Scotty during natural dogfood.
- The full 55-case corpus, 36 unreplayed cases, owner preference labels, and
  direct Scotty dogfood remain incomplete.
