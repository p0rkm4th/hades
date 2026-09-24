# HADES Decision Plane / System-One Alpha

Status: **Engineering acceptance complete — no candidate promoted; production
steering and live candidate shadowing deferred**.

## Purpose

The Decision Plane is a fast semantic recommendation layer beneath Hermes
Agent. It can classify intent, capability family, ambiguity, reasoning tier,
retrieval need, and tool family. It cannot authenticate, authorize, execute,
confirm, revoke, retry a mutation, or reconcile canonical state.

The security equation is:

```text
effective capability = policy authorization ∩ decision recommendation
```

The Decision Plane never uses a union with policy. A backend failure returns the
CURRENT routing result and records a safe fallback; it never exposes more
tools.

## Versioned contract

The first internal contract is `decision-api/v1`, implemented in:

```text
hades_decision/api.py
hades_decision/current.py
```

`DecisionInput` contains only a bounded request, bounded recent context,
coarse actor class, input kind, and optional capability-family context. The
actor class is not an identity assertion. `DecisionResult` contains typed
`DecisionValue` records with an explicit `score_kind`; CURRENT uses
`heuristic_score`, not probability.

The API has no tool or execution method by design.

## CURRENT control

`CurrentRulesBackend` reuses the maintained HADES routing signals from
`hermes/sitecustomize.py` and exposes them through the same contract. It is a
semantic control projection, not a replacement production router. This avoids
comparing a candidate against an invented regex strawman while making the
current signals measurable.

Initial sanitized corpus result, 31 cases, after adding conservative
server/voice/household vocabulary to the CURRENT projection:

```text
 intent accuracy:             24 / 29 = 82.8%
 capability-family accuracy:  24 / 29 = 82.8%
 tool-family accuracy:        19 / 24 = 79.2%
 clarification accuracy:      26 / 31 = 83.9%
local latency p50:           ~0.02 ms
local latency p95:           ~0.03 ms
```

The post-Alpha CURRENT follow-up on commit `d7dbfd0` adds bounded,
domain-generic transcription/shorthand normalization and correction/ambiguity
signals. On the same 31-case corpus it measures 29/29 intent, 29/29
capability-family, 24/24 tool-family, and 31/31 clarification decisions;
mixed-domain rows remain excluded from scalar family scoring as above. The
measured local latency is p50 ~0.036 ms and p95 ~0.061 ms. This improves the
control measurement only; production steering remains disabled.

## Post-P1 CURRENT quality follow-up

After the Hermes lifecycle repair, the original 31-case corpus was expanded
modestly to 50 sanitized cases from existing Beta/Gamma/Delta examples and
known dogfood language. It covers fragments, shorthand, voice corrections,
temporal follow-ups, server-status shorthand, recipe-plus-mutation language,
and mixed finance/Grocy/web/server requests, without private payloads.

The miss inventory found three systemic classes: referential fragments did not
consistently request clarification; context-dependent cues were lost when
maintained production signals lacked the exact lexical form; and mixed-domain
requests collapsed into one scalar family.

The bounded repair adds fallback/context signal composition, generic temporal
ambiguity handling, and an optional `recommendations` map on the same
`decision-api/v1` result. It preserves ordered composite capability and
tool-family recommendations as semantic metadata only; deterministic policy
still intersects each recommendation. Existing scalar decisions remain
backward-compatible.

Expanded benchmark:

```text
cases:                       50
intent:                      45 / 45
capability family:           50 / 50
tool family:                 43 / 43
needs clarification:         50 / 50
reasoning tier:               7 / 7
local latency p50:          ~0.045 ms
local latency p95:          ~0.071 ms
```

These are sanitized corpus measurements, not mature production semantic
accuracy. CURRENT grew from 209 to 256 lines relative to the post-Alpha
baseline; candidate shadowing, production steering, and authority policy
remain unchanged.

Tool-family scoring excludes the two mixed-domain rows that intentionally
contain multiple expected families; the v1 scalar contract does not pretend
to solve decomposition. These figures are a baseline for corpus and adapter
improvement, not a claim that the existing end-to-end HADES router has only
those accuracies.

## Corpus

The versioned sanitized corpus is:

```text
test-data/decision-corpus-v1/corpus.json
```

It includes ordinary language, poor language, voice transcription errors,
contextual references, cross-domain requests, authority-boundary examples,
and failure dispositions. Authority expectations are recorded separately from
semantic labels and are never sent to a model as permission.

## Candidate status

| Candidate | Current evidence | Alpha disposition |
|---|---|---|
| CURRENT | local production signal projection; measured on corpus | control |
| Jev | hosted typed-decision API; no downloadable local weights; synthetic/public input only | external reference; not production dependency |
| SemIf | pinned local direct-score run: 20/29 capability-family accuracy; ~160 ms p50 | not qualified for this slice |
| NanoJev | public 0.6B game-policy checkpoint; not semantically comparable without a HADES-domain artifact | deferred |
| GLiClass | pinned local small-model run: 6/29 capability-family accuracy | not qualified for this slice |

No candidate currently steers production. Candidate calibration and any
domain-specific retraining remain open; the two measured candidates above are
not promotion candidates.

## Tests

```text
bash scripts/test-decision-api-contract.sh
bash scripts/test-decision-corpus-contract.sh
bash scripts/test-decision-backend-manifest.sh
bash scripts/test-decision-candidate-readiness.sh
bash scripts/test-decision-shadow.sh
PYTHONPATH=. python3 scripts/benchmark-decision-current.py
```

The contract test also proves that a backend outage falls back to CURRENT and
that the result object has no authority or execution surface.

## Privacy

The corpus is sanitized. No hosted candidate may receive private conversations,
Hindsight memory, finance, credentials, tokens, files, or authentication
state during Alpha. Any candidate unable to satisfy this boundary remains an
external research result only.

The shadow harness always returns CURRENT to its caller. It records only a
request hash, decision names, agreement counts, latency, and candidate error
class; it does not log request text.

The deployable shadow configuration is
`config/decision-shadow.json`. It is intentionally disabled, replay-only, and
zero-sample-rate because the bakeoff produced no qualified candidate. Turning
it on requires a new candidate decision and affected production regression
evidence; it cannot steer routing by configuration alone.

The runtime hook in `hades_decision/runtime.py` is the deployable integration
boundary. It accepts an injected candidate, applies deterministic sampling,
returns CURRENT regardless of candidate output, and emits only the bounded
`ShadowObservation`. It is covered by
`scripts/test-decision-runtime-shadow.sh`; no production service currently
enables it.

The complete stage disposition is tracked in the infrastructure acceptance
record. Alpha outcome: Stage 0 PASS, sanitized replay shadow PASS, the
feature-flagged runtime boundary is deployable but disabled, production
candidate shadowing is deferred because no candidate qualified, model routing
is rejected for this bakeoff, tool narrowing and clarification remain on
CURRENT, and retry/escalation plus event triage are deferred as higher-risk
stages. This is an intentional safe disposition, not an untested enablement.

The next candidate evaluation must provide a new pinned artifact, corpus
results that beat the CURRENT control on the intended slice, calibration and
latency evidence, and affected production regression evidence before the
shadow configuration may be enabled. Until then, the live system remains on
the deterministic CURRENT routing path.
