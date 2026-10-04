# Current blockers and owner gates

This is a public, sanitized handoff. Live machine identities, addresses,
hardware details, credentials, deployment identifiers, and raw acceptance
transcripts are maintained in protected operator records, not this repository.
The statements below summarize the current engineering gates and are not a
live infrastructure probe.

## Release baseline

The HADES public source and deployment records are maintained separately.
Use the current Git and CI state for source truth; use protected deployment
provenance and fresh canonical reads for runtime truth. Older reports are
historical evidence and must not be treated as current status.

## Homelab read reliability — PARTIAL

HADES has a read-only composition path for configured Proxmox, NetBox, Uptime
Kuma, service-native, and inference sources. A fresh owner summary has returned
`PARTIAL` with per-source retrieval times. Current evidence is not broad enough
to claim that every intended node, service, GPU, backup, or network condition
is verified. Some cross-source identity links and intended service records
remain incomplete. Host utilization and network trends are not available for
all targets. Household status correctly remains `UNKNOWN` when no approved
household-safe live check is configured.

Remaining work:

- reconcile stable identifiers across canonical sources and make missing or
  contradictory links visible;
- continue serial, read-only host coverage with source and freshness recorded;
- add only approved service-native or fixed-command telemetry inputs;
- qualify backup coverage separately from local copies, contents, and restore
  success;
- dogfood owner and household status questions after each runtime change;
- retain read-only enforcement and household redaction under partial outages.

Do not infer current state from the protected capability matrix, prior chat,
memory, or an old report. Do not add infrastructure mutation authority as part
of this work.

## Separate owner or external gates

- Production cutover, client/DNS changes, or retirement of an existing runtime
  require their own explicit owner decision.
- Real household onboarding requires the selected identity and credential
  flow.
- Real finance, Home Assistant, off-host encrypted recovery custody, and
  privileged browser workflows remain separately gated.
- Infrastructure changes discovered during read-only inspection are assigned
  to the authorized infrastructure operator; HADES integration work must not
  modify hosts, networks, drivers, or hypervisor state.

## Evidence location

Detailed private acceptance records and the canonical machine matrix belong in
the protected `hades-infra` repository. Public fixtures and contracts must use
synthetic names, addresses, credentials, and measurements.
