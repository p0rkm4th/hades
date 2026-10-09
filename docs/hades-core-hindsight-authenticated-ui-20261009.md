# Authenticated Hindsight UI acceptance — 2026-10-09

The disposable Alpha/Beta/Gamma browser acceptance passed against the Hermes
0.21.6 artifact at source commit `818c13be1dc4fd28987e1e881a9408224afd4535`,
the Hindsight 0.10.3 integration source at commit
`eb6df499d35300e5b2f3f029b2e6adda04ed90f8`, the pinned Hindsight 0.10.3
container image, and the Open WebUI 0.11.4 candidate image
`hades-open-webui:0.11.4-candidate-bound`.

The test exercised explicit memory retain, correction, fresh recall, isolation
between Alpha and Beta/Gamma, and chat persistence. Hermes logged five
completions through HADES's deterministic explicit-memory path. The synthetic
extractor recorded five requests: one chat-completions extraction and four
Hindsight `/api/chat` requests. No owner or production data was used. The test
script removed its containers and volumes after completion.

The first rerun without a preinstalled plugin failed during HADES overlay
initialization because Hermes's first-start catalog migration occurs after
`sitecustomize.py` loads. The authenticated harness accepts an explicit plugin
source path; rerunning with the exact pinned integration source present before
gateway startup passed, including owner subject propagation. This is a harness
setup requirement for clean-upstream Hermes staging, not evidence that the
production Hindsight integration has been migrated or promoted.

The harness now disables Open WebUI title, follow-up, and tag generation. Those
background tasks are unrelated to the memory contract and otherwise try to
call the deliberately unavailable test chat model. This keeps the acceptance
focused on the authenticated memory flow and avoids attributing UI task-model
failures to HADES memory routing.

This is scoped multi-user memory evidence only. It does not qualify full
household UX, group isolation, shared-chat policy, all domain tools, or
Scotty's overall preference for HADES.
