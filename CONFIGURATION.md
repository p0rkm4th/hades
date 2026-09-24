# HADES configuration

Start from [`config/hades.example.yaml`](config/hades.example.yaml) and
[`config/hades.schema.json`](config/hades.schema.json). Credentials, identity
files, provider keys, private endpoints, and persistent paths belong in the
protected operator-input file and secret storage, never Git or command args.

`standalone` is the default profile. `distributed` and `proxmox` require an
explicit inventory; they never infer a household topology.
