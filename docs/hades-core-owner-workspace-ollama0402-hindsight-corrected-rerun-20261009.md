# Workspace workflow comparison on Ollama 0.40.2 with catalog Hindsight provider

This corrected two-pair `workflow-to-commit` replay used source revision
`0aca0f73661feaa4a2cf5da72792c5424a69990d`, clean Hermes Agent 0.21.6
(`818c13be1dc4fd28987e1e881a9408224afd4535`), staged Ollama 0.40.2, and the
Qwen3.6 35B Q4_K_M manifest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`. Both
stacks used a verified 65,536-token context, the same isolated rootless Docker
29.8.2 daemon, the same network-disabled immutable sandbox image, a prewarmed
shared package-manager store, and the same synthetic multifile fixture. Arm
order was PLAIN, HADES, HADES, PLAIN.

The HADES profile installed the catalogued Hermes provider at
`hindsight-integrations/hermes` from Hindsight source commit
`eb6df499d35300e5b2f3f029b2e6adda04ed90f8`. An initial attempt used the
Hindsight monorepo root and failed provider discovery before the paired run;
that attempt is excluded. The corrected run used the provider subdirectory
named by Hermes's plugin catalog and completed both arms.

## Results

| Measure | PLAIN STACK | HADES |
|---|---:|---:|
| Median task time | 47.85 s | 55.03 s |
| HADES median delta | — | +7.18 s (+15.0%) |
| Median model API calls per task | 11.5 | 12.0 |
| Median tool results per task | 7.5 | 7.5 |
| Successful focused tests and commits | 2/2 | 2/2 |

All four task runs passed the independent test, diff, source-scope, commit,
and clean-worktree checks. HADES made one `git diff` call outside the explicit
review phase across its two tasks. No answer text or commit text was retained;
there were no human quality or owner-preference ratings.

## Decision

This is a valid current-runtime comparison and confirms the coding path works
with Hermes's catalog Hindsight provider configured before startup. It does
not show a usability win: HADES remains 7.18 seconds slower by median on this
small workflow. Equal tool-result counts suggest the previous run's extra tool
results are not stable; the remaining time difference may be generation
variance or call scheduling. Two pairs are too few to separate those causes.
Keep this as a friction signal, repeat the coding subset after a coherent
change, and collect direct owner preference before claiming improvement.

The run is synthetic and local. It does not qualify larger coding tasks,
remote pushes, Open WebUI persistence, production authentication, or owner
preference. The source telemetry was emitted by the benchmark runner but not
committed as a raw transcript artifact; no prompts, answers, fixture contents,
or secrets are included here.
