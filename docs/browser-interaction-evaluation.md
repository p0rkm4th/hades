# Browser interaction evaluation

Status: PASS / ANONYMOUS READ-ONLY.

Microsoft Playwright MCP is selected for pages that require dynamic rendering,
navigation, or an authorized form workflow. Direct HTTP and structured
extraction remain preferred for ordinary research and recipe pages.

## Staged artifact

| Field | Value |
|---|---|
| Package | @playwright/mcp |
| Version | 0.0.81 |
| npm integrity | sha512-c4eVex1nS53IzLHlwAm0J9ZISDTvA7RndFX8oVcQOrmvIrKSkByazpq79lZHWJuWTB7Gpk0sLBQoRepyIgmneA== |
| Authority | anonymous browser profile by default |
| Privileged profile | separate, explicit owner-only staging input |

The package supports isolated in-memory sessions and persistent profiles.
HADES must keep those profiles separate: prompt text cannot select an
authenticated owner session, and household users cannot inherit it.

The provider-neutral selector in integrations/browser-access/policy.py enforces
that rule: household scope can select only anonymous browsing, while an owner
profile requires trusted owner scope and an explicit boolean application
authorization. Malformed authorization values fail closed rather than being
accepted through truthiness.

## Side-effect contract

- Read a page: normally allowed.
- Fill a form: draft/preview only.
- Submit a form: explicit confirmation.
- Purchase, account/security change, or privileged control: excluded from the
  first slice.
- Browser credentials, cookies, and storage state never enter model-generated
  URLs or repository evidence.

## Acceptance sequence

1. Run an isolated anonymous session against a disposable local web fixture.
2. Verify structured page reading and dynamic navigation.
3. Verify draft form fill does not submit.
4. Verify a submission requires explicit confirmation and reports the result.
5. Verify the privileged profile is unavailable to household scope.
6. Verify reload behavior only for the explicitly selected profile.

No credential, privileged profile, or external side-effecting workflow was
changed by this evaluation. The bounded anonymous actor path is accepted;
privileged browsing remains deferred.

## Current upstream decision — 2026-09-15

The current Playwright MCP core surface includes navigation, clicks, form
filling, typing, JavaScript evaluation, file upload, and tab operations in
addition to snapshots and other reads. Its `--isolated` option prevents
profile persistence, but does not make those tools read-only. Origin allowlists
also do not replace an HADES authorization boundary because redirects and
page-side behavior remain outside that setting's guarantee.

Therefore the raw package remains a dependency behind the HADES proxy, not a direct Hermes
registration. HADES now has a separate `browser-research` proxy at
`integrations/browser-access/proxy.py`. It launches the pinned package in
isolated headless mode, forces all browser traffic through a local filtering
proxy, and exposes only anonymous navigation and read tools;
it requires `HADES_BROWSER_ALLOWED_HOSTS` and remains unavailable when that
allowlist is empty. Draft, submit, storage, file, evaluation, and privileged
profile operations remain outside this registered surface. Recipe and research
flows should still prefer direct HTTP/structured extraction when sufficient.

The disposable navigation/snapshot and explicit-submit contract is reproducible with
scripts/test-playwright-mcp-fixture.sh. It uses a local fixture and isolated
in-memory browser state, verifies no POST occurs before the explicit Apply
click, and verifies exactly one POST afterward.

The policy proxy's real MCP round trip is reproducible with
scripts/test-browser-proxy-fixture.sh: it launches the pinned upstream
package, filters the advertised tools, navigates to a disposable loopback
fixture, reads its accessibility snapshot, rejects a click call, and blocks a
redirect to an unapproved host at the network proxy. The loopback/private-
target override exists only inside that test process.

Upstream reference:
https://github.com/microsoft/playwright-mcp.
