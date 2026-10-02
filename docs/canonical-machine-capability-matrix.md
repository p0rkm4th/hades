# Canonical machine capability matrix

The canonical physical inventory and its current observations belong in the
private `hades-infra` repository. This public repository documents only the
schema and interpretation rules; it must not contain a deployment's machine
names, addresses, MACs, serials, hardware layout, SSH details, or current
health observations.

A private matrix should retain, per stable resource ID:

- intended identity, role, and topology from NetBox;
- observed CPU, memory, GPU, storage, operating system, and driver data;
- runtime state from Proxmox;
- service availability from Kuma or service-native health checks;
- inference endpoint, installed models, current residency, and retrieval time;
- evidence source, timestamp, and limitations for every mutable observation.

Do not use an old matrix as a live status source. Missing, stale, or
contradictory evidence remains `UNKNOWN`, `STALE`, or `CONTRADICTORY` rather
than becoming green by default. Public tests use synthetic infrastructure and
do not encode a real deployment's topology.
