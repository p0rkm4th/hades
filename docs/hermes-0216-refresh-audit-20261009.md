# Hermes 0.21.6 refresh audit — 2026-10-09

## Version state

- Production version in `config/versions.env`: Hermes 0.21.2, pinned to the
  upstream v2026.9.11 source archive with SHA-256
  `bf45fc6c40ad770e30dfa7677ee6804a24be1a7eab768b283a0883c64662d76e`.
- Staged candidate: Hermes 0.21.6, source commit
  `818c13be1dc4fd28987e1e881a9408224afd4535`, archive SHA-256
  `1ba3500cdbe876bb9d347b3c12f41c591a421293eac58faba23571287dfe1cf8`.
- The official release page identifies v0.21.6, released October 8, 2026, as
  the latest release at this audit. It describes the tag as a stable patch
  rollup and defers its curated changes since v0.21.5 to v0.22.0. No specific
  security fix or compatibility fix is attributed to v0.21.6 by that release
  note, so this audit does not infer one.
- Hermes 0.21.6's official `pyproject.toml` declares `requires-python =
  ">=3.11,<3.15"`, with an adjacent comment that 3.14 is the newest supported
  Python and older versions are allowed to permit existing installs to update.

Authoritative sources: [Hermes Agent releases](https://github.com/NousResearch/hermes-agent/releases)
and [v0.21.6 pyproject.toml](https://github.com/NousResearch/hermes-agent/blob/v0.21.6/pyproject.toml).

## Decision

**INVESTIGATE / STAGE; do not promote yet.** The staged 0.21.6 pin is the
current stable and matches the version used in recent PLAIN STACK/HADES
workspace comparisons. Those comparisons establish a useful source-level
behavior sample, not a full installation or deployed-runtime qualification.
Production remains at 0.21.2 pending the broader Hermes overlay and owner
acceptance gates.

## HADES compatibility finding and repair

The installer rejected all Python 3.14 interpreters, even for Hermes 0.21.6.
This made the candidate benchmark environment (Python 3.14.7) differ from the
supported HADES installation path. `scripts/install-hermes-artifact.sh` now
accepts an explicit `--version 0.21.6` candidate install on Python 3.14 while
keeping the default production 0.21.2 install restricted to Python 3.11–3.13.
The selected version is recorded in the artifact provenance.

The focused installer contract checks both sides: 0.21.2 remains rejected on
Python 3.14, while an explicit 0.21.6 candidate install is accepted and records
its version. This uses a mocked interpreter and package manager; it does not
prove a full network install, successful import, or service startup on Python
3.14. Those remain candidate qualification gates.

## Overlay review state

The overlay inventory records several 0.21.6 native capabilities already
exercised in focused workspace/runtime comparisons, including authenticated
workspace tooling and native working-diff collection. HADES retains its own
subject authentication, authorization, and per-turn scope filtering where
upstream does not provide the required HADES boundary. The full responsibility-
by-responsibility clean-Hermes comparison remains open; see
[`hermes-overlay-inventory.md`](hermes-overlay-inventory.md).

## Remaining gates

- Install the pinned 0.21.6 archive through the revised installer on a clean
  Python 3.14 environment, then verify provenance, locked dependency sync,
  imports, service startup, and restart behavior.
- Finish the overlay responsibility audit and disable each candidate shim in
  turn before deciding whether native behavior replaces it.
- Complete owner-visible authenticated acceptance and compare ordinary chat,
  memory, tools, and workspace behavior before promotion.
