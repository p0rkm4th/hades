# Deterministic automation boundary

Status: **PREPARATION COMPLETE / PRODUCT-AUTHORIZATION GATE**.

HADES does not currently run n8n or any other deterministic automation in
production. This document defines the smallest safe contract for the first
approved workflow; it is not an automation engine or a permission system.

## Required execution shape

```text
authenticated subject
        ↓
capability check
        ↓
deterministic workflow with a stable idempotency key
        ↓
canonical external system
        ↓
structured outcome returned to HADES
```

The model may propose a workflow and fill declared inputs, but it must not
invent a trigger, select an undisclosed destination, or convert a preview into
an action. Any workflow that changes external state requires an explicit owner
or separately authorized capability and a confirmation boundary appropriate to
the impact.

## First-workflow requirements

Before enabling a workflow, record privately:

- the exact trigger and allowed actor/group;
- input schema, validation rules, and maximum scope;
- canonical system being changed;
- read-only, preview, confirmation, and apply phases;
- idempotency key and duplicate behavior;
- timeout, retry, and partial-failure behavior;
- audit/result record without secrets or unnecessary personal data;
- rollback or compensating action where the canonical system supports one;
- restart/replay behavior and an owner-UI acceptance workflow.

The initial implementation should use an existing mature workflow runner or a
narrow adapter. It must not introduce a generalized HADES scheduler,
orchestrator, tool registry, or runtime layer.

## Safety contract

- Unauthenticated, unknown, or revoked subjects fail closed.
- Capability-resolution failure fails closed; it never grants the union of
  available tools.
- A repeated delivery with the same idempotency key must not duplicate a
  mutation.
- A timeout or lost response is reported as **outcome unknown** until the
  canonical system is checked; it is never reported as success.
- A workflow must not retry a non-idempotent mutation without a canonical
  state check.
- Retrieved web text, model text, and tool output cannot change identity,
  authorization, destination, or approval state.
- Household users receive no finance, homelab-mutation, administration,
  security-sensitive smart-home, or privileged Agent Zero workflow by default.

## Owner authorization gate

Manny/Orc must approve one concrete workflow, its actor/capability mapping,
and its external system before implementation. The approval should name:

```text
workflow:
allowed actors/groups:
canonical system:
read/preview/apply scope:
confirmation rule:
rollback/compensation:
retention:
```

Until that approval exists, HADES remains read-only for future automation and
does not provision or contact a production workflow runner.
