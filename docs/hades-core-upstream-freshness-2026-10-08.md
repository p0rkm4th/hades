# HADES Core upstream freshness recheck — 2026-10-08

Execution-time check of official release metadata and the current tracked pins. This is an upgrade decision record, not evidence that production is running these artifacts. No production pin or deployment was changed.

## Current stable releases

| Component | Tracked/deployed evidence | Latest stable at check | Decision |
|---|---|---|---|
| Hermes Agent | Production source pin `0.21.2` in `config/versions.env`; candidate `0.21.6` is already under matched workspace testing. | `0.21.6`, released 2026-10-08, source commit `818c13be1dc4fd28987e1e881a9408224afd4535`. | **QUALIFY in staging; HOLD production.** The new release notes include dashboard authentication hardening (forwarded-IP rate-limit bypass, unbounded auth audit values, missing body-size limit, and non-loopback login-code redirect), repository Git-filter hardening, and email gateway sender validation. Test native behavior and HADES overlay removals on this exact tag before promotion. |
| Open WebUI | Production contract `0.11.1`; candidate image `0.11.4` is recorded in `config/versions.env` and the earlier candidate acceptance is documented in `docs/hades-core-upstream-refresh-2026-10-07.md`. | `0.11.4`, released 2026-09-21. | **HOLD production; retain candidate.** Current stable has no newer release in the official GitHub releases API. Continue the open browser file-picker and production provenance gates; do not infer deployed version from candidate results. |
| Ollama | No production runtime artifact was revalidated in this check. The isolated workspace benchmark used `0.40.1`. | `0.40.1`, released 2026-10-07. | **QUALIFY in staging; HOLD production pending provenance.** The release includes Windows large-file and manifest symlink fixes, cloud account/API behavior changes, and drops an upstream-copied MLX residency patch. Check platform and model-load regressions against HADES' actual runtime before changing pins. |
| Hindsight | Production manifest pins image digest `sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`; that digest's release mapping and deployed runtime are not revalidated here. Hermes candidate client/embed pins were `0.10.2`. | `0.10.3`, released 2026-10-08, source tag commit `eb6df499d35300e5b2f3f029b2e6adda04ed90f8`. Official GHCR tag `0.10.3` resolves to immutable index digest `sha256:b5da1a9aece1f53a15f12821fb1470f358ed6c74dfaa0c4b1a39c3f3ae93e002`. | **UPDATE in staging; HOLD production.** The release fixes Hermes embedded-daemon startup by moving it out of process and preventing a parent `PYTHONPATH` from contaminating the daemon, and fixes recall temporal-window typing. These changes directly merit testing against HADES' process environment, recall correction/freshness contract, and current drain/fallback behavior. Do not update the production image or Hermes plugin/client without matched runtime acceptance. |

## Reproducible release lookups

The stable-release values above were fetched on 2026-10-08 from the repositories' official GitHub Releases API, rather than inferred from search-result snippets. Hindsight's image digest was fetched from the official GHCR OCI manifest for `ghcr.io/vectorize-io/hindsight:0.10.3`; the digest pins the release tag's multi-platform index. The checks establish release availability and immutable source/image identifiers, not local deployment or cryptographic image-to-source provenance.

- [Hermes Agent v0.21.6 release](https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6)
- [Open WebUI v0.11.4 release](https://github.com/open-webui/open-webui/releases/tag/v0.11.4)
- [Ollama v0.40.1 release](https://github.com/ollama/ollama/releases/tag/v0.40.1)
- [Hindsight v0.10.3 release](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.3)
- [Hindsight GHCR package](https://github.com/orgs/vectorize-io/packages/container/package/hindsight)

## Hindsight 0.10.3 staging result

Pulled the official Hindsight `0.10.3` OCI index by digest and verified the amd64 image labels report version `0.10.3` and source revision `eb6df499d35300e5b2f3f029b2e6adda04ed90f8`. In the disposable rootless Docker 29.8.2/VFS staging engine, the focused runtime contract passed: API health, the control-plane HTTP route on loopback, worker startup with its explicit ID, tagged-memory listing, and restart recovery of only the current worker's synthetic operation while preserving foreign/stale rows. The test used synthetic data and a temporary volume; production images and pins were unchanged.

The staging run exposed a brittle assertion in `scripts/test-hindsight-runtime.sh`: it depended on a particular startup log phrase. The test now accepts `HADES_HINDSIGHT_TEST_IMAGE` for candidate qualification and waits for an actual control-plane HTTP response. The updated test passed against the `0.10.3` candidate.

The retain/recall harness now runs its synthetic model as a peer on a disposable user-defined Docker network. It does not add a host-gateway route or weaken RootlessKit's disabled host-loopback boundary. With the exact 0.10.2 digest `sha256:d1840062a5b79940ab7a9f4809ceb90fc776d4ad737cd9329e9b5836cc64ab70` as the source and the exact 0.10.3 index digest above as target, the populated-volume migration test retained a synthetic fact on 0.10.2, restarted 0.10.3 on the same volume, listed the migrated fact, and freshly recalled it.

The same rootless run against 0.10.3 passed extraction through the peer mock, valid tagged-memory listing, fresh recall, and the actual HADES explicit-memory route using the local Hermes 0.21.2 Python environment and private overlay: explicit retain, newest correction after a two-word typo, semantic paraphrase fallback, and Alpha/Beta isolation. A separate five-sample synthetic route measurement reported 29.9 ms direct-match p50 / 34.7 ms p95 and 73.2 ms semantic-fallback p50 / 82.1 ms p95, excluding Python process startup; retain followed by natural recall in a fresh process was 2,969 ms including startup. These are harness measurements, not production latency claims or comparison against 0.10.2.

The earlier HTTP 500 was caused by the host-side mock being unreachable under the intended host-loopback restriction. It was a harness networking defect, not evidence of an upstream regression. Production remains on its current immutable pin.

## Hermes 0.21.6 and Hindsight integration follow-up

Rebuilt the disposable Hermes `0.21.6` candidate from the official release archive (SHA-256 `1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8`, source commit `818c13be1dc4fd28987e1e881a9408224afd4535`). Installed Hindsight client and embed `0.10.3` into that candidate environment and tested the official Hindsight `v0.10.3` Hermes plugin source at commit `eb6df499d35300e5b2f3f029b2e6adda04ed90f8`. The Hindsight `v0.10.3` tag includes updated embedded-daemon startup and environment isolation code. Hermes `v0.21.6`'s bundled plugin catalog still points at older plugin commit `d56c4acdf59c41957613d399094cdf8c489b060c`, whose lockfile resolves client/embed `0.10.1`; the catalog and plugin dependency lock therefore need an intentional candidate refresh before promotion.

Focused upstream plugin tests passed: **51 passed** (`tests/test_local_runtime.py`, `tests/test_provider.py`) with the Hermes 0.21.6 candidate Python and Hindsight 0.10.3 packages. A runtime probe started the real embedded-daemon manager from the v0.10.3 plugin source and received its health response. The child environment had no inherited `PYTHONPATH`, `PYTHONHOME`, `PYTHONSAFEPATH`, or `VIRTUAL_ENV`; the scoped API key was present in the child environment and absent from its argv. The shutdown helper printed a timeout warning even though a follow-up process check found no remaining daemon, so graceful shutdown is not claimed as qualified.

The actual HADES memory route also passed under Hermes 0.21.6 using an isolated `HERMES_HOME` profile containing the Hindsight plugin: explicit retain, correction after a two-word typo, semantic paraphrase recall, and synthetic Alpha/Beta isolation. The valid tagged listing and fresh recall checks passed. Route timings including Python startup were 1,635 ms direct-match, 1,669 ms correction, and 1,755 ms semantic fallback in this synthetic run; these are not user-visible chat latency or owner preference measurements. An initial attempt without `HERMES_HOME` failed to discover the temporary plugin; setting it to the disposable candidate profile fixed the test setup.

**Decision remains QUALIFY in staging; HOLD production.** Update the candidate plugin/client/embed pins only after regenerating a deterministic lock for the chosen plugin source and recording package hashes. Remaining acceptance includes authenticated memory and backup/restore, repeated matched 0.10.2/0.10.3 behavior and latency, graceful child shutdown, and production artifact provenance. Hermes 0.21.6 and Hindsight 0.10.3 are not promoted by these tests.

## Next action

Complete Hindsight `0.10.3` acceptance with a deterministic lock for the selected Hermes integration/client dependency. Run authenticated memory, backup/restore, graceful daemon shutdown, and matched repeated `0.10.2`/`0.10.3` latency and recall contracts in a disposable profile. Keep production pins unchanged until provenance and all relevant gates pass.
