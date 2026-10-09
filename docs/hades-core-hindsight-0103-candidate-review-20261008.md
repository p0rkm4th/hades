# Hindsight 0.10.3 candidate review

Date: 2026-10-08

## Source and pin evidence

- The configured HADES immutable image digest is
  `sha256:84ab276b8f501546deb6ea9c64a57291718b4e16a59dd9e02a02fdd5adfe9028`.
  Its local OCI labels identify Hindsight 0.9.2, source revision
  `ebad478240d3171bb88201ececda5e8d9883d22d`. No Hindsight service was
  running in this environment, so this confirms the configured artifact, not
  deployed runtime parity.
- The previously staged plugin checkout was integration tag 1.2.1, commit
  `d56c4acdf59c41957613d399094cdf8c489b060c`, with client/embed 0.10.2. For
  the end-to-end check below, I mounted the Hermes integration plugin directly
  from the exact v0.10.3 release source. Hermes 0.21.6's candidate environment
  supplied `hindsight-client` 0.10.1, which satisfies that plugin's declared
  `>=0.10.1,<1` range. The plugin's `local_external`/embedded-daemon mode was
  not used by this external-server test.
- Official Hindsight v0.10.3 release source is commit
  `eb6df499d35300e5b2f3f029b2e6adda04ed90f8`, published 2026-10-08. The
  official GHCR tag resolved to immutable image digest
  `sha256:b5da1a9aece1f53a15f12821fb1470f358ed6c74dfaa0c4b1a39c3f3ae93e002`;
  its OCI version and revision labels match v0.10.3 and the release commit.

## Checks

- `scripts/test-hindsight-runtime.sh` passed against the candidate digest via
  `HADES_HINDSIGHT_TEST_IMAGE`. The disposable API and control plane became
  healthy, the explicitly identified worker started, the explicit-memory list
  shape/tag filter matched, and a container restart reclaimed only its own
  synthetic operation while preserving foreign/stale worker rows. The script
  removed its container and volume afterward.
- Three focused Hermes-plugin release tests passed against the exact plugin
  source in the release tag: automatic turn retain, explicit recall formatting,
  and prefetch injection. The tests use a recording fake SDK client.
- Three focused daemon-start tests passed against the same source: new embed
  environment-scrub detection, old embed clean-child fallback, and preserving
  `PYTHONPATH` for helper imports while removing it before daemon launch.
- The exact v0.10.3 `hindsight-embed` implementation test for
  `_strip_parent_interpreter_env` passed.
- The authenticated UI flow then passed using Hermes Agent 0.21.6 source commit
  `818c13be1dc4fd28987e1e881a9408224afd4535`, the v0.10.3 plugin source, the
  v0.10.3 server image digest above, and the previously qualified Open WebUI
  0.11.4 candidate image. Bank precreation was disabled, so HADES created the
  authenticated subject banks on demand. Alpha retain, correction, and fresh
  typo recall passed; Beta and Gamma could not recall Alpha's facts. Fresh
  recall took 3.38 seconds. The test harness removed its containers and
  volumes. The run report is synthetic-only and records those outcomes.
- An opt-in successful-run log capture reproduced the result and exposed
  Hermes' separate automatic title-generation tasks using the deliberately
  unreachable `synthetic-no-call` provider. They produced 33 connection retry
  errors during the run; the five deterministic memory turns still completed
  and Alpha recall remained about 3.38 seconds. The title prompts and failures
  are separate from the explicit-memory path. This does not prove ordinary
  owner turns avoid auxiliary generations. Production title-generation
  behavior and its latency impact remain unqualified.

## Overlay disposition

Hermes/Hindsight's 0.10.3 plugin starts its embedded server out of process; the
new `hindsight-embed` strips interpreter-selection variables from that daemon
child. Its exact implementation test proves the scrubber, while the UI test
used Hindsight as an external server and therefore did not exercise embedded
daemon startup. This does not justify removing
`_hades_overlay_non_hermes_interpreter`: that HADES startup guard also covers
unrelated MCP/helper Python processes that inherit Hermes `PYTHONPATH` and lack
Hermes-only packages.

HADES' Hindsight overlay also binds memory banks to trusted subjects, excludes
shared household turns from private automatic retain, limits automatic recall,
and normalizes explicit recall. Those owner/privacy behaviors are not replaced
by this release. The asynchronous-retain wrapper remains under review; the
v0.10.3 plugin has native `retain_async` configuration (default true), but
removal still needs a full candidate profile replay proving equivalent HADES
write latency, read-after-write behavior, and error reporting.

## Decision

**Qualify 0.10.3 as a candidate; hold the configured production pin.** The
server API/recovery and authenticated HADES explicit-memory path now pass
against the exact v0.10.3 server and plugin source, including bank creation,
correction freshness, typo recall, and Alpha/Beta/Gamma isolation. Still open
are Hindsight provider automatic retain/prefetch behavior, semantic paraphrase
recall, the plugin's embedded-daemon mode, and a full restart/recovery replay
through Hermes and HADES together. The synthetic UI test also surfaces
unqualified Hermes automatic title-generation traffic, which must be accounted
for in owner-visible latency and ordinary-chat measurements. Do not change
production based on this partial acceptance.

Authoritative release: [Hindsight v0.10.3](https://github.com/vectorize-io/hindsight/releases/tag/v0.10.3).
