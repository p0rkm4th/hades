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
inherited message history.
New-conversation, model-mention, and HADES capability-boundary dogfood
remains before DOGFOOD GREEN.

Upstream references: https://docs.openwebui.com/features/channels/,
https://github.com/open-webui/docs/blob/main/docs/features/authentication-access/rbac/permissions.md,
and https://docs.openwebui.com/features/extensibility/.
