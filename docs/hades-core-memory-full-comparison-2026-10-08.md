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

## Pending-memory readiness follow-up

After the full comparison, natural personal-history questions during an active
subject-scoped retain were changed to return the existing truthful pending
response immediately. Two reverse-order, one-sample checks are in
[`HADES-first`](../benchmarks/hades-core-memory-readiness-fast-hades-first-20261008.json)
and [`PLAIN-first`](../benchmarks/hades-core-memory-readiness-fast-plain-first-20261008.json).
They used the same staged Hermes 0.21.5, Ollama 0.40.1, Qwen3.6:35b Q4_K_M,
65,536-context verification, and disposable Hindsight setup described above.

| Task | PLAIN | HADES |
| --- | --- | --- |
| Ordinary chat, total | 7.92–7.98 s; about 3,430 prompt tokens; one memory schema | 2.38–2.52 s; about 720 prompt tokens; no tool schema |
| Automatic recall while retain is pending | Marker found in 1.98–2.00 s, one model generation | Truthful pending response in 46–53 ms, zero model/tool calls; fact not yet returned |
| Recall after Hindsight became idle | — | Marker found in 10.19–10.27 s |

Hindsight drained after 49.9–54.8 seconds in these focused runs, compared with
86.4–87.5 seconds in the earlier full runs. The drain duration varied, so this
does not establish a stable improvement in Hindsight itself. It does establish
that HADES no longer waits through the pending window or queues a chat
generation behind it: the response is fast and honest, but PLAIN still provides
the requested fact sooner. This remains a synthetic, one-sample-per-order
diagnostic, not owner preference or a general latency claim.

The remaining product issue is timely natural recall during and after
background retention. Never guess or imply that a missing fact was never
mentioned. Improve readiness/recall without weakening the authenticated,
subject-scoped memory boundary, then repeat this slice and the broader corpus.

## Hindsight retention-mode probe

To test whether extraction work caused the long pending window, the same
effective-context harness was run in both stack orders with Hindsight's
`retain_mode=chunks`, first with observations enabled and then disabled. The
control was Hermes 0.21.5, Ollama 0.40.1, the same Qwen3.6:35b digest, and the
same immutable Hindsight v0.10.2 image. Each artifact is one fresh-volume pair;
these are candidate settings, not production configuration.

| Hindsight settings | Drain after HADES | HADES immediate recall | HADES after idle | HADES synthetic supplement markers |
| --- | --- | --- | --- | --- |
| `concise`, observations enabled (prior pending-response runs) | 49.9–54.8 s | Pending response, 46–53 ms; marker absent | 10.19–10.27 s | Not run |
| `chunks`, observations enabled | 16.2–24.3 s | Pending response, 47–48 ms; marker absent | 9.90–10.32 s | Not run |
| `chunks`, observations disabled | 2.06 s in both orders | Pending response, 56–80 ms; marker absent | 2.52–2.58 s | HADES found expected markers in 4/10 checks across five cases and both orders; PLAIN found 5/10 |

The chunks-only run still made several Hindsight LLM calls with observations
enabled, so chunks by itself did not remove model contention. Disabling
observations cut the pending window and settled recall latency, but the broader
synthetic memory checks were mixed: HADES missed both ordering repeats for
dietary restriction, place preference, and conversation continuity, while it
passed both corrected-response-preference checks. These markers are diagnostics,
not semantic ratings; however, this is enough to reject disabling observation
consolidation as a global replacement for the current memory profile. PLAIN's
marker results also varied by case and were not uniformly correct.

The same full slice was repeated with HADES recall expanded from observations
to all Hindsight result types (`observation`, `world`, and `experience`), in
both stack orders. The additional raw-memory types did not improve HADES's
synthetic supplement results: it again found the corrected response preference
in both runs and missed dietary restriction, place preference, and conversation
continuity in both. Automatic recall remained pending at the immediate turn,
with the expected marker absent. Artifacts:
[`HADES-first`](../benchmarks/hades-core-memory-chunks-no-observations-alltypes-hades-first-20261008.json)
and
[`PLAIN-first`](../benchmarks/hades-core-memory-chunks-no-observations-alltypes-plain-first-20261008.json).

I also isolated semantic extraction from observation consolidation in a
HADES-first full-slice probe: `retain_mode=concise`, observations disabled, and
all recall types enabled. The HADES arm still took 42.1 seconds to drain, with
seven Hindsight `/api/chat` generations across its measured memory work. Its
automatic fresh-fact response was pending at 63 ms, and the supplement results
again found only the two corrected-response-preference markers (2/5 categories);
the other three categories missed. This indicates that turning off observation
consolidation alone does not remove the expensive extraction path, and the
candidate did not recover the memory coverage lost with chunks. See the
[`HADES-first artifact`](../benchmarks/hades-core-memory-concise-no-observations-alltypes-hades-first-20261008.json).

The pinned Hindsight v0.10.2 API does support named per-retain extraction
strategies on individual memory items, configured through a bank's
`retain_strategies`; its Python `MemoryItem` schema includes `strategy`.
However, the installed Hermes Hindsight provider's retain-item builder does
not currently emit that field. This is a possible upstream capability to test
through a small adapter, not evidence that a selective policy is already
available. Strategy changes also do not by themselves disable bank-level
observation consolidation. See the [v0.10.2 strategy configuration]
(https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-docs/docs/developer/configuration.mdx)
and [item schema]
(https://github.com/vectorize-io/hindsight/blob/v0.10.2/hindsight-clients/python/hindsight_client_api/models/memory_item.py).

Keep the production retain/observation settings unchanged. The next candidate
should preserve useful semantic observations while avoiding an LLM-sized
background task on the interactive runtime, or define a more selective policy
for turns whose durable facts need immediate retention. Any such policy must
pass correction, stale-value, implicit recall, and fresh-session checks before
changing the pending-response behavior. No owner preference was assigned, and
neither candidate configuration is promoted.
