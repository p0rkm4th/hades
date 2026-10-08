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

The deeper retain/recall route test did not qualify: Hindsight returned HTTP 500 before the host-side mock model received any request (`mock_request_count=0`). That route test depends on a container reaching a host-gateway mock, while this rootless setup deliberately disables host-loopback access. Treat this as an isolated harness networking limitation, not evidence of a release regression. The candidate still needs an isolated sidecar mock, correction/freshness assertions, populated-volume migration from the prior candidate, and the Hermes embedded-provider/PYTHONPATH test before promotion. Production remains on its current immutable pin.

## Next action

Complete the outstanding Hindsight `0.10.3` acceptance using the immutable digest above and its corresponding Hermes integration/client dependency. Run authenticated memory, correction/freshness, embedded startup/PYTHONPATH isolation, and backup/restore contracts in a disposable profile. Compare latency and recall behavior against the current `0.10.2` candidate with identical data and model settings. Accept only if memory isolation and correction freshness remain intact and the new process boundary removes measurable HADES startup or request-path work. Keep production pins unchanged until provenance and all relevant gates pass.
