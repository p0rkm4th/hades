# Full-application artifact closure

This is the focused scoreboard for the reconstruction campaign. It separates
software provenance, generated deployment, component-real evidence, and the
end-to-end clean-guest claim.

| Component | Artifact provenance | Generated deployment | Real component fixture | Fresh full-app guest | Reboot | Portable artifact required |
|---|---|---|---|---|---|---|
| Open WebUI | PASS: immutable upstream base plus tracked `webui/Dockerfile` and theme layer | PASS: `deploy/templates/open-webui.compose.yaml` | PASS: rebuilt image started and `/health` returned `{"status":true}` with a new WebUI database | NOT YET PROVEN | NOT YET PROVEN | no, unless the pinned base disappears; then use an image archive contract |
| Hindsight | PASS: immutable image digest in `config/versions.env` | PASS: `deploy/templates/hindsight.compose.yaml` | PASS: pinned image health returned `database=connected` with synthetic model credentials | NOT YET PROVEN | NOT YET PROVEN | no |
| SearXNG | PASS: immutable image digest in `config/versions.env` | PASS: `deploy/templates/searxng.compose.yaml` | PASS: pinned image returned JSON search results using tracked settings and a synthetic secret | NOT YET PROVEN | NOT YET PROVEN | no |
| Hermes 0.14.0 | PASS: upstream `v2026.5.16` source archive and SHA-256; installed into a new venv | PASS: `deploy/templates/hermes.service.in` | PASS: verified archive installed; real CLI surface and version `0.14.0` verified | NOT YET PROVEN | NOT YET PROVEN | no, while the upstream archive remains fetchable |
| LLDAP | PASS: immutable image digest and tracked Compose | compatibility path PASS | accepted clean-guest evidence PASS | NOT YET PROVEN through v2 generated records | tracked subset PASS | no |
| Grocy | PASS: immutable image digest and tracked Compose | compatibility path PASS | accepted clean-guest evidence PASS | NOT YET PROVEN through v2 generated records | tracked subset PASS | no |
| Agent Zero | PASS: immutable image digest and tracked Compose | compatibility path PASS | accepted clean-guest evidence PASS | NOT YET PROVEN through v2 generated records | tracked subset PASS | no |

## Current boundary

The generated records render and validate without secret contents, and the
three real application images plus a clean Hermes venv have each been exercised
in isolation. `scripts/test-full-application-image-startup.sh` now also starts
the six real pinned application images and a disposable OpenAI-compatible
model together on an isolated Docker network. It verifies internal LLDAP,
Grocy, Hindsight, and Open WebUI health, then creates an authenticated
synthetic Alpha chat through Open WebUI and confirms the assistant response by
persisted read-back, with bounded startup polling and automatic cleanup. This
is synthetic application-path evidence; the campaign does **not** yet claim:

- a fresh guest installed with v2 generated records;
- a real Hermes gateway connected to the real Open WebUI, Hindsight, Grocy,
  SearXNG, and Agent Zero instances;
- synthetic Alpha/Beta/Gamma authentication through a freshly reconstructed
  guest application path; or
- reboot persistence for the generated full application.

The next independent action is a fresh supported Fedora guest using only the
repository, v2 operator values, the verified Hermes archive, the built
Open WebUI image, and synthetic state/secrets. Legacy whole-file deployment
records must not be used for that acceptance run.
