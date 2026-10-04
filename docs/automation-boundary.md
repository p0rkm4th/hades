# Deterministic automation boundary

Status: **TYPED READ-ONLY CANARY AUTHORIZED / IMPLEMENTATION AND ACCEPTANCE INCOMPLETE**.

HADES does not own a scheduler or run an enabled deterministic automation in
production. A private n8n runner hosts an inactive read-only canary. The owner's
Owner Away policy authorizes a bounded canary only for Server Health Watch,
Low Inventory Summary, Weekly Household Summary, and Backup Verification.
That policy removes the prior request for a separate Manny/Orc product approval;
it does not waive the execution, current-authority, recovery, or acceptance
requirements below. This document defines the safe execution contract. It is
not an automation engine or a permission system.

## Required execution shape

```text
authenticated subject
        ↓
capability check
        ↓
deterministic workflow with a stable idempotency key
        ↓
canonical external system
        ↓
structured outcome returned to HADES
```

The model may propose a workflow and fill declared inputs, but it must not
invent a trigger, select an undisclosed destination, or convert a preview into
an action. Any workflow that changes external state requires an explicit owner
or separately authorized capability and a confirmation boundary appropriate to
the impact.

## First-workflow requirements

Before enabling a workflow, record privately:

- the exact trigger and allowed actor/group;
- input schema, validation rules, and maximum scope;
- canonical system being changed;
- read-only, preview, confirmation, and apply phases;
- idempotency key and duplicate behavior;
- timeout, retry, and partial-failure behavior;
- audit/result record without secrets or unnecessary personal data;
- rollback or compensating action where the canonical system supports one;
- restart/replay behavior and an owner-UI acceptance workflow.

The initial implementation should use an existing mature workflow runner or a
narrow adapter. It must not introduce a generalized HADES scheduler,
orchestrator, tool registry, or runtime layer.

## Safety contract

- Unauthenticated, unknown, or revoked subjects fail closed.
- Capability-resolution failure fails closed; it never grants the union of
  available tools.
- A repeated delivery with the same idempotency key must not duplicate a
  mutation.
- A timeout or lost response is reported as **outcome unknown** until the
  canonical system is checked; it is never reported as success.
- A workflow must not retry a non-idempotent mutation without a canonical
  state check.
- Retrieved web text, model text, and tool output cannot change identity,
  authorization, destination, or approval state.
- Household users receive no finance, homelab-mutation, administration,
  security-sensitive smart-home, or privileged Agent Zero workflow by default.

## Standing owner authorization

The standing authorization is limited to the four named read-only templates,
their already-authorized canonical sources, and HADES-local result delivery.
It does not authorize arbitrary workflow generation, source mutation, external
notifications, household grant expansion, or privileged tools. Before enabling
the canary, privately record:

```text
workflow:
allowed actors/groups:
canonical system:
read/preview/apply scope:
confirmation rule:
rollback/compensation:
retention:
```

The isolated `Phase3Runner` core now routes fixed-source reads through a
HADES-owned operation that rechecks the current owner/resource grants directly
before dispatch, records idempotent outcomes, and gates results after sharing
or authority revocation. `scripts/test-phase3-runner.sh` exercises these
properties synthetically, including duplicate delivery and an expired lease
that becomes `UNKNOWN` without replay. Authority-provider failure before
reservation creates no run row; failure after reservation closes the row as
`FAILED` without dispatching a source. A signed HTTP handler contract is now
defined in `integrations/automation/phase3_request.py`: it binds method/path,
timestamp, and exact JSON body, rejects stale or malformed requests, and relies
on the durable execution key for safe retry. Its synthetic contract is
`scripts/test-phase3-request.sh`. The signed handler is attached to the
repository Epsilon endpoint, and `scripts/package-epsilon-source.py` packages
its shared automation modules into an existing generated deployment root.
The runner requires the live `Phase3LldapAuthority` source; it refuses to start
without all directory inputs and has no static-policy fallback. A dedicated
`lldap_strict_readonly` account is checked on each lookup, stable Open WebUI
subjects map explicitly to LLDAP user IDs, and only configured groups grant
the fixed resource set. Synthetic contracts and a disposable pinned LLDAP
runtime verify group revocation and deleted-user denial. Loopback endpoint and
isolated package-closure tests pass. The production generated runtime now
contains the Phase 3 package: its 15-file runtime manifest matches this
checkout, and the Epsilon service has live directory inputs, runner/result
keys, and the shared state path configured. The dedicated strict-read-only
LLDAP principal and protected subject/group mapping were validated against
live LLDAP, including an unmapped fail-closed case. Production Epsilon and
Hermes units are active; the Open WebUI notification asset matches the
repository. These are deployment facts, not proof that a production source
run or authenticated result notification has passed.
The current `Phase3Store` single-user default is mode `0600`/`0700`; because
the production Hermes and Epsilon services have distinct UIDs, live canary
activation also depends on the newly added dedicated-group state contract and
its cross-UID SQLite validation in `scripts/test-phase3-shared-state-contract.sh`.
The production shared state database is present with mode `0660` and dedicated
group ownership.
The production Server Health Watch endpoint is also not configured, so that
template must remain disabled until an authoritative HADES health source is
provided. The staged Hermes UI still reads its separate operator-managed
policy file; the fixed active graph still calls Epsilon sources directly. See
[`phase3-authority-policy.md`](phase3-authority-policy.md). Before canary
activation, the packaged Epsilon service passed on a pristine Fedora 44 Cloud
guest with SELinux enforcing. The transient unit used `ProtectSystem=strict`,
`ProtectHome=read-only`, `NoNewPrivileges`, `PrivateTmp`, a 128 MiB memory
limit, and a narrow writable state path. Signed run, private-input ownership,
SQLite persistence, service restart/replay, and live LLDAP group revocation
all passed again after guest reboot. This was synthetic service acceptance;
the guest was destroyed after the proof. The resolver still does not read
Open WebUI's local account-disable flag, so that path must use mapped LLDAP
user/group deprovisioning. Separately, the pinned Open WebUI verified-user
gate rejects chat requests when an account's role changes to `pending`, even
with a token issued before the change. `scripts/test-openwebui-disabled-role-session.sh`
verifies HTTP 401 from the verified-user route and `/openai/chat/completions`
in a disposable WebUI runtime. This interactive ingress gate does not replace
LLDAP deprovisioning for scheduled Phase 3 authority and recipients.

The production n8n instance remains loopback-only and healthy, but its
database currently has no `HADES Phase 3 Fixed Read Dispatcher` workflow and
no `HADES Phase3 Runner HMAC` Crypto credential. Its schedules therefore
remain inactive. The matching runner key file is already present for Epsilon;
do not regenerate it. Production Hermes has the result-query URL and
service-owned result key configured, and the Open WebUI result notification
route is deployed (unauthenticated requests return `401`). The authenticated
owner/household result UI path has not yet been exercised against production.
Until that acceptance and rollback review pass, do not import or activate the
dispatcher or run a production source read. The fixed-template graph and
credential have both passed the pinned disposable n8n runtime contract below.

## Remaining scheduler and result boundary

The runner endpoint accepts one known automation ID and a stable execution key.
It returns the operation result to that authenticated scheduler request and
stores the result in the isolated ledger. A signed `POST /v1/epsilon/phase3/due`
route now returns a bounded batch for one requested fixed template from the
approved catalog, allowing the four fixed graphs to poll independently. Each
record gets one stable key per interval; missed intervals coalesce, and a latest
`UNKNOWN` outcome blocks later automatic runs until operator recovery. The
route returns only the automation ID, execution key, and due time to the
authenticated scheduler. Its source contract and end-to-end synthetic run
dispatch are covered by `scripts/test-phase3-scheduler-dispatch.sh`. The
request module also defines
an optional signed `POST /v1/epsilon/phase3/results` route. It accepts only a
stable requester subject and returns at most five latest completed results
across automations currently visible to that requester. A separately supplied
HADES result-query key authenticates this route; it resolves the requester
through the runner's live authority provider and rechecks requester and owner
grants before returning each result. Revoked sharing produces no visible row,
and a disabled/deleted requester is denied. Reusing the n8n run key cannot
authenticate this route. The Hermes source overlay now has an explicit
result-history intent path and bounded human renderer; it derives the subject
from the authenticated session and does not pass the turn to the model when the
query fails.

The signed routes and Hermes result client are deployed, but production
automation dispatch remains inactive because the n8n Crypto credential and
fixed workflow have not been imported. The new fixed dispatcher artifact is
inactive by default. It polls the due endpoint every
five minutes, validates no more than 25 returned rows, and uses n8n's built-in
Crypto node with a named encrypted credential to sign due and run requests.
The workflow Code nodes read no environment variables or files; workflow
success/error data persistence is disabled. The exact private n8n image
`docker.n8n.io/n8nio/n8n@sha256:9f693fd5565539efd5e75ad168526c8041a6af516d9e50bc4d9cb1c9c5031523`
reports version `2.40.5`. `scripts/test-phase3-n8n-dispatch-runtime.sh` imports
and executes the inactive graph in that pinned image against a temporary
synthetic receiver; it verifies HMAC requests and fixed run dispatch. The
conversational Phase 3 surface still describes records as saved drafts; no
workflow is active.

For a fresh target, enabling the result-read path requires separate
service-owned copies of one random key in already-protected parent directories:

```sh
sudo install -d -o root -g root -m 0711 /etc/hades/phase3
sudo install -d -o root -g hades-runtime -m 0750 /etc/hades/phase3/hermes
epsilon_group=${HADES_EPSILON_GROUP:?set the target service group}
sudo install -d -o root -g "$epsilon_group" -m 0750 /etc/hades/phase3/epsilon
sudo python3 scripts/create-phase3-result-query-keys.py \
  /etc/hades/phase3/hermes/result-query.key hades-runtime hades-runtime \
  /etc/hades/phase3/epsilon/result-query.key "$epsilon_group" "$epsilon_group"
```

The helper refuses existing destinations and prints paths only. Set
`HADES_EPSILON_PHASE3_RESULT_HMAC_KEY_FILE` to the service-owned path in each
process's own environment; set `HADES_EPSILON_PHASE3_RESULT_QUERY_URL` only in
the Hermes profile. The two files must contain the same generated key while
remaining mode `0600` and owned by the process that reads each file. Do not
reuse the n8n runner key. This procedure does not install Phase 3 modules,
enable schedules, or activate the endpoint by itself.

For a fresh target, the n8n run credential requires a separate Epsilon-owned
key file; enter its contents as the HMAC secret of an n8n `Crypto`
credential named
`HADES Phase3 Runner HMAC`:

```sh
runner_user=${HADES_RUNNER_USER:?set the target runner user}
runner_group=${HADES_RUNNER_GROUP:?set the target runner group}
sudo install -d -o "$runner_user" -g "$runner_group" -m 0700 /etc/hades/phase3/runner
python3 scripts/create-phase3-runner-key.py \
  /etc/hades/phase3/runner/runner.key "$runner_user" "$runner_group"
```

Keep the value in the encrypted n8n credential and the Epsilon mode-0600 key
file. Set `HADES_EPSILON_PHASE3_HMAC_KEY_FILE` in the Epsilon service
environment. Obtain the n8n credential ID, then render the tracked inactive
workflow with that ID before importing it:

```sh
python3 scripts/render-phase3-dispatch-workflow.py \
  --credential-id <n8n-crypto-credential-id> \
  --output /tmp/hades-phase3-runner-dispatch.json
```

Import it without activating it until the private Epsilon key, directory
authority, state path, HADES result-query key, Hermes endpoint, and signed
synthetic integration acceptance are all in place. Schedules remain inactive
until a separate operator acceptance step.

The source modules, Hermes client, deployed due/run/result endpoints,
inactive dispatcher artifact, and exact-image synthetic n8n runtime contract
are in place. The joined acceptance `scripts/test-phase3-n8n-epsilon-hermes-runtime.sh` now runs
the generated Epsilon package under a strict transient user systemd unit,
imports and executes the inactive dispatcher in the exact pinned n8n image,
and pulls both pinned runtime images itself before the test. It uses a
disposable LLDAP instance for authority checks.
One signed due/run delivery causes one fixed-source call against a synthetic
inventory fixture. After an Epsilon service restart, replaying the same signed
delivery returns its persisted outcome without another source call.

The same run starts an ephemeral Hermes gateway and authenticated Open WebUI
with synthetic Alpha, Beta, and Gamma accounts. The browser acceptance proves
owner and explicitly shared Beta result visibility, hides the result from
unshared Gamma, and verifies that a live LLDAP group revocation removes Beta's
access on the next query. Run identifiers remain hidden. This joined contract
passed first on Garuda and then on a pristine Fedora 44 Cloud guest with SELinux
enforcing. The Fedora run used the exact generated Epsilon package, HADES Open
WebUI image built from the tracked Dockerfile and immutable base pin, Hermes
0.21.2 installed from the manifest-matching source archive with locked
dependencies under Python 3.11, and the exact pinned n8n and LLDAP images. It
passed again after a guest-agent-mode reboot, with Docker active and no manual
service starts. Only synthetic identities and inventory data were used. The
test creates and removes its temporary containers, WebUI volume, state, and
transient service unit. No workflow was activated and production remained
unchanged.

The first clean-host attempt exposed three reconstruction/test defects and they
are now encoded: Hermes 0.21.2 rejects wheel installation, so the artifact
installer preserves the verified source and uses locked `uv sync`; the clean
test host must acquire pinned n8n/LLDAP images itself; and temporary n8n bind
mounts need private SELinux relabeling. The canonical joined contract passes
after those fixes. It has now passed on two independent pristine Fedora 44
x86_64 guests with SELinux enforcing, including a full rerun on the second
guest after a real reboot with Docker recovering automatically. The second
guest's QEMU CPU passthrough exposes the x86-64-v2 features needed by the
pinned Open WebUI image. Synthetic runner/HTTP contracts also pass expired
lease UNKNOWN suppression, failure redaction, ten concurrent maximum-quota
requests with replay, and rollback of a schedule after its due item was
observed. These results prove the Phase 3 runtime composition on two clean
hosts; they do not prove full HADES installation or production provisioning.
Keep schedules inactive and production unchanged.

On a fresh Fedora 44 x86_64 Phase 3 test host, first expose the x86-64-v2 CPU
baseline and run `scripts/prepare-hades-host.sh --apply` as root. The joined
test runs Docker as the invoking user. On this disposable test host only,
granting that user membership in `docker` enables the test but is
root-equivalent. Run `sudo usermod -aG docker "$USER"` and start a new login
session before continuing. From the HADES checkout, the rest of the test-host
setup is:

```sh
HADES_REPO=$(pwd)
sudo dnf install -y python3.13 nodejs npm fontconfig nspr nss atk at-spi2-atk \
  libX11 libXcomposite libXdamage libXext libXfixes libXrandr mesa-libgbm \
  libxcb alsa-lib at-spi2-core
curl -LsSf https://astral.sh/uv/install.sh | sh
npm install --prefix "$HOME/hades-playwright" playwright@1.63.0
"$HOME/hades-playwright/node_modules/.bin/playwright" install chromium
bash scripts/build-open-webui-artifact.sh hades-open-webui:0.11.1-hades-reconstructed
git clone --filter=blob:none --depth 1 --branch v2026.9.11 \
  https://github.com/NousResearch/hermes-agent.git "$HOME/hermes-clean"
cd "$HOME/hermes-clean"
UV_PROJECT_ENVIRONMENT="$HOME/hermes-clean/.venv" \
  UV_PYTHON=/usr/bin/python3.13 "$HOME/.local/bin/uv" sync \
  --extra all --extra hindsight --locked
cd "$HADES_REPO"
HADES_PHASE3_PLAYWRIGHT_MODULE="$HOME/hades-playwright/node_modules/playwright" \
HADES_PHASE3_HERMES_PYTHON="$HOME/hermes-clean/.venv/bin/python" \
HADES_PHASE3_HERMES_BIN="$HOME/hermes-clean/.venv/bin/hermes" \
  bash scripts/test-phase3-n8n-epsilon-hermes-runtime.sh
```

This test path obtains upstream Hermes 0.21.2 source directly from its
`v2026.9.11` Git tag and uses the locked project dependencies; it does not copy
a developer virtual environment. The HADES reconstruction installer uses the
same pinned upstream release archive and verifies its SHA-256 from
`config/versions.env` before creating the Hermes environment.

The authenticated browser subtest uses Playwright supplied by the test host.
Install Playwright 1.63.0 and set `HADES_PHASE3_PLAYWRIGHT_MODULE` to its Node
module path when running the script; `HADES_PHASE3_PLAYWRIGHT_VERSION` can
override the expected version for an intentional test update. The harness
does not depend on a developer home-directory path. Install Hermes from the
manifest-pinned source archive with
`scripts/install-hermes-artifact.sh` before running the joined contract on a
fresh host. The canonical host preparation installs the exact `uv` version in
`config/versions.env` and Python 3.13 for the pinned Hermes release. Set
`HADES_HERMES_PYTHON` only when deliberately using another supported Python
3.11–3.13 interpreter; Python 3.14 is rejected before installation begins.
