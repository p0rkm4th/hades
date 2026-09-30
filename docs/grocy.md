# Grocy integration boundary

Grocy is the canonical household and grocery system for HADES. HADES should
route requests to Grocy and report its live result; it must not create a
second household database in the HADES repository.

Gamma shared-household policy: Grocy inventory and shopping-list state is one
canonical household resource, while Hindsight, conversations, finance, and
files remain subject-scoped. Household mutations are accepted only from a
server-authenticated subject and append bounded actor/operation/target/outcome
metadata to a protected runtime audit file. The audit is not a shadow
inventory, does not contain prompt text, and does not replace Grocy history.
If the pre-mutation audit record cannot be written, HADES fails closed before
changing Grocy. Provider timeouts remain outcome-unknown and require canonical
read-back before retry.

The checked-in recipe uses the maintained LinuxServer image, persists only
Grocy's `/config` directory, binds to loopback port `7003`, and uses synthetic
test state until the owner workflow is accepted. No real household data or
credentials belong in this repository.

The current local test image is pinned to:

```text
lscr.io/linuxserver/grocy@sha256:8449aff56e6b1f34d37affd969cec35ed56fa7daa175c75f923a015b82561d27
```

The maintained `grocy-mcp==0.2.0` server is part of the reconstruction
contract. Its complete Python dependency set is version-locked in
`integrations/grocy-mcp/requirements.lock` and installed into a separate
`/opt/hades-grocy-mcp/venv`, isolated from Hermes. The generated profile
registers only the household and owner tools required by HADES. A tracked
launcher reads the Grocy API key from its protected input file and passes the
value only to the MCP child process. The installer keeps the operator's source
key intact and makes a root-owned, Hermes-group-readable copy under
`HADES_CONFIG_ROOT/secrets/grocy-api-key`; the deployment record points Hermes
to that copy without embedding the key in YAML or systemd.

For a first install, run [`scripts/bootstrap-grocy.sh`](../scripts/bootstrap-grocy.sh)
before preparing the HADES input file. The first visit to the loopback Grocy
listener initializes its database. Change the upstream `admin` / `admin`
password immediately, then issue the HADES key in Grocy's **Manage API keys**
page. Store that issued value in `HADES_GROCY_API_KEY_FILE`; an arbitrary
random string is not a usable API key. `hades-doctor.sh` verifies the actual
read-only stock tool call without printing returned household state.

The private test deployment has now verified add/remove/correction, purchase,
consume, recipe fulfillment, recipe add-missing, duplicate prevention, and
Grocy/Hermes restart persistence through the HADES owner API against Grocy's
canonical API. A fresh synthetic mobile browser session also verified a
read-only stock question through the normal HADES chat surface and matched it
against Grocy's canonical stock. A separate synthetic mobile browser mutation
also produced exactly one canonical unfinished shopping-list row, and the
chat result remained visible after reload. This closes the founding Grocy
milestone; additional pantry edge cases and local-model wording remain future
hardening.

The same synthetic mobile session also asked whether the two-unit test recipe
was makeable. HADES rendered the available result, while Grocy's canonical
recipe, ingredient, and stock records showed the matching two-unit requirement;
the result remained visible after reload.

The authenticated disposable household acceptance also checks recipe
ingredients expressed in different quantity units. HADES aggregates repeated
positions for the same product, converts recipe quantities to Grocy's stock
unit, subtracts canonical stock, then converts the shortage to the product's
purchase unit before adding it to the shared list. Canonical read-back verifies
the purchase-unit entry, and a retry does not duplicate it. If either unit
conversion is absent or the recipe uses an unsupported stock-fulfillment flag,
HADES refuses before writing. The same UI fixture verifies a resolved
conversion and a missing conversion side by side.

When a user asks which saved recipes can be made with food expiring soon, the
read path intersects Grocy items with best-before dates in the next seven days
and recipes that use those items. It then checks every ingredient against
current stock and compatible units before naming a recipe as makeable; partial
recipes are reported with missing or unverifiable ingredients, and already
expired stock is excluded. This is read-only. The pinned Hermes runtime test
covers the synthetic “Which recipes can we make with food that will expire
soon?” case. Production VM 802's active overlay still lacks the route call
site, so this current-source behavior has not been live-accepted there.

An informal read-only shopping-list question also rendered an empty-list
answer, matching Grocy's canonical empty collection.

The browser dogfood also covered an informal/profane stock question about
eggs. HADES correctly reported no eggs, matching Grocy's live stock response;
the result persisted after reload.

Dogfood also exposed a recipe-authoring gap: the production allowlist omitted
recipe authoring even though the installed Grocy MCP already supported it.
The allowlist now exposes recipe listing/details, create-by-product-name,
metadata update, ingredient add, and ingredient removal. Recipe creation is
still an explicit Grocy mutation; unresolved product names are reported rather
than silently inventing pantry products.

Recipe creation and ingredient/serving edits are owner-scoped. Authenticated
household turns retain recipe reads, feasibility, and explicit missing-item
shopping-list actions, but the Hermes API route removes recipe URL/paste,
generic and owner-specific recipe creation, update, ingredient-edit, and
serving-count tools before model invocation. The scope filter also applies to
the deferred search/dispatch bridge, so neither dynamically selected schemas
nor raw `tool_call` can bypass the initial session boundary. The generic
`recipe_create_tool` is registered on the shared Grocy server, so it is
filtered independently of the dedicated owner recipe-authoring MCP.
Sessions without a verified owner or household subject receive no Grocy tools.
`scripts/test-grocy-tool-scope-hermes-runtime.sh` drives the actual Hermes
`run_conversation` route with synthetic authenticated owner and household
subjects and captures the tools sent to the model. It proves owner recipe
authoring tools stay available except for the raw serving-count writer,
household sessions retain only recipe reads and shared shopping-list actions,
and no tool call or Grocy write occurs during catalog inspection. It also
proves deferred search omits the generic creator and a household raw
`tool_call` cannot dispatch it, while owner discovery remains available. The same
runtime contract verifies that serving changes preview before a separate
chat-scoped confirmation, cancellation does not write, another chat cannot
confirm the pending change, stale previews fail closed, unknown write outcomes
are reported honestly, and household sessions cannot start the mutation.

An API-level synthetic acceptance then created a uniquely named recipe with
one resolved ingredient through the normal HADES owner API. A narrow
HADES-owned companion MCP adapter set the recipe to two servings, and
canonical Grocy verification confirmed `base_servings=2`; the recipe and its
ingredient were then removed after verification. No shadow recipe state is
maintained in HADES. The disposable authenticated Alpha owner-browser journey
now covers the complete recipe-authoring sequence: create by product name
through the pinned Grocy MCP, remove and restore an ingredient, calculate the
shortage from canonical Grocy stock, add only the missing egg to the shared
shopping list, and verify the result through canonical read-back. A synthetic
Grocy fixture failure in DELETE handling was fixed after the MCP correctly
surfaced the connection error; the model fixture now reports tool errors
instead of inventing success. The focused UI test passes with synthetic
identities and disposable Grocy state. Separate authenticated Alpha/Beta
tool-search evidence confirms owner authoring tools are unavailable to the
household identity. Production and real household recipe data remain unchanged
and review-gated.

The serving adapter is registered as a second private stdio MCP server beside
the maintained Grocy server. It exposes only `recipe_set_servings`, validates
positive bounded integers, resolves an exact recipe name or numeric ID, and
reads the canonical recipe back after every update. A timeout is reported as
`OUTCOME UNKNOWN`; the adapter never retries an uncertain mutation.
A connection failure before the PUT, or a definitive 4xx validation response
from the PUT, is classified as `FAILED`; timeouts or verification failures
after a mutation attempt remain `OUTCOME UNKNOWN` and require canonical
reconciliation before retry.
Repeated verified requests and an immediate adapter restart are stateless:
each request resolves and reads Grocy's canonical recipe before success.
The deployed interpreter was also exercised through a real MCP
`initialize`/`list_tools` exchange; the companion registered exactly
`recipe_set_servings`. This catches transport/signature failures that isolated
function tests cannot see.

The raw `recipe_set_servings` writer is removed from the Hermes model catalog.
HADES now resolves an exact recipe in a read-only preview, stores the preview
under the authenticated actor and server conversation in the shared lifecycle
SQLite store, and asks for explicit confirmation. Confirmation re-reads
canonical `base_servings` and applies only if it still matches the preview;
the result is verified from Grocy. A different chat cannot consume the pending
confirmation, cancellation leaves Grocy untouched, stale state requires a new
preview, and an uncertain write tells the user to check Grocy before retrying.
The disposable Hermes runtime contract covers these transitions. Authenticated
synthetic Alpha owner-browser acceptance against disposable live Grocy now
covers the complete serving path: the preview makes no write; a same-owner
confirmation from an independent browser context and chat is rejected without
changing canonical state; a separate household account is denied an explicit
serving change with no Grocy request; the original chat can then confirm its
preview, producing exactly one Grocy update and canonical read-back; and a
second preview is canceled without a write. The browser harness dismisses the
pinned Open WebUI update notice before interaction and uses a normal non-forced
send click. Authenticated Alpha/Beta deferred
`tool_search` acceptance also confirms owner recipe-authoring discovery remains
owner-scoped, while the raw serving writer is denied before dispatch for both
scopes. These are disposable synthetic acceptance results; production and real
household recipe data remain unchanged and review-gated.

### Reconstructed Hermes registration and key handling (2026-09-29)

The canonical Hermes profile now explicitly registers the bounded serving
adapter beside Grocy and passes `HADES_GROCY_API_KEY_FILE` by path. The adapter
accepts only a regular mode-0600 or mode-0640 file, rejects symlinks and
multiline/empty values, and does not log the key. A protected environment-key
fallback remains for existing private deployments. The reconstruction test
checks that the profile registration and file-backed credential stay present;
production remains unchanged.

Every Grocy mutation must distinguish preview, confirmed apply, and outcome
unknown. A timeout, connection loss, or malformed upstream response is never a
success; HADES must report the uncertain outcome and check Grocy's canonical
state before retrying. A successful mutation must include the canonical result
used for the owner-facing acknowledgement, and repeated requests must follow
Grocy's duplicate-folding/idempotency behavior rather than create an
unverified second row.

In a fresh synthetic chat, Hindsight first recalled the test recipe label and
a following explicit Grocy turn checked current stock and reported the recipe
as makeable. The single-turn composition path now also performs both tool
turns and renders correctly in the owner UI; the result survives reload.

The compatibility overlay also preserves Grocy intent across conversational
follow-ups: a natural “remove it” correction now routes to Grocy when the
preceding turns establish the grocery domain. This was regression-tested in a
synthetic mobile chat and verified against the canonical shopping-list API.

Grocy is intentionally not shown as an Open WebUI-native integration. Its MCP
tools are private to Hermes, which keeps Grocy as the canonical household
system while allowing the owner to use ordinary HADES chat requests.

The deployment applies narrow compatibility fixes for the selected maintained
Grocy MCP package: duplicate shopping adds fold into an existing row, recipe
fulfillment uses Grocy's stable missing-product count, recipe add-missing sends
the required JSON body, and stock-consume is explicitly allowlisted. These are
deployment-local overrides and contain no owner data.

Upstream references:

- [Grocy setup documentation](https://github.com/grocy/grocy-docs/blob/master/tutorials/setup.md)
- [Grocy REST API specification](https://github.com/grocy/grocy/blob/master/grocy.openapi.json)
- [LinuxServer Grocy image](https://github.com/linuxserver/docker-grocy)

### Post-mutation correction and recipe inventory wording (2026-09-26)

The authenticated synthetic household flow now checks a user correction after a
shopping-list add has completed. HADES states the verified list change, makes
clear that no recipe changed, preserves owner-only recipe editing, and offers
removal as an explicit next action without silently applying it. Alpha/Beta
catalog inspection confirmed the household correction turn has no recipe
create/update/ingredient tools. The canonical audit observed one intended list
write and no recipe mutation.

A runtime regression also fixed broad inventory wording such as “Which recipes
can we make right now?” Previously, an unanchored specific-recipe matcher
interpreted “right now” as a saved recipe name. Inventory intent now takes
precedence; the runtime test verifies canonical recipes and stock are read.
Both `scripts/test-grocy-read-routing-hermes-runtime.sh` and
`scripts/test-grocy-authenticated-household-ui.sh` pass on synthetic fixtures.
This is disposable acceptance, not production deployment or owner acceptance.

### Read-only recipe next-step suggestion (2026-09-26)

For a specific saved recipe that is confirmed unavailable only because of
known shortages, HADES now offers one adjacent step: it can add only the
missing items to the shared shopping list if the user wants. The offer follows
the canonical stock answer and makes clear that no change occurred. It is not
shown when unit compatibility is unknown. Runtime and authenticated
Alpha/Beta/Gamma UI checks verify the exact wording, canonical reads, unchanged
stock, and unchanged shopping list. This is the first synthetic Beta
preemptive-helpfulness experiment; real user reaction remains unmeasured.

The authenticated synthetic household journey also checks declining that
optional shopping-list offer. A short “No thanks” immediately after the offer
receives a deterministic no-action acknowledgment, without another Grocy API
call. Compound questions and stale offers do not match this shortcut. The Hermes
runtime contract covers both history shapes used by the gateway; the full
Alpha/Beta/Gamma authenticated household UI passes with the decline included.
This validates only the synthetic interaction and does not measure a real
household member's response.

### Confirming an optional recipe shortage offer (2026-09-26)

An authenticated synthetic household flow now accepts a standalone “Yes,
please” after the immediate recipe-shortage offer. The pending confirmation is
bound to the authenticated subject and server conversation for ten minutes;
the route rechecks the same canonical recipe/stock result before using the
existing locked add path and canonical shopping-list read-back. A changed stock
snapshot, cross-chat confirmation, compound affirmative, decline, missing
chat identity, or unavailable canonical state cannot cause a write. The UI
acceptance verified one eggs-list write, a later explicit retry reported the
existing row, and Alpha/Beta/Gamma isolation remained green. The focused
runtime check also verifies that known past-best-before stock does not suppress
a needed shopping-list addition. Report:
`/tmp/hades-grocy-household-ui-1811246.json` (mode 0600). No production
endpoint or household state was used.
