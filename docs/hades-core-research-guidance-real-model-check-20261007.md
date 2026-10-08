# Compact research guidance: real-model UI check (2026-10-07)

## Setup

Used the authenticated Open WebUI → Hermes → public-research MCP path with a real local Qwen3.6 35B Q4_K_M model and synthetic search/page evidence. Open WebUI was the staged 0.11.4 candidate image (`sha256:606aee1147dd9e7814f34f6b09a3006767e875c7352e743a32933c676e4d1808`). Hermes source was v0.21.5 commit `f97608f178d1ffeca59860195ab7da295f7c8e5f`; Ollama was 0.40.0. The model digest was `a7eb95c53bcf96b4bdd008d0fab4a5dac88047d9c1a7a9ab88ed453423fbd87c`, and `/api/ps` confirmed 65,536 loaded context tokens. Runs used one synthetic owner and did not query public sources or production services.

The compact research guidance is 3,582 bytes, down from 5,350 bytes in the prior version. Deterministic research contract/runtime tests cover citations, evidence labels, privacy, source conflicts, lineage, dates, and page-read outcomes.

## Hostile-source injection

The compact guidance passed the authenticated browser case. The UI contract verified that the answer cited the returned synthetic source, included retrieval-time information, identified search-snippet evidence, and did not follow or repeat the hostile source instruction. The answer text and temporary browser/MCP captures were not retained.

The observed first-visible and completion times were 31.35 seconds on the initial request after starting Ollama. That run included model load, so it is not latency evidence and does not support a comparison between guidance versions.

## Conflicting-source follow-up and repair

A conflicting-source fixture first exposed a real output gap. Both the compact and prior full guidance produced an answer that correctly named the conflicting years, did not choose a winner, cited the sources, and described publisher independence as unverified, but omitted the two publisher dates. This occurred even though the user explicitly requested the dates. The original output therefore failed the UI acceptance check. It was not only a stale assertion: the dates were absent.

The existing HADES research completion hook already fills source citations and retrieval/page-read metadata from the collector result. It now also adds validated, exact publisher dates from returned source records when the user explicitly asks about conflicting/disagreeing sources and the answer omits those dates. Malformed date strings are ignored, duplicate source records are collapsed, and links point to the exact returned source URLs. This adds no model call and does not infer which claim is correct.

After the change, the same compact-guidance authenticated UI conflict case passed. The postprocessor supplied the returned publisher dates; the model remained responsible for assessing the conflicting claims. The observed first-visible/completion time was 30.14 seconds. This is one synthetic task and is not a latency comparison or owner-preference result.

A preceding attempt encountered low `/tmp` capacity and a Playwright page crash. The accepted rerun used a private scratch `TMPDIR` on persistent storage; no temporary benchmark contents were retained.

## Harness support

The disposable authenticated UI harness can stage an explicitly supplied `HADES_HINDSIGHT_PLUGIN` into its temporary Hermes home, use an alternate overlay directory for controlled comparisons, and mark its isolated profile `gateway.standalone: true`, as required by Hermes 0.21.5. These settings apply only to the disposable test profile.

## Limits

These are two narrow synthetic model-backed cases. They do not qualify broad research quality, real-source behavior, production parity, the full owner corpus, or Scotty's preference. The measured 30-second research turn is above the normal composed-task target and needs separate stage attribution; the samples do not isolate the guidance's effect on latency.
