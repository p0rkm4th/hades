# Agent Zero interactive Operator evaluation

Status: SELECTED / STAGED.

The native Agent Zero UI is an advanced owner operator surface, distinct from
the normal bounded Hermes-to-Agent-Zero delegation path. The first useful
contract is a dedicated native tab reached through a protected private route.
Embedding is explicitly out of scope until native behavior is proven.

## Current deployment finding

Agent Zero is bound to 127.0.0.1:7002 and has no tracked reverse proxy or
supported Open WebUI global navigation-link mechanism. Open WebUI Actions are
message-level server-side extensions; they are not a safe substitute for
server-side route authorization and do not provide a general owner-only
launcher. Theme JavaScript must not become an authority-bearing navigation
layer.

The reusable fail-closed policy contract is in
integrations/operator-access/policy.py. It accepts only a trusted proxy
assertion plus an owner group, rejects household-only identities, and validates
the forwarded path. `integrations/operator-access/session_auth.py` now verifies
the forwarded Open WebUI session and resolves the same subject against current
LLDAP owner/admin membership. It is an authorization library, not a listening
proxy, and does not forward traffic.

## Required smallest implementation

- a private reverse-proxy route to the native Agent Zero endpoint;
- server-side owner/group authorization independent of launcher visibility;
- preserved Agent Zero native authentication;
- WebSocket, streaming, upload, download, and long-lived-session forwarding;
- a dedicated-tab launcher added through a supported Open WebUI mechanism when
  one exists for the deployed version;
- no new Agent Zero mounts, credentials, Docker socket, host root, or public
  listener.

Until that route and its trusted identity source are selected, the correct
state is staged rather than dogfood-green. The existing bounded MCP bridge
remains the default operator path and is unaffected.

Upstream references: https://docs.openwebui.com/features/extensibility/
and https://github.com/agent0ai/agent-zero.

## Pinned Open WebUI extension audit (2026-09-25)

The installed HADES contract pins Open WebUI `0.11.1`. Its upstream source tag
resolves to commit `d3e8bf3405e848cfba377814d0aa7ba7290e414d`. In that exact
tag, `src/lib/components/app/AppSidebar.svelte` contains only the Home and
Chat entries; `src/lib/components/layout/Sidebar.svelte` renders the built-in
chat/model/channel sections and exposes no application navigation extension
slot. The official Extensibility index describes Pipes, Actions, Filters, and
MCP; Actions are message-level and Pipes add selectable models, so neither
provides a supported global Operator launcher.

That release does provide a server-side identity validation endpoint:
`GET /api/v1/auths/` depends on `get_current_user` and returns the authenticated
Open WebUI user's stable `id`, `email`, and `role`. This is a candidate first
hop for a private proxy when the caller's existing session cookie is forwarded
only to Open WebUI. It is not sufficient by itself to authorize Operator
access: a separate live check of mapped `hades-owner` / `hades-admin` LLDAP
membership is still required, with no client-supplied identity or group
headers trusted.

References:

- [Open WebUI v0.11.1 app sidebar](https://github.com/open-webui/open-webui/blob/v0.11.1/src/lib/components/app/AppSidebar.svelte)
- [Open WebUI v0.11.1 chat sidebar](https://github.com/open-webui/open-webui/blob/v0.11.1/src/lib/components/layout/Sidebar.svelte)
- [Open WebUI extensibility](https://docs.openwebui.com/features/extensibility/)
- [Open WebUI v0.11.1 auth session route](https://github.com/open-webui/open-webui/blob/v0.11.1/backend/open_webui/routers/auths.py#L248-L310)

Therefore the pinned release has no supported native launcher hook. Do not
patch its navigation with theme JavaScript or maintain a local UI fork solely
for this feature. The Operator route had a tested server-side identity gate,
but no wired proxy deployment or supported entry path at the time of that
audit. See the current optional gateway status below. Preserve the existing
private Agent Zero listener and bounded MCP delegation path.

## Pinned Agent Zero transport probe (2026-09-25)

The exact image digest from `config/versions.env` was started in a disposable
container on a Docker `--internal` network, with no host volumes and only a
loopback host port. Its startup reached Uvicorn, while a Hugging Face model
probe failed because the isolated container had no egress. The test container
and network were removed after inspection. No authenticated Agent Zero
session was created, and no operator task or model request was submitted.

The unauthenticated app exposes its main UI at `/index.html`; that document
uses root-absolute resources such as `/js/icons.js` and `/vendor/...` alongside
relative resources. The browser API helper normalizes calls under `/api/`, and
the Socket.IO client uses the default root transport path with WebSocket and
polling enabled. A `/operator/` path-prefix mount would therefore send some
assets and API/WebSocket traffic outside the protected route. The native UI
needs a separate root origin, or a tested rewrite for every resource and
transport endpoint; no such rewrite is implemented.

The pinned server names its session cookie `session_<runtime_id>` and its
CSRF cookie `csrf_token_<runtime_id>`, both scoped to `/`. The probe's CSRF
route returned an error object before login, so these cookie behaviors are
confirmed from the pinned source, not from an authenticated browser session.
Because browser cookies are scoped by host rather than port, a second port on
the Open WebUI hostname would share cookies. A production proxy must use a
separate private hostname/origin, or prove bidirectional cookie filtering:
never forward Open WebUI's `token` to Agent Zero, and never send Agent Zero
session/CSRF cookies to Open WebUI. This transport and origin boundary remains
unproven; keep the Operator staged and the production listener unchanged.

## Fresh target native-auth probe (2026-09-26)

The exact pinned Agent Zero image was started without a state mount on a Docker
`--internal` network. The native UI served `/index.html` with root-relative
assets, confirming that it must own a root origin. No HADES or production data
was mounted, no task was submitted, and the disposable network/container were
removed after the probe.

The fresh unmounted instance had neither auth variable in its process
environment nor either key in the runtime dotenv file. The pinned source shows
`helpers.login.is_login_required()` enables native login only when
`AUTH_LOGIN` exists in the Agent Zero dotenv configuration. Repeating startup
with synthetic `AUTH_LOGIN` and `AUTH_PASSWORD` values made `GET /` redirect
to `/login?next=/`. This verifies the upstream native-login gate, but did not
submit credentials or establish an authenticated session.

HADES' tracked `deploy/agent-zero.compose.yaml` currently sets neither
variable. `HADES_AGENT_ZERO_CREDENTIAL_FILE` is validated by the installer and
doctor but is not mounted or consumed by that Compose service. A fresh HADES
Operator route therefore cannot claim to preserve native Agent Zero
authentication until the credential input is wired safely and the existing
bounded MCP delegation path is checked against the resulting auth setting.
Keep the route staged and do not change the default service or production
listener as part of this probe. Remaining acceptance includes actual native
login/logout, private proxy HTTP and WebSocket transport, live owner/admin
authorization and revocation, and a documented disable/recovery path.

With synthetic credentials on the same disposable image, the native browser flow
was exercised: an unauthenticated `GET /` redirected to `/login`; posting the
synthetic login form returned a session cookie; the same cookie reached the UI
with HTTP 200. An unauthenticated request still redirected to login. No Agent
Zero API task was submitted. The pinned `/api/api_message` handler source
separately declares browser auth disabled and API-key auth required. This is
source evidence only: the HADES deployment contract does not currently wire
that API key, and the key-protected endpoint was not invoked.

## Optional native-login input wiring (2026-09-26)

The v2 generated-record install path now accepts the optional
`HADES_AGENT_ZERO_OPERATOR_PASSWORD_FILE`. When supplied, the renderer requires
a regular non-symlink file with mode 0600 or 0640, exactly one line, and a
16-256 character URL-safe password. It generates
`agent-zero-operator-auth.env` with mode 0600, using the fixed native login
`hades-operator`. The tracked Agent Zero Compose contract reads that file only
when the installer exports its generated path; when the input is unset it uses
an empty env file and preserves the current default service behavior. The
doctor checks the source and rendered file without printing its contents.

Validation passed for deterministic rerender, unsafe source permissions,
multiline rejection, removal of stale generated auth when the input is unset,
Compose parsing, and the doctor contract. A disposable instance of the exact
pinned image consumed the rendered env file: no-session `/` redirected to
login; synthetic login established a session and authenticated `/` returned
200. The pinned `/api/api_message` source uses its separate API-key gate and
does not require browser auth; no API task was submitted. The legacy v1 input
path fails clearly if this optional setting is requested.

## Bounded API credential handoff (2026-09-25)

The first direct derivation attempt failed because Agent Zero's persistent
runtime ID is held in its private `/a0/usr/.env`, not reliably supplied by the
container's `A0_PERSISTENT_RUNTIME_ID` environment variable. The installer now
asks the running pinned service for its own `mcp_server_token` after startup,
without displaying it, then atomically writes a mode-0600
`agent-zero-client-auth.env`. The generated Hermes systemd unit optionally
loads that file so the bounded MCP adapter inherits `AGENT_ZERO_API_KEY`.
Reruns preserve the file when the token is unchanged. The doctor compares it
read-only with the running service token; malformed or stale state fails.

On the exact pinned image in an egress-isolated disposable network, the
installer sync helper generated the client env file. The token authenticated
the harmless `lifetime_hours=0` request, which returned the expected input
validation response (HTTP 400); a synthetic wrong token returned 401. The
request is rejected before task creation. No Agent Zero task or production
service was modified. Focused renderer, installer-input, secret-mode,
idempotent-sync, and doctor tests pass.

The optional native auth path now preserves both browser login and bounded API
delegation at the credential boundary. See the gateway status below for the
remaining acceptance gates.

## Optional loopback gateway implementation (2026-09-26)

The v2 generated installer now has an explicitly disabled-by-default
`HADES_AGENT_ZERO_OPERATOR_PROXY_ENABLED` option. When enabled, the operator
must also provide the native Operator password and all three live Phase 3
LLDAP authority inputs: subject/group mapping, loopback HTTP or HTTPS endpoint,
and strict-read-only reader password. The renderer copies the mapping and
reader password into mode-0600 files owned by the Hermes runtime account,
renders an auth service and pinned Nginx Compose record, and moves Open WebUI
to the next loopback port behind a dual-port gateway. The original WebUI port
serves WebUI; the configured Operator port serves Agent Zero at a root origin.
Both are loopback-only. Nginx runs unprivileged with all capabilities dropped
and a read-only root filesystem.

The gateway forwards the Open WebUI session only to Open WebUI's validation
endpoint. Each Operator HTTP request and WebSocket handshake also performs an
uncached current LLDAP owner/admin check. Its Agent Zero upstream receives
only Agent Zero session/CSRF cookies; WebUI requests have those cookie names
removed. The auth service exposes only loopback endpoints and logs no request
metadata. Disable through the operator input and rerun the installer; the
installer stops the auth service/gateway before restoring the configured
direct WebUI bind and removes copied directory-reader credentials. Persistent
application state is not part of the gateway.

Source/render checks and a disposable exact-pinned-Nginx routing fixture pass,
including root-relative assets, cookie isolation, authorization on each new
request/handshake, household denial, owner revocation on subsequent requests,
WebSocket forwarding, and loopback listener configuration. This does not prove
live LLDAP, browser login/logout, the complete HADES runtime, or owner
acceptance. An already-open WebSocket is not revoked mid-connection;
authorization is rechecked on its next handshake. No gateway was installed on
production. The capability remains SELECTED / STAGED until live disposable
HADES acceptance covers sign-in, logout, revocation, disable/recovery, and a
supported launcher or documented direct URL.

## Superseding live disposable acceptance (2026-09-26)

The earlier status above predates the completed gateway acceptance. On the
existing disposable Fedora 44 discovery guest, the full HADES stack was
installed and rerun idempotently with synthetic identities. Alpha/Beta/Gamma
LDAP sign-ins produced stable Open WebUI subjects. The enabled gateway admitted
only mapped Alpha with current `hades-owner` membership; household, invalid or
missing sessions, and Alpha after owner-group revocation were denied. Restoring
the group allowed the next request. Native Agent Zero login/logout and WebUI
identity isolation passed through the gateway. Enabled/disabled doctor checks
passed. Disable recovery removed the auth service, proxy, and port 7004
listener, restored the direct WebUI bind and configuration ACL, and preserved
volumes and synthetic identities. The gateway was left disabled.

This is live synthetic acceptance on a previously used discovery guest, not a
pristine Guest B proof or owner dogfood. Production is unchanged. The optional
gateway remains disabled by default. The pinned Open WebUI release has no
supported global-navigation extension point, so the remaining entry-path work
is a tested/documented owner direct URL or launcher; do not use theme JavaScript
as an authorization-bearing launcher.

The optional direct URL is now documented in `docs/agent-zero.md` for the
HADES host and for an SSH local-forward from an authorized workstation. The
external-workstation tunnel has not been exercised against a live enabled
guest, so it remains an acceptance gap; this documentation does not change the
gateway's staged/disabled-by-default status.

The SSH-forward command is now wrapped by
`scripts/open-agent-zero-operator.sh`. It requires an explicit existing SSH
target, binds only to local loopback, rejects privileged/invalid local ports,
and exits with SSH on connection failure. Its argument/binding contract passes
`scripts/test-open-agent-zero-operator.sh`. This is a local launcher contract,
not evidence that an external workstation reached a live enabled gateway; the
gateway remains staged and disabled by default.
