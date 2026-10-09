# Commit follow-up friction experiment — 2026-10-09

## Control

Four order-balanced PLAIN STACK/HADES workflow replays used Hermes 0.21.6,
Ollama 0.40.2, Qwen3.6 35B Q4_K_M, a verified 65,536-token context, a
network-disabled rootless sandbox, and the same synthetic multifile coding
task. HADES used the overlay at revision `0aca0f73661feaa4a2cf5da72792c5424a69990d`.
The first two pairs had current Hindsight provider discovery configured from
the Hermes catalog subdirectory. All runs passed focused tests, source-scope
checks, and diff checks. The plain arm committed both tasks; the baseline HADES
arm also committed both tasks.

The first valid captured pair had median total time 48.73 s for PLAIN STACK
and 52.26 s for HADES. Median incremental phase times were:

| Phase | PLAIN STACK | HADES | HADES delta |
|---|---:|---:|---:|
| Inspect | 23.60 s | 23.81 s | +0.21 s |
| Edit | 5.64 s | 5.80 s | +0.16 s |
| Focused test | 10.19 s | 8.61 s | −1.58 s |
| Review diff | 3.70 s | 4.64 s | +0.94 s |
| Commit | 5.60 s | 9.38 s | +3.78 s |

HADES used fewer model API calls and tool results overall in this pair, and
ran the focused test faster. In one of its two tasks, however, it called
`git diff` again during the commit turn after a preceding diff review. The
current authenticated diff was supplied during the review turn but was absent
from the later commit request. This made the commit phase the clearest
measured HADES tax.

## Rejected candidates

Three bounded prompt/control experiments tried to remove the repeated diff:

| Candidate | HADES commits | HADES diff calls outside review | Decision |
|---|---:|---:|---|
| Fresh diff context on commit follow-up; instruct model not to repeat it | 1/2 | 0 | Reject: one task ended with an uncommitted worktree |
| Same, with explicit instruction to use terminal and report commit only after success | 1/2 | 1 | Reject: still failed to commit one task |
| Same, with OpenAI function-specific `tool_choice` for `terminal` | 0/2 | 0 | Reject: both completion requests returned HTTP 200 with `stop` and no tool call |

The forced-tool-choice experiment is recorded as an unsuccessful model/runtime
interaction, not as a successful action. Independent verification found an
uncommitted worktree in both HADES tasks. All PLAIN STACK tasks in these runs
committed successfully. The candidate code was discarded; the workspace
overlay and runtime test script are unchanged by this experiment.

## What the candidate comparison does not isolate

The fresh-diff and explicit-terminal candidates changed two things on the
commit follow-up: they injected newly collected diff context, and they removed
all earlier `tool` messages and assistant messages containing `tool_calls`
from the conversation history sent to the model. The forced-terminal
candidate did the same while also setting a function-specific `tool_choice`.
The baseline retained the conversation history. Therefore the 1/2 and 0/2
candidate results cannot be attributed to fresh diff context, the extra
instruction, or history filtering individually. The evidence supports
rejecting those combined candidates, not a claim that the added diff evidence
itself reduces commit reliability.

The next comparison should preserve the baseline history and vary one factor
at a time: first test fresh diff context alone, then history filtering alone
only if there is a concrete reason to remove those messages. A candidate must
be judged by independent commit, source-scope, test, and clean-worktree checks;
HTTP success or a final model response is not proof of a commit. The local
Ollama 0.40.2 forced-choice result also shows that this specific setting did
not produce a tool call in these two requests; it does not establish a general
runtime guarantee or explain the other candidate failures.

## Fresh diff context alone — paired rerun

A corrected benchmark hook reached the HADES child and called the native
workspace-diff helper at commit entry. It appended the helper's returned
bounded text to the ephemeral prompt, preserved full conversation history,
and left `tool_choice` unchanged. The capture confirms 661 characters of
complete diff evidence; provider requests carried 14,385 system bytes versus
13,722 in the same-source no-injection control. Both stacks used Hermes
0.21.6, Ollama 0.40.2, the same Qwen3.6 35B digest, 65,536-token context,
rootless Docker 29.8.2, the immutable network-disabled sandbox, a shared
prewarmed package-manager store, and the same two synthetic multifile tasks.

| Measure | PLAIN STACK | HADES with fresh diff context |
|---|---:|---:|
| Median task time | 54.97 s | 53.64 s |
| Median model API calls per task | 13.5 | 12 |
| Median tool results per task | 9.5 | 7.5 |
| Focused tests and source-only commits | 2/2 | 2/2 |
| HADES `git diff` outside review phase | — | 0 calls |
| HADES review-phase diff attempt | — | 1, rejected before execution |

The HADES candidate preserved completion and clean-worktree results, but the
single same-source no-injection control also committed successfully and made
no diff attempts outside its review phase. In one candidate review turn, the
model attempted a `terminal` call with Git-diff-shaped arguments despite the
supplied diff and `tool_choice=none`. HADES rejected the call as an invalid
tool because the review allowlist was empty; no command executed. Its 1.33-
second median advantage over PLAIN does not isolate the effect of the prompt
addition. Two pairs are too few to show that the added 661 characters improved
task quality, time, or reliability.

This is consistent with Ollama's OpenAI-compatibility documentation, which
does not list `tool_choice` as a supported `/v1/chat/completions` request
field. Treat `tool_choice=none` as a provider hint, not an authorization
control; the empty HADES dispatch allowlist is what rejected the observed
attempt. The review schema remains visible for prompt-prefix reuse, so a
provider may still emit an unusable call. Removing review schemas remains an
unqualified latency/quality tradeoff, not an automatic fix. See the [Ollama
compatibility field list](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx#supported-request-fields).
Reject the prompt addition for now: it has no demonstrated advantage over the
same-source HADES control and increased context/tool overhead. The experiment
is synthetic; no owner preference or response-quality rating was collected.

One earlier diagnostic run was invalid because the benchmark hook referenced
a parent-only workspace variable. The sanitized diagnostic records its
`NameError`; it is excluded from the stack comparison. The corrected runner
uses the child workspace path. Artifacts: [`fresh diff candidate`](../benchmarks/hades-core-workspace-commit-followup-fresh-diff-only-ollama0402-20261009.json), [same-source no-injection control](../benchmarks/hades-core-workspace-commit-followup-baseline-same-source-ollama0402-20261009.json), and [invalid harness diagnostic](../benchmarks/hades-core-workspace-commit-followup-fresh-diff-diagnostic-ollama0402-20261009.json).

The sanitized runner output for the baseline and all candidates is in
[`benchmarks`](../benchmarks):

- [`baseline capture`](../benchmarks/hades-core-workspace-commit-followup-baseline-ollama0402-20261009.json)
- [`fresh diff prompt`](../benchmarks/hades-core-workspace-commit-followup-fresh-diff-ollama0402-20261009.json)
- [`explicit terminal instruction`](../benchmarks/hades-core-workspace-commit-followup-explicit-terminal-ollama0402-20261009.json)
- [`forced terminal tool choice`](../benchmarks/hades-core-workspace-commit-followup-forced-terminal-ollama0402-20261009.json)

The artifacts contain aggregate timings and sanitized request/tool metadata,
not prompt or answer text. The fixtures and account identities were synthetic.

## Runtime test status and next action

The focused overlay assertions verified that a commit immediately following
an explicit diff-review request received fresh authenticated diff evidence
and retained the authorized workspace tool surface. The full Hermes runtime
script then stopped later in its fabricated-result case with a
`privacy check is unavailable` response. This script did not pass end to end;
the privacy-check failure needs separate diagnosis.

Do not retain prompt-only diff-context or forced-tool-choice behavior. The next
useful step is to inspect the exact HADES completion and tool-validation
boundary for commit requests, then test a native Hermes capability or a small
adapter that guarantees truthful commit status without claiming an unverified
commit. Any candidate must complete 2/2 commits and pass the existing
workspace containment and verification contracts before it can replace the
current behavior.
