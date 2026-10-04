#!/bin/sh
set -eu

# Install root-owned and configure as the dedicated account's SSH ForceCommand.
# The authorized_keys entry should repeat this command with the restrict option.
if [ "${SSH_ORIGINAL_COMMAND-}" != "hades-gpu-telemetry-v1" ]; then
    exit 64
fi

exec /usr/bin/timeout 5s /usr/bin/nvidia-smi \
    --query-gpu=index,uuid,name,memory.total,memory.free,utilization.gpu,utilization.memory \
    --format=csv,noheader,nounits
