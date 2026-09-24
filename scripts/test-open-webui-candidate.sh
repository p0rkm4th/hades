#!/usr/bin/env bash
set -Eeuo pipefail

# Candidate-only acceptance. The caller supplies an already-built immutable
# image; this script never changes the production version manifest.
image=${1:?usage: test-open-webui-candidate.sh IMAGE}
docker image inspect "$image" >/dev/null

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

echo "PASS Open WebUI candidate acceptance: $image"
