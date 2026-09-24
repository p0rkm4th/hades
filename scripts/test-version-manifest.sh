#!/usr/bin/env bash
set -Eeuo pipefail
manifest=config/versions.env
[[ -f "$manifest" ]] || { echo 'FAIL version manifest missing'; exit 1; }
required=(HADES_RELEASE_VERSION HADES_MANIFEST_VERSION HADES_HERMES_VERSION HADES_OPEN_WEBUI_VERSION HADES_OPEN_WEBUI_BASE_IMAGE HADES_OPEN_WEBUI_BUILD_SOURCE HADES_HERMES_SOURCE_URL HADES_HERMES_SOURCE_VERSION HADES_HERMES_SOURCE_SHA256 HADES_HERMES_CANDIDATE_VERSION HADES_OPEN_WEBUI_CANDIDATE_VERSION HADES_OPEN_WEBUI_CANDIDATE_IMAGE HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE_DIGEST HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD HADES_N8N_IMAGE_RECORD HADES_ACTUAL_VERSION HADES_ACTUAL_ADAPTER_REVISION HADES_GROCY_ADAPTER_REVISION HADES_AGENT_ZERO_ADAPTER_REVISION)
for name in "${required[@]}"; do
  value=$(awk -F= -v key="$name" '$1 == key {print substr($0, index($0,"=")+1)}' "$manifest")
  [[ -n "$value" ]] || { echo "FAIL missing version pin: $name"; exit 1; }
done
[[ "$(awk -F= '$1 == "HADES_OPEN_WEBUI_BASE_IMAGE" {print $2}' "$manifest")" == ghcr.io/open-webui/open-webui@sha256:* ]] || { echo 'FAIL Open WebUI base artifact is not immutable'; exit 1; }
[[ "$(awk -F= '$1 == "HADES_OPEN_WEBUI_CANDIDATE_IMAGE" {print $2}' "$manifest")" =~ ^ghcr.io/open-webui/open-webui@sha256:[0-9a-f]{64}$ ]] || { echo 'FAIL Open WebUI candidate artifact is not immutable'; exit 1; }
[[ "$(awk -F= '$1 == "HADES_HERMES_SOURCE_SHA256" {print $2}' "$manifest")" =~ ^[0-9a-f]{64}$ ]] || { echo 'FAIL Hermes source checksum is invalid'; exit 1; }
grep -Eq '^ARG OPEN_WEBUI_BASE_IMAGE=ghcr\.io/open-webui/open-webui@sha256:[0-9a-f]{64}$' webui/Dockerfile || { echo 'FAIL Open WebUI Dockerfile does not use an immutable base'; exit 1; }
for name in HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD HADES_N8N_IMAGE_RECORD; do
  value=$(awk -F= -v key="$name" '$1 == key {print substr($0, index($0,"=")+1)}' "$manifest")
  [[ "$value" =~ ^[^[:space:]=]+@sha256:[0-9a-f]{64}$ ]] || {
    echo "FAIL image pin is not an immutable repository-plus-digest reference: $name"
    exit 1
  }
done
[[ "$(awk -F= '$1 == "HADES_MANIFEST_VERSION" {print $2}' "$manifest")" == 1 ]] || { echo 'FAIL unsupported manifest version'; exit 1; }
if grep -Eq '(^|[=:])latest([@"[:space:]]|$)' "$manifest"; then echo 'FAIL latest is not an acceptable version pin'; exit 1; fi
for f in scripts/install-hades.sh scripts/hades-doctor.sh scripts/validate-install.sh; do
  grep -q 'config/versions.env' "$f" || { echo "FAIL $f does not reference the authoritative manifest"; exit 1; }
done
grep -q 'export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD' scripts/install-hades.sh || { echo 'FAIL installer does not export manifest image pins'; exit 1; }
for f in scripts/hades-doctor.sh scripts/validate-install.sh; do
  grep -q 'export HADES_LLDAP_IMAGE HADES_HINDSIGHT_IMAGE HADES_GROCY_IMAGE HADES_AGENT_ZERO_IMAGE HADES_SEARXNG_IMAGE_RECORD' "$f" || {
    echo "FAIL $f does not export all manifest image pins"; exit 1;
  }
done
for mapping in 'HADES_LLDAP_IMAGE:deploy/lldap.compose.yaml' 'HADES_GROCY_IMAGE:deploy/grocy.compose.yaml' 'HADES_AGENT_ZERO_IMAGE:deploy/agent-zero.compose.yaml'; do
  key=${mapping%%:*}; file=${mapping#*:}
  grep -q "\${$key:?set $key from config/versions.env}" "$file" || { echo "FAIL $file does not consume $key"; exit 1; }
done
if grep -REn '(^|=)sk-[A-Za-z0-9]|REPLACE_WITH_REAL|password=[^$]' config docs >/dev/null; then echo 'FAIL credential-like value found in public contract'; exit 1; fi
echo 'PASS authoritative version and public-secret contract'
