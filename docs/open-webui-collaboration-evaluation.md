# Open WebUI collaboration evaluation

Status: SELECTED / STAGED.

Open WebUI's maintained Channels feature is the preferred shared-conversation
surface. It provides persistent shared spaces, explicit membership and access
control, model mentions, threads, and a shared timeline. HADES should compose
that feature rather than create a second chat or channel database.

## HADES boundary

| Concern | Authority |
|---|---|
| Shared messages, membership, threads, and reload | Open WebUI |
| Requesting actor and group membership | LLDAP/Open WebUI authentication |
| Private personal context | Per-user Hindsight |
| Shared pantry truth | Grocy |
| Finance, Agent Zero, homelab, and administration | Owner-only capability policy |

Channel membership never transfers the initiating actor's authority. A Beta
message in a channel containing Alpha does not receive Alpha's memory, finance,
Agent Zero, homelab control, or administration capabilities. Channel history
also does not become a shared Hindsight bank automatically.

## Staged acceptance sequence

1. Enable Channels in a disposable copy of the pinned Open WebUI deployment.
2. Create a private household channel with explicit Alpha/Beta membership.
3. Exercise ordinary human messages, model mentions, replies, corrections,
   reload, and a new conversation.
4. Verify Grocy answers use shared canonical state.
5. Attempt Beta access to private memory, finance, Agent Zero, and homelab
   capabilities; each must be denied before tool selection.
6. Verify channel history remains in Open WebUI and private memory remains
   subject-scoped.

Production enablement is serialized separately from Hermes promotion and
requires the Open WebUI migration and rollback contract. No production setting
was changed by this evaluation.

The pinned HADES artifact's source contains the ENABLE_CHANNELS setting and
the Channels API is present. Its unauthenticated public config response omits
the admin-only feature flag, so absence of that flag from /api/config is not
evidence that Channels are unavailable. The authenticated disposable
acceptance in `scripts/test-open-webui-channels-fixture.sh` passes: synthetic
Alpha sees Channels enabled, creates a private household channel, and
anonymous channel access is denied. The same fixture also proves synthetic
Beta membership, shared posting, Alpha read-back, and message persistence
after a disposable Open WebUI restart. It also verifies that Beta membership
does not grant admin configuration access or standard-channel creation.
The fixture also verifies a newly created shared conversation starts without
inherited message history. The pinned 0.11.1 artifact had an upstream Channels
composition defect: its model-response handler awaited the chat-completion
endpoint but did not consume the returned streaming response. The HADES image
now applies an exact build-time compatibility patch, guarded by the pinned
source shape, so channel model responses are actually persisted and emitted.
The `scripts/test-open-webui-channel-model-fixture.sh` fixture proves the
provider request, streamed response, and persisted channel reply against a
disposable backend. The overlay
capability contract separately verifies that a household session removes
finance and Agent Zero tools before model invocation while preserving them for
owner scope.

The companion `scripts/test-open-webui-private-chat-soak.sh` exercises the
real pinned image's saved-chat route. It creates Alpha through initial signup,
creates Beta through the administrator-only user route, sends a synthetic
OpenAI-compatible completion, verifies Alpha persistence, rejects Beta
retrieval of Alpha's chat, and verifies persistence after WebUI restart.

Upstream references: https://docs.openwebui.com/features/channels/,
https://github.com/open-webui/docs/blob/main/docs/features/authentication-access/rbac/permissions.md,
and https://docs.openwebui.com/features/extensibility/.
