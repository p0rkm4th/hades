#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/hades-openwebui-artifact.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
mkdir -m 700 "$tmp/bin"
cat >"$tmp/bin/docker" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
format=${5:-}
case "$format" in
  '{{.Id}}') printf '%s\n' "${FAKE_IMAGE_ID:?}" ;;
  *org.opencontainers.image.version*) printf '%s\n' "${FAKE_UPSTREAM_VERSION:?}" ;;
  *org.opencontainers.image.revision*) printf '%s\n' "${FAKE_UPSTREAM_COMMIT:?}" ;;
  *org.hades.open-webui.source-commit*) printf '%s\n' "${FAKE_HADES_COMMIT:?}" ;;
  *org.hades.open-webui.base-image*) printf '%s\n' "${FAKE_BASE_IMAGE:?}" ;;
  *) echo "unexpected fake docker format: $format" >&2; exit 2 ;;
esac
SH
chmod 700 "$tmp/bin/docker"
source "$repo_dir/config/versions.env"
export PATH="$tmp/bin:$PATH"
export FAKE_IMAGE_ID="$HADES_OPEN_WEBUI_CANDIDATE_HADES_IMAGE_ID"
export FAKE_UPSTREAM_VERSION="$HADES_OPEN_WEBUI_CANDIDATE_VERSION"
export FAKE_UPSTREAM_COMMIT="$HADES_OPEN_WEBUI_CANDIDATE_SOURCE_COMMIT"
export FAKE_HADES_COMMIT="$HADES_OPEN_WEBUI_CANDIDATE_HADES_COMMIT"
export FAKE_BASE_IMAGE="$HADES_OPEN_WEBUI_CANDIDATE_IMAGE"
bash "$repo_dir/scripts/verify-open-webui-candidate-artifact.sh" synthetic-image >/dev/null

for field in FAKE_IMAGE_ID FAKE_UPSTREAM_VERSION FAKE_UPSTREAM_COMMIT FAKE_HADES_COMMIT FAKE_BASE_IMAGE; do
  original=${!field}
  printf -v "$field" '%s' "${original}mismatch"
  export "$field"
  if bash "$repo_dir/scripts/verify-open-webui-candidate-artifact.sh" synthetic-image >/dev/null 2>&1; then
    echo "FAIL candidate artifact verifier accepted mismatched $field" >&2
    exit 1
  fi
  printf -v "$field" '%s' "$original"
  export "$field"
done

builder=$(<"$repo_dir/scripts/build-open-webui-artifact.sh")
grep -q -- '--label "org.hades.open-webui.source-commit=$source_commit"' <<<"$builder" || {
  echo 'FAIL Open WebUI builder omits HADES source provenance label' >&2
  exit 1
}
grep -q -- '--label "org.hades.open-webui.base-image=$base_override"' <<<"$builder" || {
  echo 'FAIL Open WebUI builder omits immutable base provenance label' >&2
  exit 1
}
for script in test-open-webui-candidate.sh test-open-webui-populated-migration.sh; do
  grep -q 'verify-open-webui-candidate-artifact.sh' "$repo_dir/scripts/$script" || {
    echo "FAIL $script does not enforce candidate image provenance" >&2
    exit 1
  }
done
grep -q 'HADES_DISABLED_ROLE_EXPECTED_IMAGE_ID="\$HADES_OPEN_WEBUI_CANDIDATE_HADES_IMAGE_ID"' "$repo_dir/scripts/test-open-webui-candidate.sh" || {
  echo 'FAIL candidate acceptance does not bind role revocation to the exact image ID' >&2
  exit 1
}
echo 'PASS Open WebUI candidate version, source, base, and image identity are bound to the manifest'
