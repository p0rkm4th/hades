#!/usr/bin/env bash
set -Eeuo pipefail

package=${1:-}
hades_repo=${2:-}
infra_repo=${3:-}

if [[ -z "$package" || -z "$hades_repo" || -z "$infra_repo" ]]; then
  printf 'usage: %s PACKAGE_DIR HADES_REPO INFRA_REPO\n' "$0" >&2
  exit 2
fi
[[ -d "$package" && ! -L "$package" ]] || { echo 'FAIL package directory' >&2; exit 1; }
[[ -d "$hades_repo/.git" ]] || { echo 'FAIL HADES repository' >&2; exit 1; }
[[ -d "$infra_repo/.git" ]] || { echo 'FAIL infrastructure repository' >&2; exit 1; }

verify_manifest() {
  local dir=$1 manifest=$2
  [[ -f "$dir/$manifest" ]] || { echo "FAIL missing $dir/$manifest" >&2; exit 1; }
  (cd "$dir" && sha256sum -c "$manifest" >/dev/null)
}

verify_manifest "$package/volumes" volume-SHA256SUMS
verify_manifest "$package/repositories" SHA256SUMS

for bundle in "$package"/repositories/hades-*.bundle; do
  [[ "$(basename "$bundle")" == hades-infra-* ]] && continue
  git -C "$hades_repo" bundle verify "$bundle" >/dev/null 2>&1 || {
    echo "FAIL HADES Git bundle verification: $bundle" >&2
    exit 1
  }
done
git -C "$infra_repo" bundle verify "$package/repositories/hades-infra-"*.bundle >/dev/null 2>&1 || {
  echo 'FAIL infrastructure Git bundle verification' >&2
  exit 1
}

for archive in "$package"/volumes/*.tar.gz; do
  tar -tzf "$archive" >/dev/null
done

for database in "$package"/sqlite/*/*.db; do
  [[ -s "$database" ]] || { echo "FAIL empty database: $database" >&2; exit 1; }
  sqlite3 "$database" 'pragma integrity_check;' | grep -qx ok || {
    echo "FAIL SQLite integrity: $database" >&2
    exit 1
  }
done

echo 'PASS migration artifacts: checksums, Git bundles, archives, SQLite'
