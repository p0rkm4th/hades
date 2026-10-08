# Hermes 0.21.6 staging candidate

## Decision

Qualify Hermes 0.21.6 as a staging candidate only. Production remains pinned to
Hermes 0.21.2, including its existing installer default and Python 3.11–3.13
contract. The candidate installer selects the candidate's own release archive,
checksum, source commit, and Python 3.14 default; it does not alter the
production deployment pin.

## Provenance

The official [Hermes Agent v0.21.6 release](https://github.com/NousResearch/hermes-agent/releases/tag/v0.21.6)
is dated 2026-10-08 and points to commit
`818c13be1dc4fd28987e1e881a9408224afd4535`. Its published notes identify
security fixes for dashboard authentication, untrusted repository Git
filters, and email sender parsing. The immutable source archive SHA-256 is
`1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8`.

The separately staged Hindsight plugin source is pinned to repository commit
`d56c4acdf59c41957613d399094cdf8c489b060c`; its lock files pin client/embed
libraries to 0.10.1. Although Hindsight 0.10.2 is released, do not claim it is
installed until that plugin lock is deliberately refreshed and tested.

## Qualification evidence

- Installed the exact v0.21.6 archive into a fresh staging prefix. The
  install provenance records the archive SHA and source commit; the Hermes
  install stamp records version 0.21.6 and the same commit.
- Ran nine focused upstream modules from the clean source with the staged
  Python 3.14 environment: memory provider, provider initialization and
  unavailable behavior, declared conversation scope, ACP MCP discovery,
  Hermes MCP server transport, relay upstream authorization, relay auth, and
  wire user identity. Result: **138 passed**.
- Candidate installer contract verifies Python 3.14 is accepted for the
  candidate and Python 3.15 is rejected. A production-path regression check
  verifies Python 3.14 remains rejected for the current 0.21.2 pin.
- Version manifest and one-component upgrade-helper contracts pass with the
  candidate metadata.

These checks qualify artifact installation and focused upstream behavior. They
do not establish full HADES compatibility, production deployment safety, or
owner preference. Keep the candidate in staging until broader gateway,
Open WebUI, security, workspace, and owner-use gates pass.
