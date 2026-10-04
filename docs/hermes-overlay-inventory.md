# Hermes Compatibility Overlay Inventory

`hermes/sitecustomize.py` is a deployment overlay, not a HADES runtime. Each
behavior below has an explicit reason to exist and a removal condition. The
overlay must be re-evaluated whenever the pinned Hermes version changes.

| Behavior | Upstream gap or deployment constraint | Evidence / regression check | Removal condition |
|---|---|---|---|
| Register packaged SearXNG at startup | Lazy plugin discovery can race legacy web-tool resolution | Composition smoke check and Hermes health | Upstream discovery is deterministic and web-search owner workflow passes without it |
| Make Hindsight retain asynchronous | Synchronous local extraction can exceed chat timeout while Ollama shares the GPU | Hindsight/API tests and owner memory persistence workflow | Upstream retain is asynchronous by default and latency/persistence pass without the patch |
| Bound and normalize Hindsight retain/recall | Small models can recurse through reflection or surface duplicate, low-specificity facts | Memory regression plus fresh owner recall/correction evidence | Upstream offers the same bounded tool/result contract and fresh owner workflow passes |
| Reconcile and narrow Grocy MCP tools | Production Hermes 0.14.0 can construct an API agent before dynamic MCP discovery; mixed prompts need least privilege | Grocy canonical-state workflows and memory/household composition; clean Hermes v0.21.2 staging with its declared `mcp` extra registered and invoked a synthetic MCP tool through `tool_search` → `tool_call` | Migrate to an upstream version/configuration with the declared MCP extra, prove the full Grocy owner matrix and restart behavior, then delete this production-only reconciliation path |
| Route external-source and memory intents to a tool-capable model | Current completion-only/weak local models are unsuitable for reliable tool calls | Model capability registration and owner model/tool workflows | Upstream capability routing provides equivalent behavior |
| Isolate completion-only creative models from HADES tools | Uncensored/creative models are intentionally tool-less | Owner model-picker labels and no-tool workflow | A reviewed safety policy explicitly replaces this deployment boundary |
| Preserve authoritative Hindsight output in streamed turns | Some local models emit a misleading continuation after a successful memory call | Memory regression and mobile DOM recall/correction evidence | Upstream streaming preserves the authoritative tool result |

The subject-scope resolver also re-runs the strict session-key validator before
assigning owner or household scope. Invalid, empty, or untrusted keys therefore
remain denied rather than inheriting ordinary household capability. This is a
fail-closed security invariant, not candidate-specific cosmetic behavior.

Overlay initialization remains optional for upstream-only Hermes environments.
When `HADES_HERMES_EXECUTABLE` is configured, the current shim skips only the
expected missing-`hindsight_client` import in a child Python interpreter that
is not the Hermes executable, and records that skip at debug level. Other
initialization exceptions emit an explicit `hades.overlay` error. Operators
must treat that diagnostic as an unavailable HADES policy layer rather than as
a healthy HADES deployment; production promotion and owner traffic require the
overlay to initialize cleanly. The recovered production overlay predates this
child-interpreter exception and logs initialization failures as errors.

## Extraction record — 2026-10-01

The read-only workflow-presence probe used only during uncertain Backup Check
deletion recovery has moved from `hermes/sitecustomize.py` to
`integrations.automation.workflow_presence`. It returns `True` or `False` only
when the runner listing is available and returns `None` when listing fails, so
an outage cannot be mistaken for proof of deletion. The overlay retains the
recovery policy call; the domain contract owns the runner query. Regression
coverage is in `scripts/test-automation-workflow-presence.sh`, included in
Public CI. Hosted branch and main runs `36900909782` and `36901194602` passed
all 105 workflow commands. The overlay is still large and requires further
one-responsibility-at-a-time review.

## Review rule

No behavior is removed solely because an upstream test suite passes. Its
removal condition must include the affected HADES owner workflow, canonical
backend verification where applicable, and reload/restart persistence when it
affects state. Production remains pinned while the full external-contract
matrix is not isolated from authoritative owner data.

## Deployment drift check

The running profile loads the overlay from its installed `PYTHONPATH` copy;
repository changes do not update that copy automatically. Before restarting
Hermes after an overlay change, run the read-only check with the operator-known
installed path:

```text
bash scripts/verify-live-hermes-overlay.sh /path/to/installed/sitecustomize.py
```

If an installed overlay has additional deployment-local code and differs from
the repository file, do not replace the whole file. Create a candidate that
replaces only the HADES direct-memory function while preserving every other
byte in the installed overlay copy:

```text
python3 scripts/prepare-hindsight-overlay-candidate.py \
  --active-overlay /path/to/copied/installed/sitecustomize.py \
  --output /path/to/new/sitecustomize.py
```

The candidate is mode `0600`, refuses to overwrite a file, validates syntax,
and reports the before/source/candidate SHA-256 values. Run the Hindsight
explicit-memory contract with `HADES_HINDSIGHT_OVERLAY_SOURCE` set to the
candidate, and run the pinned-service runtime contract before installing it.
Review the exact diff, keep a verified rollback copy of the active overlay, and
check service health after restart. This helper only prepares a file; it does
not access or modify a host.

The check compares bytes and validates syntax without modifying either file.

After the installed overlay has been synchronized, Hermes restarted, and the
service health checked, refresh the machine-readable runtime record with the
same installed overlay and manifest that were just validated:

```text
python3 scripts/write-deployed-provenance.py \
  --output /path/read-by/hades-epsilon-source/hades-live-provenance.json \
  --hades-sha <deployed-40-character-HADES-commit> \
  --source-repo /path/to/clean/deployed/HADES/git-checkout \
  --infra-sha <deployed-40-character-infrastructure-commit> \
  --infra-repo /path/to/clean/deployed/hades-infra/git-checkout \
  --hermes-version <running-Hermes-version> \
  --hermes-executable /path/to/the/configured/hermes \
  --overlay /path/to/installed/sitecustomize.py \
  --hermes-profile /path/to/HERMES_HOME/profiles/hades/config.yaml \
  --task-store /path/to/deployed/HADES/integrations/task/store.py \
  --manifest /path/to/deployed/config/reconstruction-manifest.json \
  --epsilon-manifest /path/to/deployed/config/epsilon-source/phase3-runtime-manifest.json \
  --deployment-path /path/to/deployed/HADES/runtime \
  --service hades-hermes.service
```

The writer checks that `--source-repo` and `--infra-repo` are clean Git
worktrees at exactly `--hades-sha` and `--infra-sha`; it records both Git tree
hashes. The deployed TaskStore and reconstruction manifest must match files
from the HADES source revision.
It checks that the service is active and matches `--hermes-executable` to the
running process. For units with `HADES_HERMES_EXECUTABLE`, it also checks that
the path matches the unit and that its live `--version` output contains the
claimed version. For the legacy `python -m hermes_cli.main` unit, it verifies
that exact module entrypoint and reads the `hermes-agent` package version from
the same interpreter. The provenance record includes the resolved executable
path, SHA-256, and runtime kind. It also checks that `--overlay` is the
`sitecustomize.py` selected by that unit's effective `PYTHONPATH`. It refuses
to write a record when the supplied path differs. It also hashes the deployed
TaskStore source so task-route behavior has an artifact identity. The required
`--hermes-profile` must resolve to `HERMES_HOME/profiles/<name>/config.yaml`,
where `<name>` is selected by the running Hermes process's `-p` or `--profile`
argument. Only its SHA-256 is added to the record; profile contents, private
endpoints, and secret references are not returned. This distinguishes
deployments that share code but use different MCP registrations or activation
settings. The record's private `mcp_runtime` list identifies enabled local MCP
source paths and hashes, external executable hashes, and HTTP endpoint hashes.
It fails if a local script is outside the clean HADES checkout or differs from
the claimed revision. The provenance endpoint exposes only the aggregate
`mcp_runtime_sha256`; it does not return private endpoint values. An HTTP
endpoint hash identifies the configured destination but does not attest the
service image behind that destination; container identity must still be
verified separately. When Epsilon is packaged, pass its generated package
manifest so the record binds the exact
fixed-reader/dispatcher source bundle. Refresh the record whenever that
package is regenerated. The output path must be the exact file configured for
the provenance service.
The writer creates a same-directory temporary file and atomically replaces
the record; it sets mode `0600`. Read the service endpoint after writing and
confirm both revisions, Hermes version, overlay hash, TaskStore hash, and
manifest hashes match the just-verified runtime. Never publish the record
before restart and health checks succeed, or reuse it for a different generated
tree. This is a manual
post-deployment step today; the private Hermes deployment workflow has no
tracked automated caller in this repository.

## HADES guest artifact reconciliation snapshot — 2026-09-29

Read-only comparison found three distinct source identities:

| Artifact | Observed SHA-256 / revision | Source relation |
|---|---|---|
| Running checkout | `b102dfd`, 18 dirty paths | Hermes service working tree |
| Running checkout `hermes/sitecustomize.py` | `1863ed…` | Differs from the active installed overlay |
| Active installed overlay | `d827e9db…` | Exact active bytes reproduce the identical-prompt cross-chat confirmation consume in a synthetic probe |
| Current clean HADES candidate | `4e04ee5`, overlay `75c53a39…` | Passes focused runtime and clean-archive packaging/recovery contracts; not deployed |

The read-only doctor run using the generated operator input exits nonzero with
one failure, `HADES layer provenance is stale`; the installation marker and
reconstruction manifest pass. File-level comparison against the running
checkout finds that both MCP adapters match, while the overlay and two theme
assets differ. The active `hades-theme.css` exactly matches current HADES HEAD;
the active `hades-theme.js` matches tracked historical commit `cdf18cc`. The
overlay's function scan maps 62/64 active bodies to repository history; the
remaining `_hades_task_response` and `_hades_nonpersonal_state_turn` match
protected deployment backups, not canonical tracked source. Thus the files
have partial historical attribution, but the installed layer and provenance
record do not identify one reproducible complete HADES revision.

No production file, service, provenance record, VM, or firewall was changed.
Do not promote the active overlay by copying it into a release candidate.
Prepare any review candidate from a clean canonical HADES revision, validate
the full packaged component set, and keep deployment behind source identity
and rollback review.

## Canonical source candidate refresh — 2026-09-29

A fresh `git archive HEAD` was extracted into a temporary directory and tested
without inherited worktree files. The source identity is HADES
`ba1168e4e8a664b092de4ba317f1734dd8693904`, tree
`d6d16cf531b4cd364d00c41e28f3ed1a4af985c6`, with overlay SHA-256
`4ba96516a605b330f8573983aa7d7357ab3976e7b233d45342bb6c60a0588701`.
The canonical seven-input installation layer digest is
`b341ef8dab674f058cc5df2ed24cd0d6137e7bee990ab69298cd8f4b644e9e6b`.

Against the pinned Hermes 0.21.2 Python runtime, the clean archive passed the
confirmation-conversation, self-service continuation, Grocy tool-scope, and
live-overlay drift contracts, plus Python compilation. The self-service test
includes the exact “Perfect, continue” lost-state path and verifies no model or
infrastructure write. This is a current source-bound candidate, not a complete
reconciliation of the active production overlay, the complete deployed runtime
component set, or an independently verified rollback package. Production
remains unchanged and deployment remains gated.

### Read-only runtime refresh — 2026-09-29

Strict-host-key SSH to the documented HADES guest account refreshed the runtime
identity: `hades-hermes.service` is active/running, PID `2021647`, zero
restarts, Hermes health HTTP 200 / version `0.21.2`; listeners remain on the
Docker bridge at `<PRIVATE_LAN_ADDRESS>:8642` and `:8643`. The deployed checkout remains
`b102dfdf42fc564c040c432cb2c6e87ee1f27d22` with 18 status entries. Active
overlay SHA-256 is `d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`,
while the live provenance endpoint reports HADES `bcd81f435c4d8a6210802ffeb64c20a0ad3adbd7`,
overlay `1863ed16573b7c040b78de98e7a3e6ad4463efb167c55c3b2c92bdc4d0a3c12a`,
and generated time `2026-09-24T07:54:33Z`.

Fresh hashes confirm the deployed five-file layer is mixed: both installed MCP
adapters match the dirty `b102dfd` checkout; installed CSS matches current
canonical HADES HEAD `ba1168e`; installed JS matches neither the deployed
checkout nor current HEAD; active overlay matches neither. The current clean
source candidate and focused runtime results are recorded above. Strict-host-key
SSH was read-only; no service, file, provenance record, VM, or firewall changed.

The VM's protected backup inventory contains two mode-0600 historical overlay
snapshots (`3bb18c07…` and `a9fe9863…`) plus the mode-0600
`scope-hotfix-20260927T0019Z/sitecustomize.py.original`
(`7827093c…`). The latter is not an exact backup of today's active `d827e9db…`
overlay. A protected HADES Git bundle is present with SHA-256
`e5a0f0ea…`; its `main` ref is `bbb6d755…`, not the serving checkout `b102dfd`
or current canonical HEAD `ba1168e`. These are useful historical sources, but
they do not establish an exact rollback copy of the currently active layer.
The separately documented storage host rollback package remains a distinct
custody artifact; its existence does not reconcile the live mixed component
map. Do not treat these VM backups as a reviewed candidate rollback package.
The infra promotion record identifies a separate protected Hermes 0.14.0
rollback archive (`3310c9f1…`), which was verified for the September runtime
promotion. That is a runtime-version rollback, not an exact rollback package
for today's Hermes 0.21.2 service plus mixed HADES overlay and assets.
Fresh strict-host-key, read-only inspection on storage host reconfirmed its SHA-256
`3310c9f11ccac10d249d77b308f280aa3da905f6fcff80627476a5cabab66dd1`; the
archive has four members and contains the prior `hades-hermes.service` unit,
with no `sitecustomize.py`, theme, or HADES adapter. This confirms it cannot
restore the active five-file HADES layer by itself.

The live installation marker says `layer=fcd5e1ed…` and
`manifest=48a30c93…`; the generated reconstruction manifest hashes to
`811807b9…`, and its Epsilon runtime manifest to `b210eb73…`. Recomputing the
deployed checker's five-file algorithm read-only gives three distinct values:
marker `fcd5e1ed…`, serving-checkout expected layer `e178774c…`, and installed
layer `9acb5239…`. This freshly reproduces the stale-layer failure and confirms
the active installation is not merely carrying a stale provenance endpoint.

## Clean source candidate refresh — HADES 41db14b (2026-09-29)

A new `git archive HEAD` review was run after the anonymous-account privacy
change. Source identity is HADES `41db14b30a4647f35ec911e1c8e9c6ffc1904e1a`,
tree `c494f1d597448f08d6309ae27d05eee1bcaf3f85`, overlay SHA-256
`95b56f551d512971deeb2f5df537fba8f7bfa5a37ec359af5e8714cc7bf5fe14`, and
current canonical seven-input install digest
`30f76bcfce23e1bd86faa8f74b0b143a2f8d890a63cc16a908b7abe1ca0de1b6`.

The current installer copies six HADES runtime files: the Hermes overlay,
three adapters, and two WebUI assets. Its seven-input digest additionally
includes `integrations/grocy-mcp/requirements.lock`, which is not copied into
the HADES config layer. Therefore the digest names the source/install contract;
it is not a byte digest over only the installed files. Historical references
to a five-file digest describe an older deployed checker/component inventory
and are not comparable to the current seven-input source digest without
recomputing both from their exact scripts and files.

From the clean archive, Python compilation, pinned Hermes confirmation
isolation, exact Minecraft “Perfect, continue” recovery, Grocy tool scope,
and live-overlay drift contracts pass. The full synthetic private-fixture
install/validate/non-mutating-doctor path also passes, including the current
six-file payload and seven-input manifest digest. These are source-bound and
isolated acceptance results. They do not reconcile HADES guest's active mixed
artifact or provide an exact production rollback package; production remains
read-only.

### Strict-host-key runtime recheck — 2026-09-29 (follow-up)

The documented `codex` key and pinned known-hosts file still reach HADES guest
read-only. `hades-hermes.service` is active with zero recorded restarts;
`/health` returns HTTP 200 and Hermes 0.21.2. The active overlay remains
`d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`. The
provenance endpoint at `/v1/epsilon/provenance` still reports the 2026-09-24
`bcd81f4` / `1863ed…` record, so it does not identify the active overlay.

The live `generated-full/config` directory contains the active overlay, the
recipe-authoring and Agent Zero adapters, and the two HADES theme assets. It
does not contain the current installer's `adapters/grocy-mcp-launch.py`; it
also contains finance/receipt upload assets and historical theme backups. This
is consistent with the older five-payload inventory but differs from the
current six-file installer payload. The missing current-source file may be
served from the detached checkout or another generated path; this read-only
inventory alone does not prove which path Hermes actually invokes. Do not
claim the live layer conforms to the current installer until that dependency
is resolved.

No source, service, deployment record, file, VM, or firewall was modified.

### Read-only MCP runtime dependency map — 2026-09-29

The live systemd unit sources `$HADES_HOME/generated-full/profile/hermes.env`
(mode 0600) and starts Hermes 0.21.2 with profile `hades`. A sanitized parse
of the effective profile configuration shows Grocy MCP launches from
`$HADES_HOME/.local/share/hades-grocy-mcp-venv/bin/grocy-mcp`, package
version 0.2.0. That user-local venv has no `manifest` file; the current
canonical installer instead creates `/opt/hades-grocy-mcp/venv`, writes a
lock-hash manifest, and registers `integrations/grocy-mcp/launch.py` in the
profile. Thus version equality alone does not prove that the production
Grocy MCP dependency was installed from the current lock.

The effective profile also launches recipe ingestion, finance import, public
page extraction, Agent Zero, and homelab read/control adapters from source
paths under the detached `$HADES_HOME/Hades` checkout, except homelab control,
which resolves under `$HADES_HOME/Hades-reconciled-b102dfd`. Sensitive MCP
configuration values were not printed. Checked API-key fields are environment
references; the sourced Hermes environment file is mode 0600. This still leaves
source revision and generated profile composition mixed across checkouts.

This is a read-only dependency/path map, not proof every tool was functionally
invoked or that its private inputs are recoverable. No source, service,
configuration, secret, VM, or firewall changed.


## Required Open WebUI asset packaging fix — 2026-09-29

Read-only production inventory found finance and receipt upload assets already
present in HADES guest, while the current installer did not copy them even though
the Open WebUI Compose template bind-mounts them. This is a rebuild defect; it
did not cause the supplied live Minecraft continuation failure and no production
change was made.

Commits `897166f` and `f91b0db` add finance/receipt assets to the installer,
reconstruction manifest, doctor/validator installed-file checks, provenance
digest, and a CI closure guard that compares all Open WebUI config asset mounts
to the manifest. The synthetic installer test also removes one staged asset and
confirms doctor fails with the exact missing asset. The updated canonical
payload is eight installed files; its digest has nine source inputs because it
also covers the Grocy requirements lock, which is not copied to the config
layer.

Validation from a clean archive of `897166f` passed shell/Node/manifest syntax,
installer source preflight, finance and receipt upload contracts, and the full
synthetic install/validator/non-mutating-doctor fixture. The repository-aware
manifest-closure check passed from the Git checkout. `f91b0db` changes only
that closure guard to compare all Compose mounts generically. No owner data,
production service, or VM was changed.

The latest clean archive, HADES `f91b0db86f97ac2fad749f01e6be94bf641c9fe9`
(tree `4560077ab9598438964d086d44da1044304ca21c`), reproduces the same overlay
and nine-input installation digest. Its synthetic fixture passes both validator
and non-mutating doctor, and doctor rejects removal of a Compose-mounted upload
asset. This verifies current committed source after the closure-guard change.

## Hermes MCP profile classification and production drift — 2026-09-29

The canonical profile now has an authoritative registration classification in
`config/reconstruction-manifest.json`. V1-required registrations are Grocy,
Grocy recipe serving authoring, recipe URL/paste ingestion, and read-only
homelab discovery. Receipt OCR and finance file intake are owner-gated. Bounded
Agent Zero delegation, homelab control, browser research, static page
extraction, and composed public research are optional/staged and disabled in
the canonical profile until their explicit activation/acceptance gates pass.
Synthetic fixtures are test-only; Agent Zero native A2A remains post-V1.

A fresh strict-host-key, read-only parse of the effective HADES guest profile found
four registered MCP servers: `grocy`, `grocy_recipe_authoring`,
`hades-agent-zero`, and `homelab-readonly`. The `grocy` command resolves to the
user-local `hades-grocy-mcp` executable rather than the canonical file-key
launcher. The required `recipe-url-ingest` registration is absent. This differs
from older blocker notes that described it as registered; the current profile
file is the authority for this observation. No authenticated tool call was
made and no user data was accessed.

`scripts/check-hermes-profile-contract.py` now checks the profile against the
manifest classifications and verifies the required registration paths. Both
`hades-doctor.sh` and `validate-install.sh` call it, so an installed profile
missing recipe ingestion fails clearly instead of passing on Grocy alone. The
manifest-closure regression removes that registration and verifies rejection;
the synthetic-install doctor regression also verifies rejection. This records
source-side drift detection; it does not modify the active profile or service.

Correction (2026-09-29): this earlier four-registration observation used the
top-level generated `profile/config.yaml`; it is not the selected profile when
the service is started with `-p hades`. Use the selected-profile reconciliation
below as the current runtime evidence: it includes `recipe-url-ingest` and has
nine registrations in the latest requalification; see the current composition snapshot below.

### Runtime source/rollback fingerprint refresh — 2026-09-29

The running unit still uses Hermes 0.21.2 from
`$HADES_HOME/Hades-reconciled-b102dfd` (`b102dfd`, 18 dirty entries), while a
second `$HADES_HOME/Hades` checkout is `c3f7262` with 49 dirty entries. The
active installed overlay is `d827e9db…`; the current canonical overlay is
`95b56f55…`. Installed recipe-authoring and Agent Zero adapters, the WebUI JS
theme, and finance/receipt upload assets differ from current HADES source; CSS
matches. The current file-key Grocy launcher is missing from the installed
config directory. The install marker records layer `fcd5e1ed…`; current source
and installed artifacts therefore do not describe one reproducible layer.

The root-owned mode-0600 pre-Minecraft overlay snapshot exists at
`.sitecustomize.pre-minecraft-continuation.25c85b9` with SHA-256
`25c85b9d…`. It is only an overlay preimage, not an exact rollback package for
the profile, adapters, assets, manifests, service, and source tree together.
No complete rollback package was established in this inspection. No secrets
were read; production remains unchanged.

## Strict-host-key component-path reconciliation — 2026-09-29

A fresh read-only HADES guest inspection resolved the active Hermes MCP profile's
adapter paths and hashed the complete current installer file set. Secret
values were not read. The service still runs Hermes 0.21.2 with zero restarts;
the sole configured Proxmox template alias is `linux-sandbox`.

| Runtime component | Active bytes/path | Current canonical HADES HEAD (`dba3a70`) | Serving checkout (`b102dfd`) | Finding |
|---|---|---|---|---|
| Hermes overlay | Installed `d827e9db…`; effective `PYTHONPATH` selects this file | `95b56f55…` | Checkout source `1863ed16…` | Installed bytes match neither source identity. |
| Grocy MCP | `$HADES_HOME/.local/share/hades-grocy-mcp-venv/bin/grocy-mcp`; version previously observed as 0.2.0 | Required file-key launcher and requirements-lock manifest | Not established | Canonical `adapters/grocy-mcp-launch.py` is absent from generated config. Effective package has no recorded lock provenance. |
| Recipe-authoring MCP | Profile executes `$HADES_HOME/Hades/integrations/grocy-recipe-authoring/server.py` (`4006276e…`) | `199c689f…` | `ec519539…` | Effective source is neither canonical nor the staged adapter; the staged file matches the serving checkout. |
| Agent Zero MCP | Profile executes `$HADES_HOME/Hades/integrations/agent-zero-mcp/server.py` (`e183e2ab…`) | `e183e2ab…` | `d31775e5…` | Effective source matches current canonical bytes; staged adapter matches the older serving checkout and is not what the profile runs. |
| Homelab read-only MCP | Profile executes `$HADES_HOME/Hades/integrations/homelab-readonly/server.py` (`03f3c416…`) | `efdc63b3…` | Not compared in this pass | Effective source differs from current canonical source and comes from the dirty `$HADES_HOME/Hades` checkout. |
| WebUI CSS | Installed `f617293a…` | `f617293a…` | `fdb90c80…` | Matches current canonical source. |
| WebUI theme JS | Installed `774c3c46…` | `360459e4…` | `5e3ab2c4…` | Matches neither current source identity. |
| Finance upload JS | Installed `76fd0770…` | `cabc6468…` | `165c9650…` | Matches neither current source identity. |
| Receipt upload JS | Installed `5b4d1069…` | `05c9ff59…` | `e55b0602…` | Matches neither current source identity. |

The unit starts Hermes with `-p hades`, so the selected profile is
`$HADES_HOME/generated-full/profile/profiles/hades/config.yaml`, SHA-256
`31108a8a…`. It registers and enables nine servers: all four V1-required
servers, both owner-gated servers (`finance-file-import` and
`receipt-ocr-gateway`), and three optional/staged servers (`hades-agent-zero`,
`homelab-control`, and `public-page-extract`). The control MCP template alias
is only `linux-sandbox`; the separate `public-research` and `browser-research`
servers are absent. The top-level
`$HADES_HOME/generated-full/profile/config.yaml` has SHA-256 `8eb17616…` and
contains the older four-server list, but is not selected by the running unit.
Earlier reports that described that top-level file as the effective profile
are superseded by this process-argument/path check. HADES checkouts on HADES guest
remain `b102dfd` with 18 status entries and `c3f7262` with 49. Together these
observations show the serving process composes a generated overlay/assets and
selected profile, two different source checkouts, and an untracked user-local
Grocy package. Neither a single-source installer run nor restoration of one
overlay snapshot restores this runtime exactly.

The selected profile's owner-gated and staged entries are enabled. This is an
observed production configuration, not proof that the explicit owner activation
gate was satisfied or violated; activation intent is not recorded in the
profile. No gated tool was invoked. The shipped canonical profile keeps those
entries disabled. The doctor now warns for enabled owner-gated operator
entries, while the canonical-profile check requires them disabled.

This path map strengthens the no-deploy decision. An exact rollback must account
for both dirty checkouts, the generated profile and component files, service
configuration, and the Grocy executable/package provenance while preserving
private inputs. No production files, services, secrets, VM state, or firewall
rules were changed.

### Existing runtime-config archive scope check — 2026-09-29

The protected `runtime-config.tar` created on 2026-09-25 is not an exact
current rollback. Its member list includes the Hermes unit and selected
generated assets, but no effective Hermes profile or generated MCP adapter
files. Hashes of archived bytes versus current live bytes show the archive
matches the current unit (`2d24951c…`), CSS (`f617293a…`), finance upload
(`76fd0770…`), and receipt upload (`5b4d1069…`); its overlay (`0c1abb2d…`)
and theme JS (`154051fa…`) differ from current active files (`d827e9db…` and
`774c3c46…`). It is a partial historical recovery input.

The protected HADES bundle has `main=bbb6d755…`, not the serving worktree
`b102dfd`; the inventory also includes older backup/public refs. The archive
and bundle were only listed/hashed. Neither was extracted or restored. Available
protected artifacts do not provide a reviewed exact rollback package for the
active mixed runtime. No production files or services were modified.

### Exact active code/config rollback snapshot — 2026-09-29

A root-owned, mode-0600 snapshot now captures the active Hermes code/config
composition at
`$HADES_HOME/generated-full/backups/hades-runtime-rollback/20260929T184128Z/active-runtime-code-config.tar.gz`
on HADES guest. SHA-256:
`8000ca97a89635f1119318820299b38b00b4c248c1b2d943c4537b789701b759`.
The 38,583,720-byte archive includes the active service unit, both dirty HADES
checkouts used by the service/profile, generated config/assets/overlay/adapters,
the selected `hades` MCP profile, `hermes.env`, the install-contract marker,
and the effective user-local Grocy MCP virtualenv. The runtime profile and
environment may contain private values; the archive and its parent directories
are root-owned and mode `0600` / `0700` respectively.

`tar --compare` passed against the captured live paths, SHA256 verification
passed, and an isolated extraction into a root-only temporary directory
compared byte/metadata-identically to the archive; the temporary extraction
was removed. The member audit confirmed that application state and profile
session/memory data were excluded. The pinned Hermes package under `/opt`, OS
packages, databases, and application volumes are outside this code/config
snapshot and were not changed; this is a rollback for HADES runtime code and
configuration on the existing VM, not a host-disaster or data restore.

This closes the missing exact code/config preimage for a bounded runtime
rollback, with same-VM custody. It does not satisfy encrypted off-host backup
custody or authorize deployment. No service, runtime file, VM, database,
application volume, or firewall was changed.


## HADES guest runtime composition and rollback audit — 2026-09-29

### Active runtime identity

Strict-host-key read-only inspection found the selected Hermes profile at
`$HADES_HOME/generated-full/profile/profiles/hades/config.yaml`, SHA-256
`31108a8a6130fa5bbd301a29e6bab61bb5d54b9a46c84e6c04de5b4e4ab56fbe`. A fresh structural parse of the raw YAML and effective mapping finds nine MCP
registrations, confirming the earlier nine-entry report. `receipt-ocr-gateway`
is an HTTP URL registration and was omitted by a command-only inventory pass:

| Registration | Contract class | Selected profile | Runtime source/provenance | SHA-256 | Local HADES source identity |
|---|---|---|---|---|
| `grocy` | V1 required | Registered | User-local `hades-grocy-mcp` venv, package `0.2.0`; no installed lock or manifest file. The canonical generated `adapters/grocy-mcp-launch.py` is absent. | executable `386b44a1…` | No canonical source manifest |
| `grocy_recipe_authoring` | V1 required | Registered | `$HADES_HOME/Hades/integrations/grocy-recipe-authoring/server.py`; remote serving checkout is modified. | `4006276e3d1636532483a51ae2ed3f626392bd49115359d78e3dd749c3724cb9` | Historical HADES commit `049deed7`; not current HEAD |
| `recipe-url-ingest` | V1 required | Registered | `$HADES_HOME/Hades/integrations/recipe-ingest/server.py`; remote serving checkout is modified. | `52b61e2e777bda35537c2deb1debc571fcfdbf90ce70f1cd735de2485aedf72c` | HADES current HEAD blob; commit `dba152b1` |
| `homelab-readonly` | V1 required | Registered | `$HADES_HOME/Hades/integrations/homelab-readonly/server.py`; remote serving checkout is modified. | `03f3c416ab0a9e062e4e1c0040a08633c2cbe492ab371d5ce07a78c2038a712a` | Historical HADES commit `e99ce702`; not current HEAD |
| `finance-file-import` | Owner gated | Registered | `$HADES_HOME/Hades/integrations/actual-finance-import/server.py`; remote serving checkout is modified. | `d4faee079b4df26b658767a2b3ddcc0dab09dc1071c476304905469f711edabe` | HADES current HEAD blob; commit `dba152b1` |
| `receipt-ocr-gateway` | Owner gated | Registered | HTTP URL-form registration; endpoint value withheld. Current endpoint SHA-256 `1b7156850c13908ede5d663f65a9c406e3c06b4ae62c2e6a68fee680d0ec4a51`; active `hades-receipt-ocr:20260918-r3` image ID `sha256:e38b5a8e575e148fdee68c5fb5103acb9a674bb5dec82577bea338316e541860` (linux/amd64), no source labels. | Endpoint digest and image ID captured; source/build provenance unknown | Not reconciled |
| `public-page-extract` | Optional/staged | Registered | `$HADES_HOME/Hades/integrations/web-extract/server.py`; absent from remote serving checkout HEAD. | `231c097385e6a221bb9e9a73d50572b09cf43b34b23dd8c6b80bc0dd1f8e9b4a` | HADES current HEAD blob; commit `40d064e8` |
| `hades-agent-zero` | Optional/staged | Registered | `$HADES_HOME/Hades/integrations/agent-zero-mcp/server.py`; remote serving checkout is modified. | `e183e2abdb7766d3fc3c25496b2da4ae8365109caf06f8e8cc9a923fc76729f3` | HADES current HEAD blob; commit `dba152b1` |
| `homelab-control` | Optional/staged | Registered | `$HADES_HOME/Hades-reconciled-b102dfd/integrations/homelab-control/server.py`; absent from remote serving checkout HEAD. | `139de9bcabd644bdd68faa64da8602e372f8e2804542143b43f70c81c1a8cfbb` | HADES current HEAD blob; commit `dba152b1` |

The selected profile contains no `public-research`, `browser-research`, or Agent
Zero Operator registration. All nine entries are registered: four V1-required,
two owner-gated, and three optional/staged. Owner activation intent for the
gated and staged entries is
not recorded. No such tool was invoked during this audit, and no activation
change is inferred or made.

The serving checkouts are HADES `c3f7262281c83343ced72edc4ca1e48bed47cc89`
with 28 tracked modifications and 28 untracked paths, and
`Hades-reconciled-b102dfd` at `b102dfdf42fc564c040c432cb2c6e87ee1f27d22` with
9 tracked modifications and 26 untracked paths. A fresh status-only recheck
confirmed these counts and HEADs. The configured source bytes
were copied read-only into a private temporary directory and compared with the
full local HADES history. All seven server files map to source blobs in that
repository: five match current HADES HEAD (`recipe-ingest`, finance import,
`web-extract`, Agent Zero, and homelab control); Grocy recipe authoring and
homelab read-only match earlier commits `049deed7` and `e99ce702`. The dirty
serving checkouts themselves do not provide a single clean revision for this
set. The Grocy MCP executable resolves into a user-local venv with no canonical
lock/manifest evidence. The live generated reconstruction manifest is SHA-256
`811807b9357055ba50bf629e5b4e52981e8398e10d179c762061cb3e45992b3f`; its
installed layer remains mixed and the provenance record remains stale.

The two historical source differences are behaviorally scoped. Current Grocy
recipe authoring adds a permission-checked file-backed API key reader with a
protected environment fallback; the selected production entry currently names
`GROCY_API_KEY`, not `GROCY_API_KEY_FILE`. Current homelab read-only adds a
read-only NetBox service catalog projection and bounded per-monitor ping
metadata. The older configured source lacks those additions. Current-source
contracts pass for the Grocy recipe-authoring boundary, homelab adapter, and
canonical Hermes profile template. The confirmation-isolation Hermes runtime
contract also passes cross-chat refusal, missing-conversation-ID refusal, and
same-chat decline with no model call. These tests validate tracked candidate
source, not production's historical code or owner-enabled profile entries.

The generated config has the active overlay (`d827e9db…`), recipe-authoring
adapter (`ec519539…`), Agent Zero adapter (`d31775e5…`), CSS/JS theme assets
(`f617293a…`, `774c3c46…`), and finance/receipt upload assets
(`76fd0770…`, `5b4d1069…`). The canonical Grocy launcher is missing there. The
MCP entries point directly into the dirty serving checkouts rather than to
one manifest-bound installed source tree. Among the generated files, the CSS
matches current HADES HEAD; the theme JS, finance upload, and receipt upload
match older tracked commits `a18437c4`, `ecaaa70d`, and `44df2891`; the two
installed recipe-authoring/Agent Zero adapters trace to commit `0f94d476`.
The active overlay has no exact whole-file Git blob match, although its function
bodies are partially attributable as documented above. The canonical Grocy
launcher is missing. This is not a reproducible single-revision source
composition even though most individual files have source lineage.

### Clean committed candidate acceptance — HADES 32e146a (2026-09-29)

A fresh `git clone --no-hardlinks` of HADES `32e146a11a51906dfdd2a267d78544277f485343` produced a clean worktree with zero status entries. This supersedes the earlier `b5979cb` candidate run. The clone passed the canonical Hermes profile contract, reconstruction manifest closure, and the full synthetic private fixture: test-mode install, validator, non-mutating doctor, required-file and secret-mode checks, layer/provenance digest, and doctor rejection for a missing mounted asset or required registration. The canonical profile kept owner-gated and staged entries disabled.

The same clean candidate passed the pinned Hermes Minecraft continuation contract and cross-chat confirmation runtime contract, including lost pending-state recovery, fail-closed context-free confirmation, missing conversation-ID rejection, and same-chat decline. All were synthetic; no production account, MCP call, VM, or firewall was used. The temporary clone and fixture were removed by their normal cleanup paths. This validates the current source candidate and its default profile, not HADES guest's mixed overlay, private profile, Grocy venv, or production acceptance.

### Rollback snapshot verification

The root-owned mode-0600 archive
`$HADES_HOME/generated-full/backups/hades-runtime-rollback/20260929T184128Z/active-runtime-code-config.tar.gz`
remains present with SHA-256
`8000ca97a89635f1119318820299b38b00b4c248c1b2d943c4537b789701b759`. A
full read-only comparison found 10,035 of 10,036 archive entries
byte/metadata-equal, with no missing paths. The only difference is the
regenerated `integrations/homelab-readonly/__pycache__/server.cpython-312.pyc`.
All 105 archived files under `generated-full` match current bytes, including the
active overlay. The snapshot is a verified same-VM code/config preimage; it is
not off-host custody, host/data recovery, or authorization to deploy.

This separates the gates: a same-VM code/config rollback snapshot is verified,
while one coherent, manifest-bound runtime source composition and authorized
update procedure remain unresolved. No production service, profile, source,
secret, VM, database, or firewall was changed.

### Latest clean committed candidate — HADES 3d290f9 (2026-09-29)

A fresh no-hardlink clone of HADES `3d290f9ac4e70f55bbdd993d6f16ad26e4356c1e`
had a clean worktree and passed the deployed-provenance writer contract,
Hermes Minecraft continuation contract, Epsilon provenance endpoint contract,
and reconstruction-manifest closure contract. The provenance writer now parses
both inline JSON-style MCP argument arrays and the block-style YAML lists used
by the selected HADES guest profile, and rejects unsupported mappings. The exact
Minecraft request returns a concrete no-write plan in source acceptance;
“Perfect, continue” recovers that plan without model or infrastructure calls.

This is current-source acceptance only. It does not qualify the active mixed
HADES guest runtime or authorize deployment. The selected production profile,
source checkouts, Grocy executable, receipt OCR image, and rollback boundary
remain as recorded above; production stayed read-only.

### Clean current-HEAD synthetic install — HADES e012813 (2026-09-29)

A fresh no-hardlink clone of HADES
`e0128137822c5e42d9b2abeb839d89851026de6b` passed
`scripts/test-synthetic-private-fixture.sh`. The clean install recorded its
revision/tree, reconstruction manifest, and nine-input HADES runtime layer
digest `744f38406fdc718cff2246a3ae31b18474fe429d83871567f49112775ff3f8de`;
secret modes, mounted assets, required MCP registrations, validator, and
non-mutating doctor all passed. Doctor correctly rejected missing assets and
required registrations and warned when a synthetic operator profile enabled
an owner-gated server. The canonical profile left all owner-gated and staged
registrations disabled.

This validates the canonical installation contract on a clean source clone.
It does not reproduce HADES guest's private profile, historical MCP blobs, unlocked
Grocy environment, or unlabelled receipt OCR image. No production state was
changed.

### Active generated layer versus clean candidate — read-only refresh 2026-09-29

The exact active generated files were rehashed on HADES guest and compared with
Git blobs at candidate `e0128137822c5e42d9b2abeb839d89851026de6b`. The clean
candidate's nine-input runtime layer digest is
`744f38406fdc718cff2246a3ae31b18474fe429d83871567f49112775ff3f8de`; the live
install marker instead records layer `fcd5e1ed01ddced08d1709087f54e4377149a1bf5b8858a651dfcfaf53f0e1a6`, versions manifest
`48a30c9385c57ee05fd42ac9308729a76d222316434a3cc2c6cca7de85ea0c4c`, and
reconstruction manifest
`811807b9357055ba50bf629e5b4e52981e8398e10d179c762061cb3e45992b3f`. Current
candidate manifest hashes are `0b71d225…` and `a0561d8e…` respectively.

| Runtime input | Active HADES guest bytes | Clean candidate `e012813` | Comparison |
|---|---|---|---|
| Hermes overlay | `d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a` | `aa2867e238460282acedacd550fb57b2c23f5c6842ea18605f85f956644ea2c1` | Different; active bytes have no exact whole-file source blob |
| Grocy launcher | Missing at `generated-full/config/adapters/grocy-mcp-launch.py`; runtime instead invokes unlocked venv executable | `8aba83116f609e451ad124af0459a0e31ac4d689667584ffccc972e69757a358` | Required canonical launcher absent |
| Grocy requirements lock | Not present in active serving checkout; effective venv has no nearby lock/project manifest | `dcde0308ec25f30e983bda3aa77c46c2ca0a20be61d1e2bc6ddef463c4b6ce25` | Installed dependency bytes not bound to candidate lock |
| Recipe-authoring adapter | `ec519539cabd40f0b2bf21159b730037be6561a68dd96ab82d452b9b0c7a0e11` | `199c689f7aa2617d372efd1669007880c3a0aec55ab74252bb59570808fdd611` | Different; live profile invokes a historical source checkout |
| Agent Zero adapter | `d31775e59001dbb2e5a2d6e1fccee30a034a3687f62f523342a757270e1bdead` | `e183e2abdb7766d3fc3c25496b2da4ae8365109caf06f8e8cc9a923fc76729f3` | Different; live profile invokes a different source path |
| HADES theme CSS | `f617293a4da1fcea450bd0e02ef3ccad1d297657507e8e75648b17d1e48484d3` | `f617293a4da1fcea450bd0e02ef3ccad1d297657507e8e75648b17d1e48484d3` | Exact match |
| HADES theme JS | `774c3c46fc641000de8728d2cacb2632f5698a7a92bdb187c97e8cfc36c72abb` | `360459e42ea8530beb73ba349bf7366ce39a082f71a1e6fc59d22a7f94196290` | Different |
| Finance upload JS | `76fd07708ccbe50257e8bdf4867d6c2ebe3324d18f0e69eb562c3d9beda1ff30` | `cabc64689f903b522de8da47f9aa92c1b8b6c736e203eeca7164f6ea5cd9186a` | Different; owner-gated asset |
| Receipt upload JS | `5b4d1069920eea19b2630fd021b67444004b7634ebb560fa2202081a7e769d05` | `05c9ff59949351bf74536412c3f08ba24c4c2d8ed6908abbe019c0c8eb3e5fb2` | Different; owner-gated asset |

This confirms that only the CSS is byte-identical across the installed layer;
the launcher's absence, historical adapters, overlay, theme JS, and upload
assets prevent the active generated layer from matching the clean candidate.
The live profile and receipt image remain separate composition inputs. No
files or services were changed during this recheck.
