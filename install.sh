#!/usr/bin/env bash
set -Eeuo pipefail
repo_url=${HADES_REPO_URL:-https://github.com/p0rkm4th/Hades.git}
ref=${HADES_REPO_REF:-main}
source_dir=${HADES_SOURCE_DIR:-/opt/hades}
[[ $# -gt 0 ]] || { echo 'Usage: install.sh COMMAND [options]' >&2; exit 2; }
command=$1; shift
case "$command" in
  install|preflight|doctor|status|validate|repair|reconfigure|backup|restore|upgrade|uninstall) ;;
  help|-h|--help) echo 'Usage: install.sh COMMAND [options]'; exit 0 ;;
  *) echo "FAIL unsupported lifecycle command: $command" >&2; exit 2 ;;
esac
if [[ -e "$source_dir" && ! -d "$source_dir/.git" ]]; then
  echo "FAIL source path exists but is not a Git checkout: $source_dir" >&2; exit 1
fi
if [[ ! -d "$source_dir/.git" ]]; then
  git clone --filter=blob:none --branch "$ref" "$repo_url" "$source_dir"
else
  git -C "$source_dir" fetch --quiet --tags origin "$ref" || { echo 'FAIL could not refresh existing checkout' >&2; exit 1; }
  git -C "$source_dir" checkout --quiet --detach "$ref"
fi
exec "$source_dir/scripts/hades" "$command" "$@"
