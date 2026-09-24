# HADES architecture

HADES composes Open WebUI (surface), Hermes Agent (orchestration and policy),
Hindsight (durable memory), canonical household applications, and optional
bounded Agent Zero/n8n paths. Logical roles are CORE, INFERENCE_FAST,
INFERENCE_DEEP, STORAGE, OPERATOR, VOICE, and CANONICAL_APPS.

Hermes Agent is software. Hermes Compute is a possible inference/voice host;
they are never interchangeable names. See
[`docs/component-manifest.md`](docs/component-manifest.md).
