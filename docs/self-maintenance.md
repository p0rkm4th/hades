# Owner-authorized self-maintenance boundary

HADES may eventually inspect, improve, test, and deploy its own software and
node configuration. This is an owner capability, not an implicit permission
for the ordinary conversational process to write arbitrary host files.

The intended execution path is:

```text
owner request
    -> typed maintenance plan
    -> exact files/commands/resources shown
    -> backup or reversible checkpoint where practical
    -> explicit confirmation for writes/restarts
    -> isolated maintenance worker
    -> tests and deployment validation
    -> read-back and rollback-ready result
```

The normal Hermes runtime may write only its declared mutable state. A future
maintenance worker may receive narrowly scoped access to:

- a dedicated HADES working tree or worktree;
- the HADES and hades-infra repositories;
- generated deployment configuration;
- selected node configuration paths;
- approved service restart operations.

It must not receive a general shell-to-root path, the owner's SSH keys,
unrelated private files, unrestricted Proxmox access, Docker socket access, or
credentials outside the operation being performed. Host `sudo` should be
implemented as command/path-specific policy with fixed argument validation and
logging, not as `sudo ALL`.

Self-modification is accepted only when the resulting change is represented in
tracked deployment material, tested, attributable to an owner-approved plan,
and recoverable. A model statement such as “I fixed it” is never evidence of a
successful change; the worker must provide the diff, command outcome, service
health, and post-change read-back.
