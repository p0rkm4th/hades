# Gamma bounded self-service workloads

Gamma starts self-service with a plan-only product contract. The current
policy allows only the approved `minecraft`, `website`, and `linux-sandbox`
templates, validates fixed resource shapes, enforces per-owner quotas, records
ownership and explicit sharing, and requires owner confirmation. It does not
contact Proxmox, accept raw VM IDs/images/scripts, expose host mounts or
network configuration, or grant users hypervisor authority.

The repository now also contains a constrained provisioner boundary that accepts
only a confirmed `WorkloadRequest`, uses policy-owned placement, permits
creation only by the workload owner, and caches terminal canonical outcomes so
an unknown response is never blindly retried. The live executor uses the
existing least-privilege Proxmox broker, maps only the approved template, waits
for asynchronous clone/start tasks, and reconciles canonical state. A
disposable disposable clone create/read-back passed and was purged. The authenticated
owner UI now also has a bounded “show my servers” path and lifecycle adapter
for status/start/stop/restart/delete. Inventory is least-privilege: the broker
does not require pool-audit permission; managed guests are identified by the
explicit `hades-managed` tag, approved node, and approved VMID range. A tagged
created test guest was created and reconciled through the live product path, then stopped
and purged. A durable authorization-only registry now records the authenticated
owner and explicit grants; it contains no VM runtime state or private user
data. The owner DOM path has now passed status, explicit restart confirmation,
and explicit delete confirmation, including stop-before-destroy reconciliation
and registry removal. The owner path can explicitly share and revoke a workload
with configured synthetic household subjects. Authenticated DOM dogfood passed:
Household A saw and could request an approved action on the shared sandbox,
Household B could not see it, revocation immediately removed Household A's
visibility, and the owner then deleted the workload with canonical cleanup.
Restart uses a bounded graceful reboot with a confirmed stop-start fallback
when guest-agent reboot is unreliable.

The Rocky 10.2 candidate was rejected after its x86-64-v2 userspace panicked
on hypervisor host's multi-core CPU before cloud-init or networking. The approved template
candidate is now Debian 12 GenericCloud on hypervisor host approved Linux sandbox template, with a derived image
adjustment for Proxmox's generated `eth0` cloud-init network stanza. A
disposable clone reached SSH, completed cloud-init, and reported an active
QEMU guest agent; it was purged after acceptance. The constrained credential
and canonical live executor gate are green; product wiring and household
dogfood remain.

## Minecraft provisioning readiness — 2026-09-28

A strict-host-key read-only check of the live Hermes process found only the
`linux-sandbox:853` alias in `HADES_PROXMOX_TEMPLATE_MAP`; therefore production
has no approved Minecraft VM template available to this flow. The local source
now inspects the bounded read-only template/placement catalog before persisting
a request. When the Minecraft alias or approved placement is missing, it
refuses plainly and creates no pending confirmation. Pinned Hermes runtime
and authenticated disposable Alpha UI checks cover the refusal. A narrow live
overlay guard now also recognizes the exact lost-plan Minecraft continuation
and refuses before model or provisioning calls when that alias is absent; the
previous live artifact is retained root-only for rollback. This guard does not
create a VM or change firewall rules. The complete tracked continuation/plan
implementation remains newer than the deployed overlay. Generic server wording
now asks what workload is intended; unsupported Factorio/Palworld and
mixed-workload requests fail closed. A configured alias alone does not prove
Minecraft or guest IP readiness.

The tracked Hermes confirmation response reports successful creation as a
running VM only, explicitly says it has not verified Minecraft or read the
guest IP, and confirms that no firewall rule changed. Unknown or partial
execution outcomes tell the user not to retry until an administrator
reconciles state; raw adapter error text is not shown. This source/runtime
acceptance remains separate from production deployment and Minecraft template
configuration.

The first configured provisioning response now includes the concrete bounded
plan immediately, followed by the explicit `Create it` confirmation instruction.
The next-turn continuation can repeat that plan after a worker change or lost
pending state. Minecraft, website, and Linux sandbox plans state workload
specific verification limits; only the Minecraft plan mentions TCP 25565, and
none claims a guest address or firewall readiness without a supported readback.

The authenticated disposable cross-worker UI test now exercises the complete
request → `Perfect, continue` → `Create it` flow as synthetic owner Alpha across
two Hermes workers. A loopback-only Proxmox API fixture performs the bounded
clone/configure/start/status sequence and a temporary ownership registry
records the synthetic guest. The browser verifies that HADES reports only the
running VM, says Minecraft and guest IP are unverified, and confirms no firewall
rule changed. The test makes no model inference for the provisioning turns;
its container, volume, fixture server, and ports are removed after the run.
This is authenticated synthetic acceptance, not production creation or proof
that a Minecraft template/application is installed.

### Lost-plan dogfood recheck — 2026-09-28

The owner repeated the two-turn Minecraft request/“Perfect, continue” flow;
production returned a generic greeting after the approval. The local pinned
Hermes contract passes, including transcript recovery to a read-only plan when
pending state is lost. A strict-host-key inspection of HADES guest confirmed that
active `hades-hermes.service` uses
`$HADES_HOME/generated-full/config/overlay`; its template map contains only
`linux-sandbox:853`, not Minecraft.

The deployed detached checkout is at `b102dfd` with 18 dirty paths. Its Hermes
source hash is `1863ed16573b7c040b78de98e7a3e6ad4463efb167c55c3b2c92bdc4d0a3c12a`,
which differs from the active overlay hash. The stored provenance record was
generated on 2026-09-24 and does not identify the active runtime artifact. The
deployed checkout source also lacks the tracked transcript-recovery hook.

The exact active artifact plus the continuation guard was run through pinned
Hermes with the supplied transcript. It returned a plain Minecraft-unconfigured
refusal with `api_calls=0`; no model or provisioning call occurred. The
authenticated disposable Task Attention UI acceptance also passed. Live
overlay SHA-256 is now
`d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`; Hermes is
active with zero systemd restarts and `/health` reports Hermes 0.21.2 healthy.
The previous active overlay is retained at
`$HADES_HOME/generated-full/config/overlay/.sitecustomize.pre-minecraft-continuation.25c85b9`
as root-owned mode 0600.

This confirms a deployment artifact mismatch and leaves HADES-managed Minecraft
creation unavailable. The chat did not create a VM, and the adapter still cannot
verify a provisioned guest or read its IP. A separate current check on management host
found the existing vanilla server healthy at `<PRIVATE_LAN_ADDRESS>:25565/TCP` and the
existing Prominence II server healthy at `<PRIVATE_LAN_ADDRESS>:25566/TCP`; both LAN
TCP connections succeeded. These services predate the chat and are not HADES
self-service workloads. External firewall/port-forward status remains
unverified, and no firewall change was made. The narrow overlay repair does not
close deployment provenance or configure a new Minecraft template.

### Authenticated continuation route recheck — 2026-09-28

The exact lost-state flow passed again through the disposable authenticated
Open WebUI/Hermes UI with the current tracked overlay: the test removed only the
synthetic Alpha pending record between turns, then sent “Perfect, continue”.
HADES recovered the bounded plan, made zero model calls, and performed zero
Proxmox, VM, or firewall actions.

A read-only copy of the live overlay was separately hashed and used for a
second UI attempt. That attempt did not reach the chat flow: the local Hermes
child interpreter lacked `prompt_toolkit`, overlay initialization failed, and
the test gateway returned HTTP 503. This is an invalid deployed-artifact UI
comparison, not evidence that the live chat flow passes or fails. The owner’s
reported generic greeting remains unresolved against the live artifact. No
production service, VM, or firewall was changed.

The authenticated UI regression now also opens a separate fresh Alpha chat
while the original chat still has its pending Minecraft plan. A context-free
“Perfect, continue” receives an explicit request to restate the workload;
the original chat's pending plan is not reused. The full synthetic UI report
records zero model and infrastructure calls for both the transcript-recovery
and context-free paths.

Static comparison of the read-only active overlay confirms that its narrow
Minecraft guard has only the transcript-backed refusal path; it has no
context-free continuation refusal. This is a plausible explanation for the
reported generic reply when chat history is absent, but the private production
transcript was not inspected and the precise live trigger is unconfirmed. The
active-artifact authenticated UI attempt remains invalid because its local
runtime could not initialize the overlay dependencies. No production change
was made.

### Active overlay context-free acceptance result — 2026-09-28

A synthetic authenticated UI run using a read-only copy of the exact active
overlay and the pinned Hermes 0.21.2 Python runtime reached the fresh-chat
continuation path. The active artifact did not return before inference: the
isolated unavailable model endpoint was called once (`api_calls=1`) and the
turn was interrupted during that call. The model endpoint was intentionally
unreachable; this test therefore proves the active artifact fails to fail
closed in the context-free case, but it does not reproduce the owner's exact
generic wording.

The same UI scenario passes with the current tracked source: the fresh chat
receives a request to restate the server, with zero model calls. The test
workspaces, synthetic accounts/state, and containers were removed afterward.
This is a source/runtime drift defect. No live service, VM, or firewall was
changed.



### Read-only production provenance recheck — 2026-09-29

A fresh owner dogfood repeated the Minecraft request → plan → “Perfect,
continue” flow; the live assistant again returned a generic greeting. No new
VM, Minecraft process, IP address, or firewall endpoint resulted. No production
write was attempted.

Strict-host-key SSH to the documented HADES Core 802 account confirmed
`hades-hermes.service` active with zero recorded restarts. Its process runs from
`$HADES_HOME/Hades-reconciled-b102dfd` at detached revision `b102dfd`; that
checkout has local modifications and untracked paths. The deployed checkout's
`hermes/sitecustomize.py` SHA-256 is
`1863ed16573b7c040b78de98e7a3e6ad4463efb167c55c3b2c92bdc4d0a3c12a`. The
service loads `PYTHONPATH=$HADES_HOME/generated-full/config/overlay`, whose
active `sitecustomize.py` SHA-256 is
`d827e9dbb7373d9889e442094a169260b60293d85169866f9848378648febb1a`; a
read-only search found no tracked transcript-recovery or fail-closed
context-free continuation hook in that active overlay. Its template map is
`linux-sandbox:853` only. The documented provenance endpoint at `<PRIVATE_LAN_ADDRESS>:8643` returns `READY`, but
its record is stale: generated `2026-09-24T07:54:33Z`, HADES `bcd81f4`, and
overlay hash `1863ed16573b7c040b78de98e7a3e6ad4463efb167c55c3b2c92bdc4d0a3c12a`.
The reported overlay hash matches the deployed checkout source file, not the
active `d827e9db…` overlay; its HADES revision differs from deployed checkout
`b102dfd`. The separate private-deployment JSON is not the file served by this
endpoint.

The current tracked Hermes source SHA-256 is
`75c53a3907aba22a78d14723933b2a891e925fb758a7f60dcc2745a967499b90`.
`bash scripts/test-self-service-continuation-hermes-runtime.sh` passes the
first-turn plan, same-chat continuation, lost-pending-state recovery,
context-free refusal, unconfigured-template refusal, and no-write assertions
against this source. This remains source/runtime evidence, not live acceptance.
No production files, service, VM, or firewall were changed.

### Repeated owner-provided lost-plan transcript — 2026-09-29

The owner supplied the exact two-turn UI exchange again. The first assistant
turn said it would show the template, bounded resources, placement, and sharing
plan, but did not actually show those details or provide an explicit
confirmation action. After the owner replied “Perfect, continue,” Hermes
returned a generic greeting. This is both an incomplete confirmation preview
and a lost-continuation user failure. No server, VM, address, or firewall
endpoint was created.

The current tracked Hermes 0.21.2 source/runtime test was rerun against the
matching request and transcript. It passes the full read-only plan recovery,
including template/placement revalidation, no model call, and no infrastructure
write. That does not supersede the observed production failure: the active
overlay is a mixed artifact without the tracked recovery helper, and its
provenance/rollback composition remains unresolved. Do not deploy the source
fix until that gate is closed. Separately, production has no configured
Minecraft template/placement and the adapter cannot verify Minecraft process
health or read back a guest IP, so it cannot fulfill this original new-server
request today. No external firewall action is authorized or implied.

### Current-turn routing regression found on Guest C — 2026-09-28

An authenticated synthetic Alpha memory-retain turn on reconstruction Guest C
returned the managed-server adapter error instead of handling the current
request. The same response reproduced through the Hermes API with a new
conversation ID. Guest C's installed overlay matched its repository checkout;
the route took the last user message from the supplied history before
considering the current turn, so an earlier server question could preempt an
unrelated request.

The managed-server route now uses the current `user_message` and consults
history only if that value is empty. The Hermes 0.21.2 runtime test reproduces
the stale-server-history case before the fix and now verifies that current
explicit memory intent reaches its own route without a model or server call.
Adjacent Hindsight memory, self-service, and Task/server runtime contracts
pass. The Guest C application has not yet been rerun against this fix; it
remains discovery build A. No production service or state was changed.

During Guest C setup, the Open WebUI database initially exposed no selectable
model even though its configured Hermes endpoint and API key were valid. The
synthetic authenticated test explicitly configured the Hermes connection as
Alpha administrator. The operator-facing setup instructions should make this
first-use model activation step explicit; this test configuration is not
owner acceptance.

### Minecraft request-plus-endpoint intent correction — 2026-09-29

The exact dogfood wording explicitly asks to “spin up” a Minecraft server and
also asks for the resulting IP/port. The prior endpoint-first route treated any
request mentioning a port or firewall as an inventory-only question, which
discarded the create intent. It now sends explicit provisioning verbs through
the bounded plan flow; standalone “what is the Minecraft server IP and port?”
questions continue to use read-only inventory. A plan must still be shown,
“Perfect, continue” only recovers that no-write plan, and the separate “Create
it” confirmation is required before the synthetic provisioning adapter runs.

PASS: endpoint-routing contract and pinned Hermes continuation runtime pass.
The authenticated disposable UI used the exact owner wording across Hermes
workers A → B → A, showed the same 4-core/8-GiB/40-GiB synthetic plan after
“Perfect, continue,” and created only after “Create it.” The loopback Proxmox
fixture reported VM running, while the response correctly withheld any claimed
Minecraft readiness, guest IP, or firewall update. No live route, VM, endpoint,
or firewall was touched. This is source-level synthetic acceptance; production
still has the mixed `d827e9db…` overlay and no configured Minecraft template.
