# Epsilon workflow templates

These exported workflows are inactive templates. Their HADES Core health node
uses `http://hades-core.invalid/health` as an intentionally non-routable
placeholder. Configure the canonical endpoint explicitly in the protected
operator input `HADES_EPSILON_HEALTH_URL`; the typed Server Health Watch
builder substitutes that value when it produces an approved workflow.

Do not activate or import a raw template without resolving its private source
endpoints and checking the rendered workflow. Other household and owner gates
remain enforced by the HADES source and runner contracts.
