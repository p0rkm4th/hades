# Hermes Runtime Artifact Contract

## Current authoritative checkpoint — 2026-10-13

Runtime source commit `7ab2cf2b3c0d0ba3ca363a3be9ad6af3a1ee5e59` was
fast-forwarded to canonical `main`. Candidate Public CI run `38357042859` and
post-promotion main run `38357817633` both passed.

Production runs Hermes 0.21.2 in `hades-hermes.service`. The service-selected
Python import and the installed
`generated-full/config/overlay/sitecustomize.py` are both SHA-256
`d0b6b03f73fb140dcd33f4bdb0511af04682280e4dfe9476b5b458b701721756`. The
runtime manifest ID is
`1471cd606cf99cd44344e11c999c2e0c7a7856cdf5e57c88c32aa79dae98f633`; its
file SHA-256 is
`b3f23992483f0039ca3cc41b9676aea3d1f486f97f1a67fde18e3c3d86da52a9`. The
manifest binds HADES commit `7ab2cf2b3c0d`, Hermes 0.21.2, the source and
builder hashes, and the approved deployment configuration fingerprints.
`verify-live` reports `EXPECTED`; the service is active and `/health` passes.

The running file is a byte-identical copy of tracked
`hermes/sitecustomize.py`, built by `scripts/hermes-runtime-artifact.py`.
The old deployment overlay at checksum `cda3b3556a24dce439b5a8f718f1ab51d89a208235df3acb3b59b750f5664d49`
is preserved as a metadata-verified rollback artifact under the protected
deployment backup root. The inactive Hermes installation-root copy and stale
reconciled-checkout copy remain unused; no second active import path is
configured.

The synthetic production UI smoke passed ordinary chat, kitchen stock, named
Grocy recipe, homelab follow-up, finance calculation, and safe Palworld
capability handling. The seven temporary chats were deleted and verified
absent from the acceptance owner's chat list. No tool-call records appeared
in the chats; the synthetic actor is excluded from automatic retention, and
the read routes invoked no write capability. Protected response-hash and
cleanup evidence is in the local HADES state directory; it contains no
response payloads.

The first deployment attempt exposed a readiness race: a single health probe
ran before Hermes had bound its port. The checksum-guarded installer restored
the exact previous overlay; the old runtime then became healthy and its loaded
checksum was verified. Both deploy and rollback now wait up to 60 seconds for
service health. The subsequent deployment passed identity and health checks.

## Historical pre-convergence checkpoint — before 7ab2cf2b deployment

Runtime convergence is active on branch `codex/runtime-convergence-20261013`,
based on HADES `2d4a702d8c9eef3ce99280e6dd45a1b47a5e36a5`.

The Hermes service is `hades-hermes.service`, running Hermes 0.21.2 through
the configured Hermes 0.21.2 virtualenv Python with
`python -m hermes_cli.main`. Its `PYTHONPATH` selects the active
`generated-full/config/overlay/sitecustomize.py`. A probe
using that interpreter and service environment reported the same
`sitecustomize.__file__` and bytes as the running installation. The process
started after the file's last change time. The active file SHA-256 is
`cda3b3556a24dce439b5a8f718f1ab51d89a208235df3acb3b59b750f5664d49`.

The tracked source at the checkpoint is 757,504 bytes with SHA-256
`2131b75cdc5363c0638bef287c626b669002a9e70624061c68c7e0fa271e4be0`. The
active generated overlay is 802,106 bytes. A structural comparison found 50
shared top-level functions with different bodies, 31 active-only definitions,
and 45 source-only definitions. The latest active-only patch relative to its
exact prior backup is the named-recipe production shortcut; canonical source
already implements that owner fix. The active overlay is therefore not a
reproducible build of the current source.

Other copies:

| Artifact | Current role |
|---|---|
| `hermes/sitecustomize.py` in canonical Git | Runtime source |
| Generated deployment `config/overlay/sitecustomize.py` | Active runtime, currently drifted |
| Hermes install root `sitecustomize.py` | Not selected by the service's import path; inactive legacy copy |
| Reconciled checkout `hermes/sitecustomize.py` | Stale checkout copy; not selected by the service |
| `generated-full/backups/*/sitecustomize.py` | Historical rollback snapshots; only the new runtime deployment backup is the immediate rollback |

The existing Epsilon provenance endpoint currently reports HADES `bcd81f4`
and overlay `1863ed…`; that record is stale and does not identify the active
overlay. Do not use it as current runtime truth. The new bounded verifier below
reports the process, selected import file, installed checksum, source manifest,
and Hermes version together.

## Production-only delta disposition

The active overlay is a historical generated-full artifact, not a second
current source tree. Its exact pre-shortcut backup is preserved in the
protected deployment backup area. A comparison against that backup found one
16-line named-recipe shortcut; the corresponding operation is now in tracked
source and covered by the Grocy operation tests.

The active file also contains older homelab/backup presentation helpers that
are absent by name from current source. Their migration dispositions are:

| Active-only group | Current source path | Disposition |
|---|---|---|
| Backup and guest inventory presentation | `_hades_direct_proxmox_backup_status`, `_hades_direct_homelab_guest_inventory_read`, and current homelab read adapters | Historical implementation residue; qualify against bounded backup, guest, and owner homelab contracts before deployment |
| Node, workload, and resource presentation | Current homelab follow-up, node status, capacity, and resource adapters | Historical implementation residue; current source owns these operations |
| Network diagnostic detail | Current per-turn classifier preserves performance intent, keeps it out of the broad-summary shortcut, and returns fresh probe/runtime detail with limits | Required live behavior; now represented in canonical source and covered by routing plus health contracts |
| Source/visibility explanations | Current provenance and household boundary responses | Historical implementation residue; preserve current authority and redaction contracts |
| Model-fit and GPU presentation | Current provider-native inference and bounded GPU read paths | Historical implementation residue; no deployment-only authority is intended |
| `_hades_p1_finance_merchant_calculation` | Deterministic merchant-period aggregation inside `_hades_direct_finance_guidance` | Duplicate production wrapper; current source owns row filtering, signed totals, pending separation, and coverage semantics |
| `_hades_runner_has_workflow` | No current source caller; no current contract depends on this helper | Stale helper, removable with the old overlay |

The candidate is the tracked canonical source, not a splice of these legacy
helpers. Public CI and focused source contracts qualify it; production
replacement remains gated on CI, runtime identity, and bounded synthetic
smoke. The exact prior artifact and its metadata remain the rollback. This
disposition is recorded so the migration does not depend on an unrecorded
judgment.

## Supported artifact path

`scripts/hermes-runtime-artifact.py` is the only supported source-to-runtime
builder. It emits a byte-identical copy of tracked `hermes/sitecustomize.py`
and a deterministic JSON manifest. The manifest binds HADES commit and tree,
Hermes version, source/artifact checksum, builder source checksum, and hashes of
explicit deployment configuration inputs. It contains no build timestamp.
Changing any input changes the manifest ID; changing the source changes both
the artifact and its checksum.

The `hermes-overlay-composition.py` and `prepare-*-overlay-candidate.py`
utilities remain for bounded migration/test cases. They are not the production
runtime build path. Production runtime logic must be tracked in canonical
source before deployment.

From a clean checkout, fingerprint approved private configuration inputs on
the HADES host. The command prints only labels and hashes, never file contents:

```sh
sudo python3 scripts/hermes-runtime-artifact.py fingerprint \
  --config-input systemd-unit=/etc/systemd/system/hades-hermes.service \
  --config-input hermes-environment="$HADES_HERMES_ENV_FILE" \
  --config-input hermes-profile="$HERMES_HOME/profiles/hades/config.yaml"
```

Pass those `NAME=sha256:HEX` values to the builder in a clean Git worktree:

```sh
install -d -m 0700 /tmp/hades-runtime
python3 scripts/hermes-runtime-artifact.py build \
  --source-repo "$PWD" \
  --hermes-version 0.21.2 \
  --config-input systemd-unit=sha256:<fingerprint> \
  --config-input hermes-environment=sha256:<fingerprint> \
  --config-input hermes-profile=sha256:<fingerprint> \
  --artifact /tmp/hades-runtime/sitecustomize.py \
  --manifest /tmp/hades-runtime/sitecustomize.runtime.json

python3 scripts/hermes-runtime-artifact.py verify \
  --source-repo "$PWD" \
  --hermes-version 0.21.2 \
  --config-input systemd-unit=sha256:<fingerprint> \
  --config-input hermes-environment=sha256:<fingerprint> \
  --config-input hermes-profile=sha256:<fingerprint> \
  --artifact /tmp/hades-runtime/sitecustomize.py \
  --manifest /tmp/hades-runtime/sitecustomize.runtime.json
```

The release deployment script is
`scripts/deploy-hermes-runtime-overlay.sh`. It is deliberately pinned to the
qualified Hermes 0.21.2 service. Set `HADES_GENERATED_ROOT`,
`HADES_HERMES_ENV_FILE`, `HERMES_HOME`, and `HADES_HERMES_PYTHON` from the
approved private deployment configuration; do not put their values in Git. It
verifies the expected pre-state and both candidate hashes, saves an exact
metadata-preserving rollback copy, installs by same-filesystem rename, restarts
Hermes, verifies the loaded module path/checksum/version and health, and
restores the old artifact if any check fails.
`scripts/rollback-hermes-runtime-overlay.sh` performs an explicit
checksum-guarded rollback from that backup. Run these through the existing
approved scoped privilege path; neither script changes sudo or SSH policy.

The Hermes health URL is resolved on the HADES host from the existing Open
WebUI container's `host.docker.internal` mapping. Keep that address in a shell
variable; do not print it into public evidence. A deployment invocation has
this shape:

```sh
overlay_dir="$HADES_GENERATED_ROOT/config/overlay"
hermes_host=$(docker exec hades-open-webui getent hosts host.docker.internal | awk 'NR==1 {print $1}')
sudo bash scripts/deploy-hermes-runtime-overlay.sh \
  --candidate /tmp/hades-runtime/sitecustomize.py \
  --manifest /tmp/hades-runtime/sitecustomize.runtime.json \
  --target "$overlay_dir/sitecustomize.py" \
  --manifest-target "$overlay_dir/sitecustomize.runtime.json" \
  --expected-current-sha256 <current-active-sha256> \
  --expected-candidate-sha256 <candidate-sha256> \
  --expected-manifest-sha256 <manifest-sha256> \
  --rollback-dir "$HADES_GENERATED_ROOT/backups/runtime-convergence-<hades-sha12>" \
  --service hades-hermes.service \
  --python "$HADES_HERMES_PYTHON" \
  --health-url "http://$hermes_host:8642/health" \
  --config-input systemd-unit=/etc/systemd/system/hades-hermes.service \
  --config-input "hermes-environment=$HADES_HERMES_ENV_FILE" \
  --config-input "hermes-profile=$HERMES_HOME/profiles/hades/config.yaml"
```

Explicit rollback supplies the active candidate checksum and the saved pre-state
checksum:

```sh
sudo bash scripts/rollback-hermes-runtime-overlay.sh \
  --target "$overlay_dir/sitecustomize.py" \
  --manifest-target "$overlay_dir/sitecustomize.runtime.json" \
  --rollback-dir "$HADES_GENERATED_ROOT/backups/runtime-convergence-<hades-sha12>" \
  --expected-current-sha256 <currently-installed-candidate-sha256> \
  --expected-rollback-sha256 <saved-prestate-sha256> \
  --service hades-hermes.service \
  --python "$HADES_HERMES_PYTHON" \
  --health-url "http://$hermes_host:8642/health"
```

After deployment, the bounded live identity command is:

```sh
sudo python3 scripts/hermes-runtime-artifact.py verify-live \
  --artifact "$HADES_GENERATED_ROOT/config/overlay/sitecustomize.py" \
  --manifest "$HADES_GENERATED_ROOT/config/overlay/sitecustomize.runtime.json" \
  --installed "$HADES_GENERATED_ROOT/config/overlay/sitecustomize.py" \
  --service hades-hermes.service \
  --python "$HADES_HERMES_PYTHON" \
  --config-input systemd-unit=/etc/systemd/system/hades-hermes.service \
  --config-input hermes-environment="$HADES_HERMES_ENV_FILE" \
  --config-input hermes-profile="$HERMES_HOME/profiles/hades/config.yaml"
```

It reports `EXPECTED` only when the manifest, candidate, installed file,
service-selected Python import, process start time, configuration fingerprints,
and Hermes version agree. It reports `DRIFTED` on a known mismatch and fails
closed when process identity is unavailable. The process-start check ensures
the installed bytes were already present when the current Hermes interpreter
started; the import probe independently confirms Python's actual selection for
that same executable and environment.

## Deployment gate

Do not deploy until the candidate commit's hosted Public CI is green. Before
installation, verify that the current active SHA still matches the recorded
pre-state. If it differs, stop and rebuild the comparison against the new live
artifact. After installation, require `verify-live`, Hermes health, bounded
synthetic chat/memory/Grocy/homelab/finance smoke, and the compact owner
regression set. Production changes only the Hermes overlay and its private
runtime manifest; no model, Open WebUI, or broad memory rollout changes are in
scope.

Historical inventory entries below remain evidence of prior states. They do
not override this current source-to-runtime contract.
