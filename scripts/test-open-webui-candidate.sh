#!/usr/bin/env bash
set -Eeuo pipefail

# Candidate-only acceptance. The caller supplies an already-built immutable
# image; this script never changes the production version manifest.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo_dir/config/versions.env"
image=${1:?usage: test-open-webui-candidate.sh IMAGE}
bash "$repo_dir/scripts/verify-open-webui-candidate-artifact.sh" "$image"

HADES_PRIVATE_CHAT_WEBUI_IMAGE="$image" \
HADES_PRIVATE_CHAT_WEBUI_PORT="${HADES_PRIVATE_CHAT_WEBUI_PORT:-18895}" \
HADES_PRIVATE_CHAT_MODEL_PORT="${HADES_PRIVATE_CHAT_MODEL_PORT:-18896}" \
bash scripts/test-open-webui-private-chat-soak.sh
HADES_CHANNELS_WEBUI_IMAGE="$image" \
HADES_CHANNELS_WEBUI_PORT="${HADES_CHANNELS_WEBUI_PORT:-18869}" \
bash scripts/test-open-webui-channels-fixture.sh
HADES_CHANNEL_MODEL_WEBUI_IMAGE="$image" \
HADES_CHANNEL_MODEL_WEBUI_PORT="${HADES_CHANNEL_MODEL_WEBUI_PORT:-18892}" \
HADES_CHANNEL_MODEL_BACKEND_PORT="${HADES_CHANNEL_MODEL_BACKEND_PORT:-18893}" \
bash scripts/test-open-webui-channel-model-fixture.sh
HADES_OPEN_WEBUI_LDAP_TEST_IMAGE="$image" \
bash scripts/test-openwebui-ldap-bootstrap.sh
HADES_DISABLED_ROLE_TEST_IMAGE="$image" \
HADES_DISABLED_ROLE_EXPECTED_IMAGE_ID="$HADES_OPEN_WEBUI_CANDIDATE_HADES_IMAGE_ID" \
bash scripts/test-openwebui-disabled-role-session.sh
EXPECT_VULNERABLE=0 HADES_PLAYWRIGHT_MODULE="${HADES_PLAYWRIGHT_MODULE:-${HOME}/.local/share/hades-playwright/node_modules/playwright}" \
bash scripts/test-openwebui-docx-preview-security.sh "$image"

echo "PASS Open WebUI candidate acceptance: $image"
