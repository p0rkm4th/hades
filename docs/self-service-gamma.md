# Bounded self-service workloads

HADES self-service is an optional, owner-controlled capability. Public policy
supports only explicitly approved workload templates and fixed resource
profiles. The operator keeps template identifiers, placement rules, quotas,
and credentials in private configuration.

The request path is bounded:

1. Resolve an approved workload type and policy-owned placement.
2. Show the exact plan and require owner confirmation before provisioning.
3. Use the least-privilege infrastructure broker and reconcile the canonical
   result after asynchronous operations.
4. Cache terminal outcomes so an unknown result is not blindly retried.
5. Grant sharing explicitly; check the grant again when an operation runs.
6. Report only what the source verified. A running guest does not establish
   application health, external reachability, or firewall readiness.

Raw VM IDs, images, scripts, host mounts, and network configuration are not
accepted from users. Lifecycle operations are constrained to owner-managed
guests and require the confirmation policy defined for that operation.

A deployment may have no approved template for a requested workload. In that
case HADES must explain the missing configuration and perform no partial
provisioning. Real template maps, live guest identifiers, server addresses,
and deployment acceptance evidence stay in private operator records.
