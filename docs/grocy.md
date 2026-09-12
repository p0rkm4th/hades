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

Integration remains unproven until add/remove/purchase/consume and recipe
shortage workflows are performed through HADES and verified against Grocy's
canonical API after reload.

Upstream references:

- [Grocy setup documentation](https://github.com/grocy/grocy-docs/blob/master/tutorials/setup.md)
- [Grocy REST API specification](https://github.com/grocy/grocy/blob/master/grocy.openapi.json)
- [LinuxServer Grocy image](https://github.com/linuxserver/docker-grocy)
