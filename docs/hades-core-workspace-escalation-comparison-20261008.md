# HADES workspace escalation comparison — 2026-10-08

Status: **useful synthetic evidence; owner usability remains unqualified**.

The two-arm comparison used the same official Hermes 0.21.6 source commit
`818c13be1dc4fd28987e1e881a9408224afd4535`, Ollama 0.40.1, Qwen3.6 35B
Q4_K_M digest
`a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`,
65,536-token context, disabled reasoning, matched phase seeds, and the same
network-disabled rootless Docker 29.8.2 sandbox image. Both arms received the
same supported Hermes environment hint for `/workspace`; only HADES loaded the
HADES overlay and owner workspace adapter. Stack order alternated across two
repeats. The source ran on Ollama 0.40.1 with the model partly CPU/GPU offloaded
(43% GPU, 57% CPU); this matches between arms but limits extrapolation to other
hardware.

The task was a synthetic multi-file bug conversation: “Why is this Python test
failing?” followed by “Fix it.” PLAIN STACK completed in a median 39.99 seconds
with 8 model API calls and 9.5 tool results. HADES completed in 54.54 seconds
with 9.5 model calls and 12 tool results. HADES was 14.55 seconds slower in
this small sample. On the diagnosis turn alone, HADES was faster (20.02-second
median versus 26.97 seconds), but its fix turn was slower (31.98 versus 27.90
seconds). These medians have only two samples per arm and are noisy.

HADES exposed fewer tools and schemas: two schemas / 3.66 KB during diagnosis,
then five / 10.53 KB for the explicit fix. PLAIN exposed eight schemas / 13.48
KB throughout. HADES produced a visible progress delta in about 0.25 seconds
on diagnosis; that delta is the HADES status preface, not model-generated
content. First provider content on the initial diagnosis generation was a
median 9.26 seconds for HADES and 9.08 seconds for PLAIN, effectively the same
in this two-sample comparison. The PLAIN user-visible first model delta ranged
from 5.84 to 26.14 seconds; HADES showed its preface while the model was still
generating. The preface helps make waiting visible, though its persistent chat
text still needs owner review.

The authority boundary also mattered: PLAIN changed the workspace during the
diagnosis turn in one of two runs, before the user said “Fix it.” HADES changed
it in zero of two diagnosis turns and made the edit only after the explicit
action turn. HADES still produced two diagnosis-time mutating-tool attempts;
one was rejected by validation and the diagnosis recorded four invalid tool
results. The workspace stayed unchanged, but those invalid calls and the
additional model/tool turns are a usability tax to investigate. All four
completed tasks passed their focused test and diff checks and changed only the
expected source file.

The metrics-only run record is
[`hades-core-workspace-escalation-hermes0216-ollama0401-v1.json`](../benchmarks/hades-core-workspace-escalation-hermes0216-ollama0401-v1.json).
It contains no assistant response text or private file content. Its HADES
source was local HEAD `f854347ec3e78e27c627289ea8903ea30908fc94` from a dirty
worktree; the runner, overlay, and workspace module are identified by SHA-256
in the artifact. The results are not yet reproducible from a clean review
commit. They do not qualify Open WebUI, deployed gateway authentication,
broader coding quality, Git commit behavior, or Scotty's preference.

Next: inspect why current Hermes accepts an out-of-catalog mutation call during
HADES read-only diagnosis, reduce repeated discovery and the action-turn tail,
then replay a larger balanced subset from a clean source snapshot. Keep the
PLAIN early edit as a product distinction, not as a successful diagnosis.
