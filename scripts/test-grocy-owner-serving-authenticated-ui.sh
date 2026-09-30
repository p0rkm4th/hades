#!/usr/bin/env bash
set -Eeuo pipefail

# Extend the established disposable Alpha/Beta/Gamma UI fixture with the
# owner-only recipe serving preview/confirmation/cancellation journey.
repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export HADES_GROCY_UI_INCLUDE_OWNER_SERVING=1
export HADES_GROCY_UI_OWNER_SERVING_ONLY=1
exec bash "$repo_dir/scripts/test-grocy-authenticated-household-ui.sh"
