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
- Hermes build tool pin: uv 0.12.15. The official uv release page now lists
  0.12.24 (released 2026-10-08) as latest. Its notes include package-hash
  verification fixes and workspace-cache fixes. **INVESTIGATE** this build-tool
  refresh separately: 0.12.15 has just completed the exact candidate install,
  while 0.12.24 has not yet been exercised against HADES' locked install path.

Authoritative sources: [Hermes Agent releases](https://github.com/NousResearch/hermes-agent/releases),
[v0.21.6 pyproject.toml](https://github.com/NousResearch/hermes-agent/blob/v0.21.6/pyproject.toml),
[v0.21.6 Hindsight plugin catalog record](https://github.com/NousResearch/hermes-agent/blob/v0.21.6/plugin-catalog/hindsight.yaml),
and the [uv 0.12.15 release](https://github.com/astral-sh/uv/releases/tag/0.12.15).

## Decision

**INVESTIGATE / STAGE; do not promote yet.** The staged 0.21.6 pin is the
current stable and matches the version used in recent PLAIN STACK/HADES
workspace comparisons. Those comparisons establish a useful source-level
behavior sample, not a full installation or deployed-runtime qualification.
Production remains at 0.21.2 pending the broader Hermes overlay and owner
acceptance gates.

## HADES compatibility finding and repair

The installer initially rejected all Python 3.14 interpreters, even for
Hermes 0.21.6. After allowing that candidate version, a real install exposed a
second mismatch: Hermes 0.21.6 removed the `hindsight` optional extra. Its
official `plugin-catalog/hindsight.yaml` instead points to the Hindsight-owned
Hermes integration (catalog version 1.2.1, commit `d56c4ac`, requiring Hermes
`>=0.21.4`). The installer now uses versioned dependency profiles: 0.21.2
retains its upstream `hindsight` extra, while 0.21.6 installs the locked
`all` profile and leaves the separately managed memory plugin to the plugin
catalog.

A third issue was visible after installation: source archives have no `.git`
directory, and Hermes deliberately reports an unknown version without its
native `install-stamp.json`. The installer now invokes Hermes 0.21.6's own
`scripts/write_install_stamp.py` with the pinned commit, version, and external
update owner. The CLI now reports `Hermes Agent v0.21.6 ... upstream 818c13be`
instead of an unknown version. The stamp and adjacent HADES provenance file
both identify the exact source commit and artifact hash.

A real temporary installation then passed on Python 3.14.7 using the exact
Hermes archive SHA above and uv 0.12.15. The official uv release asset digest
was verified as
`f97935763c04be3e692460a7aaeaaab8fc3b78fcf8b389da820b38ae7423a638`. Locked
sync installed 106 packages; `import hermes_cli.main` passed and the generated
Hermes command ran. Artifact provenance recorded source version 0.21.6 and the
expected archive SHA. The temporary install/cache was removed when the run
ended.

The focused installer contract checks both dependency profiles and the
Python boundary: 0.21.2 remains rejected on Python 3.14 and retains its
Hindsight extra, while 0.21.6 is accepted, omits that obsolete extra, and
stamps the pinned identity. This proves the candidate artifact install/import
path, not HADES overlay startup, plugin installation, or service/restart
behavior.

## Overlay review state

The overlay inventory records several 0.21.6 native capabilities already
exercised in focused workspace/runtime comparisons, including authenticated
workspace tooling and native working-diff collection. HADES retains its own
subject authentication, authorization, and per-turn scope filtering where
upstream does not provide the required HADES boundary. The full responsibility-
by-responsibility clean-Hermes comparison remains open; see
[`hermes-overlay-inventory.md`](hermes-overlay-inventory.md).

## Remaining gates

- Resolve the CLI's `vunknown` display for archive installs, then verify HADES
  overlay startup, plugin installation, service startup, and restart behavior.
- Finish the overlay responsibility audit and disable each candidate shim in
  turn before deciding whether native behavior replaces it.
- Complete owner-visible authenticated acceptance and compare ordinary chat,
  memory, tools, and workspace behavior before promotion.
