# Browser interaction evaluation

Status: PASS / ANONYMOUS, READ-ORIENTED.

Microsoft Playwright MCP is selected for pages that require dynamic rendering,
navigation, or an authorized form workflow. Direct HTTP and structured
extraction remain preferred for ordinary research and recipe pages.

## Staged artifact

| Field | Value |
|---|---|
| Package | @playwright/mcp |
| Version | 0.0.83 |
| npm integrity | sha512-oNcl+Ae2/IAjhfPeP46BfIkSakfmprY+aOtkv5MjrQ4lPav4/yNtPhL0iq8SlIM90oApWgBDUxaNKvktazUKOg== |
| Release source | [Microsoft Playwright MCP v0.0.83](https://github.com/microsoft/playwright-mcp/releases/tag/v0.0.83) |
| Browser build | Chrome for Testing 155.0.8059.12, Playwright Chromium revision 1247 |
| Staging browser setup | `npx --yes @playwright/mcp@0.0.83 install-browser chrome-for-testing` |
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

## Current upstream decision — 2026-10-08

The HADES candidate now pins Microsoft Playwright MCP 0.0.83. The npm registry
SHA-512 integrity was independently checked against the published tarball and
matches the staged artifact row above. The official v0.0.83 release fixes stale
WebMCP tab/frame binding, browser-close download crashes, and page-load dialog
timeouts; it also supports WebMCP tools with Chromium 155+.

The anonymous proxy policy adapter and DNS pinning/HTTP-write rejection checks
passed. The direct disposable Playwright fixture also passed with the Chromium
155 build required by 0.0.83; it verified dynamic page reading, no submission
before an explicit action, and exactly one submission after that action. A
separate real MCP round trip through the HADES proxy passed the upstream tool
filter, blocked page-script POST, denied an unapproved redirect, and confirmed
the private-target override was fixture-only. The candidate changes no
privileged profile or production service; deployment artifact parity and
owner-visible browser acceptance remain open.

The package launch does not install its browser build. Any deployment candidate
must provision the matching Chromium 155 / revision 1247 artifact once and
verify its source/checksum before enabling the proxy; installing it on every
browser request would add avoidable latency.

## Decision rationale — 2026-09-15

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
redirect to an unapproved host at the network proxy. The fixture also runs page
JavaScript, verifies that rendered content is visible, and confirms that
fetch/XHR POST attempts do not reach the fixture. A tracked init script blocks
non-read JavaScript APIs; the HTTP proxy rejects methods other than GET/HEAD.
All hostname answers are validated together and the outbound socket uses the
same validated IP, so a later DNS answer cannot redirect a request to a
private target. The loopback/private-target override exists only inside test
processes.

Public research can optionally fall back to one anonymous rendered page when
static extraction fails or yields fewer than 80 non-whitespace characters. It emits `DYNAMIC_PAGE` evidence
with the requested and final URLs, retrieval time, title, and an explicit
untrusted-text warning. This fallback is disabled by default. Enable it only
with `HADES_PUBLIC_RESEARCH_DYNAMIC_ENABLED=true` and an explicit reviewed
`HADES_BROWSER_ALLOWED_HOSTS` list in the private Hermes environment. No
browser credentials, cookies, forms, or authenticated profiles are used.

Upstream reference:
https://github.com/microsoft/playwright-mcp.
