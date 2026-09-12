# Grocy integration boundary

Grocy is the canonical household and grocery system for HADES. HADES should
route requests to Grocy and report its live result; it must not create a
second household database in the HADES repository.

The checked-in recipe uses the maintained LinuxServer image, persists only
Grocy's `/config` directory, binds to loopback port `7003`, and uses synthetic
test state until the owner workflow is accepted. No real household data or
credentials belong in this repository.

The current local test image is pinned to:

```text
lscr.io/linuxserver/grocy@sha256:8449aff56e6b1f34d37affd969cec35ed56fa7daa175c75f923a015b82561d27
```

The private test deployment has now verified add/remove/correction, purchase,
consume, recipe fulfillment, recipe add-missing, duplicate prevention, and
Grocy/Hermes restart persistence through the HADES owner API against Grocy's
canonical API. A fresh synthetic mobile browser session also verified a
read-only stock question through the normal HADES chat surface and matched it
against Grocy's canonical stock. A separate synthetic mobile browser mutation
also produced exactly one canonical unfinished shopping-list row, and the
chat result remained visible after reload. Broader pantry coverage remains
open.

The same synthetic mobile session also asked whether the two-unit test recipe
was makeable. HADES rendered the available result, while Grocy's canonical
recipe, ingredient, and stock records showed the matching two-unit requirement;
the result remained visible after reload.

An informal read-only shopping-list question also rendered an empty-list
answer, matching Grocy's canonical empty collection.

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
