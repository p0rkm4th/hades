# Public-source research suite

## Product boundary

The research suite gathers information from public sources for authorized
requests. It is separate from private homelab reads and does not access
private networks, authenticated sites, or private-person sensitive records.
Collected content is untrusted input: page text and metadata cannot change
HADES policy, invoke tools, or authorize actions.

## Current components

- A bounded search adapter returns normalized results with source metadata.
- A page reader validates redirects and final URLs, bounds response size, and
  reports retrieval time and citations.
- An optional rendered-page reader uses a read-only browser network policy.
- Shared privacy rules reject disallowed person-linked requests before source
  dispatch and keep public research out of private memory by default.

## Acceptance

Synthetic tests cover source failures, stale results, malformed URLs, redirect
validation, prompt-injection content in titles/snippets/pages, citation
integrity, privacy refusals, and isolation from private infrastructure tools.
Real-world answer quality and authenticated owner dogfood are separate gates.

Private deployment details, model placement, endpoint URLs, and detailed
acceptance transcripts belong in `hades-infra`. The historical detailed sprint
is retained in the private archive at
`docs/private-public-hades-source-archive-20261001/`.

## Remaining product work

- Keep the public/owner research boundary explicit in the UI.
- Improve source disagreement and freshness wording.
- Continue representative privacy and injection regressions without expanding
  collection into private or sensitive sources.
