# Browser interaction evaluation

Status: SELECTED / STAGED.

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

No browser profile, credential, production MCP registration, or external
side-effecting workflow was changed by this evaluation.

The disposable navigation/snapshot and explicit-submit contract is reproducible with
scripts/test-playwright-mcp-fixture.sh. It uses a local fixture and isolated
in-memory browser state, verifies no POST occurs before the explicit Apply
click, and verifies exactly one POST afterward.

Upstream reference:
https://github.com/microsoft/playwright-mcp.
