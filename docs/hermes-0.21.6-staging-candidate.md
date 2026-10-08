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

The separate Hindsight plugin at commit
[`d56c4ac`](https://github.com/vectorize-io/hindsight/tree/d56c4acdf59c41957613d399094cdf8c489b060c/hindsight-integrations/hermes)
is outside this package-install slice. Its [`pyproject.toml`](https://github.com/vectorize-io/hindsight/blob/d56c4acdf59c41957613d399094cdf8c489b060c/hindsight-integrations/hermes/pyproject.toml)
reports version 1.2.1 while its [`uv.lock`](https://github.com/vectorize-io/hindsight/blob/d56c4acdf59c41957613d399094cdf8c489b060c/hindsight-integrations/hermes/uv.lock)
virtual package reports 1.2.0; client/embed dependencies are locked at 0.10.1.
Hindsight 0.10.2 is released, but this evidence does not qualify a refreshed
plugin lock or plugin activation. Keep Hermes-plus-Hindsight qualification
open until that lock is reconciled and tested.

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
- Candidate URL and checksum overrides that would break source provenance are
  rejected. Production artifact checks also require the manifest-pinned
  checksum before recording the pinned source commit.
- Version manifest and one-component upgrade-helper contracts pass with the
  candidate metadata.

These checks qualify Hermes package artifact installation and focused upstream
behavior. They do not establish Hindsight plugin installation/activation, full
HADES compatibility, production deployment safety, or owner preference. Keep
the candidate in staging until the plugin lock, broader gateway, Open WebUI,
security, workspace, and owner-use gates pass.
