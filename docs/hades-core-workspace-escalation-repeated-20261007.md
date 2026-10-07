# Repeated workspace escalation comparison (2026-10-07)

## Method

Ran two synthetic, multi-file diagnosis → action pairs through PLAIN and HADES using Hermes 0.21.5, Ollama 0.40.0, the same Qwen3.6 35B digest, 65,536 context, matched phase seeds, and one shared warm model process. Pair order was balanced across repeats. Both arms used a rootless Docker 29.8.2 daemon and the same immutable sandbox image with container networking disabled. The staged slirp4netns 1.3.6 package hash was checked against Arch's official package database; the package signature was not independently validated because its signing key was unavailable locally.

## Results

- HADES median task time was 45.5s (range 45.2–45.7s); PLAIN was 40.2s (range 27.0–53.4s). HADES used 6 model generations and 8 tool results per task at the median; PLAIN used 9.5 generations and 12.5 tool results. The two-sample latency difference is not stable enough to qualify.
- HADES kept diagnosis from changing the workspace in both runs. It nevertheless attempted one diagnosis-time terminal test call that returned invalid/no usable result; workspace state remained unchanged.
- During the action follow-up, HADES ran a terminal test in 1 of 2 runs. In the other, it patched, made no action-phase terminal call, and the completion guard returned an unverified notice. This confirms the prompt instruction does not guarantee verification, while the guard prevents a false passing-test claim.
- PLAIN changed the workspace during diagnosis in 1 of 2 runs. Its later action phase then made no tool calls, so it also failed the requested escalation sequence in that sample.
- Independent post-run tests and diff checks passed in all four final workspaces, with only the expected source changed. These checks validate final state, not when the assistant acted or verified.
- HADES emitted an early progress delta, but that includes a host-generated preface. The artifact separates that visible-progress timing from provider-reported first model content; the two must not be conflated as model TTFT.

The artifact reports counts and timings only; prompts, responses, commands, file contents, tool arguments, transcripts, local paths, and identity values are omitted. It is a diagnostic, not an owner preference result. It does not qualify the full coding workflow, Git actions, Open WebUI continuity, or Scotty's preference.

## Next work

Investigate why the action loop stops after a successful patch without running terminal verification in one of two HADES runs. Preserve the truthful unverified guard and diagnosis-time no-mutation boundary while testing a native Hermes completion mechanism. The latency distribution also needs more paired samples before choosing a latency intervention.
