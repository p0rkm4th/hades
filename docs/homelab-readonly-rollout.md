# Homelab read-only runtime rollout

This procedure updates the owner-only homelab read path on an existing HADES
Core guest. It uses the canonical `install-hades.sh` path so the selected
Hermes overlay, homelab view module, install marker, generated service unit,
and other installed HADES layer files stay bound to one source revision. It
does not change Proxmox, NetBox, Kuma, host accounts, keys, ACLs, network
settings, or inference nodes.

Use this only after the exact candidate's Public CI and public tree/history
safety checks pass. The selected source checkout must be clean at the approved
commit. Do not identify a deployment by a moving branch name.

## Requirements

- Root access to the HADES Core guest through its approved operator procedure.
- A clean HADES checkout at the exact candidate SHA on that guest.
- That checkout must be the path configured as
  `HADES_HERMES_WORKING_DIRECTORY`. The installer checks that the runtime
  working-directory adapter package matches its source checkout; the doctor
  and provenance writer bind the selected MCP entrypoint to that same source.
  Stop if the configured working directory differs. Do not copy one package
  over another checkout or claim parity across unrelated revisions.
- Protected operator inputs and private Hermes profile available through the
  existing deployment. Do not print secrets or dump the process environment.
  Keep shell tracing disabled.
- A root-only backup location with enough space for the active Hermes profile,
  install-managed HADES layer, generated deployment records, service unit,
  install marker, and source checkout rollback metadata.

Before using this procedure, inspect optional Agent Zero state without changing
it. Require `HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED=false`, no installed or
enabled `hades-agent-zero-operator-auth.service`, and no running or stopped
`hades-agent-zero-operator-proxy` container (check all containers, not only
running ones). Require no symlink at
`$HADES_CONFIG_ROOT/operator-proxy`, and no files or symlinks beneath that
path. Require no ACL entry for the Hermes runtime UID on `$HADES_CONFIG_ROOT`,
no `HADES_AGENT_ZERO_CREDENTIAL_FILE` or
`HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE` input, and no active
`agent-zero-client-auth.env`. Require the generated
`$HADES_DEPLOYMENT_DIR/agent-zero-client-auth.env` path itself to be absent,
including symlinks. Also require these optional generated records to be absent
from `$HADES_DEPLOYMENT_DIR`: `agent-zero-operator-proxy.env`,
`agent-zero-operator-proxy.compose.yaml`, `agent-zero-operator-auth.env`, and
`agent-zero-operator-auth.service`. The renderer removes these paths when their
corresponding inputs are disabled. If optional proxy or client-auth state is
active/configured, stop; this homelab-only procedure does not authorize
changing it.

The canonical installer recursively normalizes Hermes profile ownership and
modes and recursively assigns Hindsight data ownership to UID/GID 1000. Before
rollout, inventory those trees with `lstat` semantics and require the operations
to be no-ops: every Hermes profile object is owned by the configured runtime
UID/GID; directories are mode 0700; regular files have no group/other bits;
regular files and directories have no setuid/setgid/sticky bits; symlinks have
the expected runtime owner/group. Hindsight data root must already exist as a
directory. Every Hindsight data object, including symlinks and the root
directory, must already be UID/GID 1000, and regular files/directories must
have no setuid/setgid/sticky bits. Require no named or default ACL entries in
either tree, because the profile chmod pass must not change ACL masks. Stop if
any object would change. This
procedure does not back up application data or authorize recursive permission
repair.

## 1. Identify the live runtime

Set `HADES_REPO` to the checkout configured as the Hermes working directory,
`HADES_SHA` to the approved full candidate commit, and `OPERATOR_INPUTS` to the
protected input file. Resolve the running Hermes MainPID, command line,
working directory, named profile selection, and required environment fields
without dumping unrelated values. Record the current source HEAD as
`PREVIOUS_HADES_SHA`. Confirm the runtime working directory equals `HADES_REPO`,
exactly one `-p hades` selector is active, `HERMES_HOME` matches the configured
Hermes home, and the selected profile is
`HERMES_HOME/profiles/hades/config.yaml`.

    set -euo pipefail
    set +x
    : "$HADES_REPO"
    : "$HADES_SHA"
    : "$OPERATOR_INPUTS"
    REPO_OWNER=$(stat -c '%U' "$HADES_REPO")
    run_git() { runuser -u "$REPO_OWNER" -- git -C "$HADES_REPO" "$@"; }

Record privately the actual active unit path, Hermes home, selected profile,
profile environment file, active overlay and composition manifest, install
marker, configuration root, state root, generated deployment directory, and
all paths the installer will update. Do not assume historical paths remain
current. Record the previous source revision and tree for rollback.

In the selected profile, the enabled `homelab-readonly` registration must
point to the candidate working-directory source package:

    ${HADES_HERMES_WORKING_DIRECTORY}/integrations/homelab-readonly/server.py

Preserve unrelated profile settings. Do not select a stale generated package
under another integration root for this rollout. The installer, doctor, and
provenance checks must all resolve the same candidate package.

## 2. Prepare protected rollback copies

Before changing the source checkout or private profile, create a new root-owned
mode-0700 backup directory with a unique deployment ID. Never overwrite an
earlier backup. Save hashes, ownership, and modes in a protected record. Back
up at least:

- the selected Hermes profile file and the profile environment file;
- the installed overlay and composition manifest;
- `overlay/homelab_views.py`, installed adapters and web assets;
- installed versions and reconstruction manifests;
- the Hermes systemd unit and every generated HADES deployment record that
  will be rewritten from the supplied operator inputs;
- `$HADES_CONFIG_ROOT/searxng/settings.yml`, because the canonical installer
  regenerates this active SearXNG settings file from the protected secret;
- the install marker at `HADES_STATE_ROOT/install-contract`;
- the previous source revision/tree and the prior selected adapter identity.

Do not copy secrets to a public location or print their values. Preserve the
existing native data volumes; this application-layer rollout does not back up
or replace household database contents. The Hermes-profile and Hindsight
metadata preconditions above ensure recursive installer normalization does not
change those trees. The Agent Zero precondition ensures its disable/removal
branch and client-auth deletion branch have no applicable live state.

Check that all active targets still match the captured backup hashes before
continuing. If any target changed during preparation, stop and recapture the
live state.

## 3. Stage the exact source revision

If the checkout is not already at `HADES_SHA`, require its entire worktree,
including untracked files, to be clean. Do not stash, reset, or clean local
work. If it is dirty, stop and resolve ownership of that work before rollout.
Stop Hermes before changing code in its live working directory, then fetch and
check out only the approved immutable SHA:

    test -z "$(run_git status --porcelain=v1 --untracked-files=all)"
    systemctl stop hades-hermes.service
    run_git fetch origin "$HADES_SHA"
    run_git checkout --detach "$HADES_SHA"
    test "$(run_git rev-parse HEAD)" = "$HADES_SHA"
    test -z "$(run_git status --porcelain=v1 --untracked-files=all)"

Use the checkout's designated repository owner for Git operations and preserve
the runtime account's read/traverse access. Do not recursively change checkout
ownership. If fetching the commit or preserving those permissions fails,
restore `PREVIOUS_HADES_SHA` with `run_git checkout --detach` while Hermes
remains stopped, then start the prior service and stop the rollout.

## 4. Compose over the freshly captured active overlay

Set protected shell variables for the active overlay, staged output, manifest,
operator input file, and deployment directory. Compose the two supported
homelab wrapper definitions from this exact candidate over the freshly
captured active overlay:

    python3 "$HADES_REPO/scripts/prepare-homelab-overlay-candidate.py" \
      --repo "$HADES_REPO" \
      --active-overlay "$ACTIVE_OVERLAY" \
      --output "$OVERLAY_CANDIDATE" \
      --manifest-output "$OVERLAY_MANIFEST"

Review the diff. It must change only the two supported wrapper definitions and
preserve every other deployment-local overlay byte. Verify that the composition
manifest binds the candidate source revision, source tree, active base hash,
final overlay hash, and wrapper hashes. Stop if the base changed, composition
verification fails, or the diff contains unrelated policy.

Prepare the selected profile change in a protected staging file. Change only
the `homelab-readonly` args from its previous path to the supported
`${HADES_HERMES_WORKING_DIRECTORY}/integrations/homelab-readonly/server.py`
entrypoint. Review the exact diff and retain the backup copy.

Before applying, render candidate deployment records into a protected staging
directory using the existing record renderer. Set `STAGING_CONFIG_ROOT` to a
new private staging directory and pass it explicitly so preflight cannot
rewrite active SearXNG settings:

    install -d -m 0700 "$STAGING_CONFIG_ROOT"
    bash "$HADES_REPO/scripts/render-deployment-records.sh" \
      "$OPERATOR_INPUTS" "$RECORDS_CANDIDATE" \
      --searx-settings-root "$STAGING_CONFIG_ROOT"

Compare the staged SearXNG settings and rendered non-Hermes Compose records
with their active equivalents after ignoring generated header metadata. Stop
if their effective configuration changes; this rollout must not silently
alter unrelated service configuration. The installer will render records
again from the same protected inputs and intentionally update the active
SearXNG settings file.

## 5. Apply through the canonical installer

Immediately before applying, verify that the active profile, overlay,
composition manifest, install marker, service unit, generated records, and
active SearXNG settings still have the captured preflight hashes. Install the
reviewed profile file atomically with its recorded owner and mode.

Run the canonical installer with the same protected inputs and the exact
composed overlay plus manifest:

    bash "$HADES_REPO/scripts/install-hades.sh" \
      --inputs "$OPERATOR_INPUTS" \
      --hermes-overlay-candidate "$OVERLAY_CANDIDATE" \
      --hermes-overlay-manifest "$OVERLAY_MANIFEST"

The installer updates the installed HADES layer, including
`overlay/homelab_views.py`, writes the install marker for this exact source
and manifest, renders the Hermes unit and generated deployment records, and
performs its normal idempotent service reconciliation. Do not manually replace
individual runtime files or hand-edit the marker. Do not run a second Compose
or systemd restart command after it succeeds.

If installer output shows an unexpected change to non-Hermes service
configuration, stop and roll back. Its regular pinned service reconciliation
may report unchanged containers as already running; record any actual
recreation and reason.

## 6. Verify source, runtime, and owner boundaries

Run the candidate validator and doctor with the protected inputs:

    bash "$HADES_REPO/scripts/validate-install.sh" --inputs "$OPERATOR_INPUTS"
    bash "$HADES_REPO/scripts/hades-doctor.sh" --inputs "$OPERATOR_INPUTS"

Both must pass. Confirm the running process command line/profile, Hermes home,
working directory, overlay environment, selected MCP package, and install
marker all identify the approved candidate. Confirm the running process has
the expected service environment without printing secret values.

Generate deployed provenance from the exact HADES and private infra source
checkouts. Supply protected values for `INFRA_REPO`, `INFRA_SHA`,
`HERMES_VERSION`, `HERMES_EXECUTABLE`, `ACTIVE_OVERLAY`, `OVERLAY_MANIFEST`,
`INSTALL_MARKER`, `HERMES_PROFILE`, `TASK_STORE`, and `PROVENANCE_OUTPUT`:

    python3 "$HADES_REPO/scripts/write-deployed-provenance.py" \
      --output "$PROVENANCE_OUTPUT" \
      --hades-sha "$HADES_SHA" \
      --source-repo "$HADES_REPO" \
      --infra-repo "$INFRA_REPO" \
      --infra-sha "$INFRA_SHA" \
      --hermes-version "$HERMES_VERSION" \
      --hermes-executable "$HERMES_EXECUTABLE" \
      --overlay "$ACTIVE_OVERLAY" \
      --overlay-composition-manifest "$OVERLAY_MANIFEST" \
      --install-marker "$INSTALL_MARKER" \
      --hermes-profile "$HERMES_PROFILE" \
      --task-store "$TASK_STORE" \
      --manifest "$HADES_REPO/config/reconstruction-manifest.json" \
      --deployment-path "$HADES_DEPLOYMENT_DIR" \
      --service hades-hermes.service

Both source checkouts must be clean at the supplied revisions. If a clean
private infra revision is unavailable, keep provenance and source/runtime
parity open rather than substituting an unverified value. Keep provenance
protected because it contains deployment identity and paths.

Check the Hermes health endpoint using the current documented local health
path. Run fresh authenticated owner and Household A/B prompts. Owner answers
must show current evidence and uncertainty honestly. Household answers must
remain abstract and hide host, service, address, model placement, and owner-only
infrastructure detail. Run affected no-dispatch, source-outage, and
service-health regressions. Record timestamps/results without copying raw
private answers into public docs.

## 7. Roll back on any failed gate

Stop if profile/package identity is ambiguous, provenance differs,
doctor/validator/health/UI checks fail, or effective non-Hermes service
configuration changed. Before restoring, verify that every changed active file
still has the hash recorded for this rollout; if any differs, stop for
operator review.

Stop Hermes if it is running. Restore the previous source checkout revision
only when its worktree remains clean. Restore the selected profile, installed
HADES layer and overlay manifest, generated deployment records, Hermes unit,
SearXNG settings, and install marker from the root-only backup with their
recorded ownership and modes. Since recursive ownership/mode operations were
proven no-ops before applying, Hermes-profile and Hindsight metadata remain as
captured. Since optional Agent Zero state was proven absent, rollback needs no
proxy/client-auth reconstruction. Run `systemctl daemon-reload`, start Hermes,
and verify the previous health and source identity. Do not alter unrelated
containers, data volumes, or infrastructure sources during rollback.

Keep the failed candidate and its package/build evidence for diagnosis. Do not
delete unrelated deployment files.

## Evidence boundary

This procedure does not establish real-source coverage, owner acceptance,
household acceptance, or off-host recovery by itself. Track each separately.
Keep private infrastructure, operator inputs, profile, package hashes, backup
location, and raw owner/household responses in protected records. Public HADES
documentation should report only sanitized source revision, CI run, outcome,
and remaining gaps.
