# Models and providers

Supported paths are CPU-local, local GPU, an existing private OpenAI-compatible
server, an owner-approved cloud provider, and explicit local-primary/cloud-
fallback. The default is local-only. Cloud fallback never activates silently
and cannot expand tool authority.

Hermes owns provider integrations. Provider provenance identifies model,
provider, fallback, and reason; finance, files, secrets, and private memory
remain local unless policy explicitly permits otherwise.
