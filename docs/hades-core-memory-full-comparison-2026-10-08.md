# Full synthetic memory comparison — 2026-10-08

Artifacts: [`HADES-first`](../benchmarks/hades-core-memory-effective-context-full-hades-first-20261008.json) and [`PLAIN-first`](../benchmarks/hades-core-memory-effective-context-full-plain-first-20261008.json)

## Control

Each artifact contains one fresh-volume pass; the two passes reverse stack
order. Both used Hermes 0.21.5, Ollama 0.40.1, Qwen3.6:35b Q4_K_M digest
`a7eb95c5…`, and Hindsight 0.10.2 with the same immutable image pin. Ollama
was launched on loopback with `OLLAMA_CONTEXT_LENGTH=65536`. Before each pass,
the exact OpenAI-compatible chat endpoint processed a 7,010-token probe without
a per-request context override, and `/api/ps` reported 65,536 for the loaded
chat model. Every Hermes generation requested 65,536; PLAIN runtime observations
reported 65,536 at each response boundary. HADES residency and eviction are
reported separately.

The corpus slice includes ordinary chat, automatic fact retention and recall,
core-09 explicit savings memory, favorite-fruit save/correction, implicit and
fresh-session recall, and five additional synthetic memory cases. The PLAIN arm
includes Hermes's native memory tool; HADES uses its deterministic memory route
and automatic Hindsight prefetch. No answer text was persisted. Marker checks
are descriptive, and no owner preference was assigned.

## Results

| Task | PLAIN | HADES |
| --- | --- | --- |
| Ordinary chat, total | 7.74–8.04 s; 3,433–3,437 prompt tokens; one 3,449-byte memory schema | 2.16–2.25 s; 714–717 prompt tokens; no tool schema |
| Automatic memory recall after a fresh retained fact | Marker found both orders in 1.94–2.07 s | Marker missed both orders in 28.28–29.23 s; chat model absent at response boundary |
| Explicit core-09 save and recall | Save 3.42 s with one memory tool call and two generations; recall 1.44–1.49 s | Save and recall completed deterministically in 0.04–0.10 s with zero model generations; expected marker found |
| Favorite-fruit save, correction, implicit recall, fresh recall | Correct markers; tool-backed writes use two generations | Correct markers through the deterministic route in 0.04–0.08 s, zero model generations |
| Five additional memory cases | Expected markers in 2/5 and 4/5, depending on order; final turns 0.36–2.53 s | Expected markers in 3/5 in both orders; model-backed final turns 20.6–31.1 s, deterministic cases 0.04–0.08 s |

Hindsight background work drained after 86.4–87.5 seconds. Its Qwen3:14b
inference loaded at 40,960 context and used about 15.4 GB VRAM. The HADES
automatic-recall prompt was not just slow: it missed a fact that PLAIN recalled
immediately, and the chat model was not resident at the response boundary.
This supports shared-runtime contention and pending-memory readiness as
concrete HADES costs. It does not isolate which Hindsight operation causes
which portion of the delay.

The explicit-memory comparison shows a clear HADES benefit for facts handled by
its synchronous deterministic route. The natural automatic-memory path remains
unqualified: both immediate recalls missed, and unrelated Hindsight work
continued for more than a minute. The additional five-case markers vary with
order and are too few to establish a reliable quality advantage.

## Interpretation and next work

This is a focused synthetic memory slice, not the complete 55-case owner corpus
and not Scotty dogfood. The large PLAIN ordinary-chat prompt includes the native
memory schema, so it should be followed by a separate PLAIN chat-only slice
before using that latency difference as a general ordinary-chat claim. The
post-idle PLAIN core-09 recall also varied sharply by order (1.36 s versus
15.33 s), another reason to treat these cells as diagnostic rather than stable
latency estimates.

The next repair targets natural personal-history recall while Hindsight writes
are active. Return a fast, truthful “still processing” response from the
existing authenticated subject-scoped readiness check instead of waiting up to
10 seconds and then queueing another model generation behind Hindsight. Keep
the safe memory boundary: never guess or imply that a missing fact was never
mentioned. Re-run both orders and the broader corpus after that change.
