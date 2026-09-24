# Full-application artifact closure

This is the focused scoreboard for the reconstruction campaign. It separates
software provenance, generated deployment, component-real evidence, and the
end-to-end clean-guest claim.

| Component | Artifact provenance | Generated deployment | Real component fixture | Fresh full-app guest | Reboot | Portable artifact required |
|---|---|---|---|---|---|---|
| Open WebUI | PASS: immutable upstream base plus tracked `webui/Dockerfile` and theme layer | PASS: `deploy/templates/open-webui.compose.yaml` | PASS: rebuilt image started and `/health` returned `{"status":true}` with a new WebUI database | PASS: fresh Rocky generated-installer run and restart/isolation soak | PASS: generated-runtime reboot recovery and post-reboot isolation | no, unless the pinned base disappears; then use an image archive contract |
| Hindsight | PASS: immutable image digest in `config/versions.env` | PASS: `deploy/templates/hindsight.compose.yaml` | PASS: pinned image health returned `database=connected` with synthetic model credentials | PASS: fresh Rocky generated-installer deployment | PASS: generated-runtime reboot recovery | no |
| SearXNG | PASS: immutable image digest in `config/versions.env` | PASS: `deploy/templates/searxng.compose.yaml` | PASS: pinned image returned JSON search results using tracked settings and a synthetic secret | PASS: fresh Rocky generated-installer deployment | PASS: generated-runtime reboot recovery | no |
| Hermes 0.14.0 | PASS: upstream `v2026.5.16` source archive and SHA-256; installed into a new venv | PASS: `deploy/templates/hermes.service.in` | PASS: verified archive installed; real CLI surface and version `0.14.0` verified | PASS: fresh Rocky generated-installer gateway and authenticated model route | PASS: Hermes active after reboot; post-reboot authenticated model route and stale-key rejection passed | no, while the upstream archive remains fetchable |
| LLDAP | PASS: immutable image digest and tracked Compose | compatibility path PASS | accepted clean-guest evidence PASS | PASS: fresh Rocky generated-installer deployment | PASS: generated-runtime reboot recovery | no |
| Grocy | PASS: immutable image digest and tracked Compose | compatibility path PASS | accepted clean-guest evidence PASS | PASS: fresh Rocky generated-installer deployment | PASS: generated-runtime reboot recovery | no |
| Agent Zero | PASS: immutable image digest and tracked Compose | compatibility path PASS | accepted clean-guest evidence PASS | PASS: fresh Rocky generated-installer deployment | PASS: generated-runtime reboot recovery | no |

## Current boundary

The generated records render and validate without secret contents, and the
the pinned application images plus a clean Hermes venv have each been exercised
in isolation. `scripts/test-full-application-image-startup.sh` now also starts
the six real pinned application images and a disposable OpenAI-compatible
model together on an isolated Docker network. It verifies internal LLDAP,
Grocy, Hindsight, and Open WebUI health, then creates an authenticated
synthetic Alpha and Beta users, confirms Alpha's assistant response by
persisted read-back, and rejects Beta access to Alpha's private chat, with
bounded startup polling and automatic cleanup. The client then restarts
Open WebUI, signs Alpha in again, confirms the same chat remains readable, and
signs Beta in to verify the private-chat denial still holds.
This is synthetic application-path evidence; the fresh generated-installer
evidence below adds the installer and Hermes/WebUI boundary.

The same six-image composition was rerun from the current pushed checkpoint on
2026-09-15 and passed again, including Alpha/Beta authentication, model-route
response persistence, private-chat denial, and Open WebUI restart persistence.
This strengthens disposable application-composition evidence but does not
replace the fresh generated-installer evidence below.

On 2026-09-16, a fresh Rocky Linux 10.2 guest ran the complete v2 generated
installer path from generated private inputs. Hermes was reachable from the
containerized WebUI through a private Docker-bridge bind, API-key mismatch was
rejected, and the synthetic Alpha/Beta response-persistence, private-chat
denial, restart-persistence, and post-restart isolation checks all passed.
The disposable signup/test state was removed and signup was restored to false.
See [`acceptance/fresh-rocky-generated-installer-2026-09-16.txt`](../acceptance/fresh-rocky-generated-installer-2026-09-16.txt).

On 2026-09-16, the same actual-image composition was completed on an
independent fresh Rocky Linux 10.2 guest after the tracked Rocky Docker
prerequisite path was repaired. All seven disposable containers reached health,
Alpha/Beta model and privacy checks passed across an Open WebUI restart, and
cleanup retained no reconstruction containers. This is complementary to the
generated-installer evidence above; reboot persistence and the broader
multi-domain household contract are covered by the generated-installer
acceptance and synthetic household-soak evidence below.

The fresh-guest reboot and full household capability soak are now evidenced by
the generated-installer and synthetic household-soak records. The remaining
reconstruction gate is owner-visible authenticated composition on that
reconstructed deployment; legacy whole-file deployment records must not be
used for that acceptance.

An earlier attempt from the current checkpoint booted Fedora Cloud 44, installed
Docker/Compose, and built the pinned Open WebUI artifact, but stopped during
remaining image acquisition when the temporary guest overlay consumed the
host's `/tmp` tmpfs. The temporary guest and downloaded artifacts were
reclaimed; that historical attempt does not override the later successful
fresh Rocky acceptance.

The retry moved the overlay to the root filesystem and exposed a Fedora
SELinux/UID-1000 secret-mount defect in the harness. The `:ro,Z` mounts and
service-UID ownership are now fixed; those stalled Fedora attempts remain
historical evidence rather than current blockers.
