#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
printf 'not a Hermes release\n' > "$fixture/artifact"
chmod 600 "$fixture/artifact"
test -n "$(bash "$repo_dir/scripts/install-hermes-artifact.sh" --help)"
grep -q -- '--candidate' < <(bash "$repo_dir/scripts/install-hermes-artifact.sh" --help)
if bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/prefix" \
  --artifact "$fixture/artifact" --sha256 0000000000000000000000000000000000000000000000000000000000000000 \
  >/tmp/hades-hermes-artifact-contract.out 2>&1; then
  echo 'FAIL checksum mismatch was accepted'; exit 1
fi
grep -q 'checksum mismatch' /tmp/hades-hermes-artifact-contract.out
test ! -e "$fixture/prefix"
grep -q 'python_bin=.*HADES_HERMES_PYTHON:-python3.13' "$repo_dir/scripts/install-hermes-artifact.sh"
grep -q '"\$python_bin" -m venv' "$repo_dir/scripts/install-hermes-artifact.sh"
grep -q 'HADES_HERMES_UV_VERSION' "$repo_dir/scripts/install-hermes-artifact.sh"
grep -Fq '"$uv_bin" sync "${extras[@]}"' "$repo_dir/scripts/install-hermes-artifact.sh"
grep -q 'installation=python-venv-uv-locked-editable' "$repo_dir/scripts/install-hermes-artifact.sh"
! grep -qE 'cp .*venv|copy.*venv' "$repo_dir/scripts/install-hermes-artifact.sh"
mkdir -p "$fixture/source"
printf '[project]\nname = "hermes-agent"\n[project.optional-dependencies]\nhindsight = []\n' > "$fixture/source/pyproject.toml"
tar -czf "$fixture/source.tar.gz" -C "$fixture" source
sha=$(sha256sum "$fixture/source.tar.gz" | awk '{print $1}')
cat > "$fixture/python315" <<'PY'
#!/usr/bin/env bash
if [[ "$1" == -c ]]; then printf '3.15\n'; exit 0; fi
exit 1
PY
chmod 755 "$fixture/python315"
if HADES_HERMES_PYTHON="$fixture/python315" bash "$repo_dir/scripts/install-hermes-artifact.sh" \
  --prefix "$fixture/python-prefix" --artifact "$fixture/source.tar.gz" --sha256 "$sha" \
  >"$fixture/python.out" 2>&1; then
  echo 'FAIL unsupported Hermes Python version was accepted'; exit 1
fi
grep -q 'requires Python >=3.11,<3.14 (found 3.15)' "$fixture/python.out"
test ! -e "$fixture/python-prefix"
cat > "$fixture/python313" <<'PY'
#!/usr/bin/env bash
if [[ "$1" == */scripts/write_install_stamp.py ]]; then printf '%s\n' "$@" >"$HERMES_TEST_STAMP_ARGS"; exit 0; fi
if [[ "$1" == '-c' ]]; then printf '3.13\n'; exit 0; fi
if [[ "$1" == '-' ]]; then grep -q 'hindsight' pyproject.toml; exit $?; fi
if [[ "$1" == '-m' && "$2" == 'venv' ]]; then mkdir -p "$3/bin"; cp "$0" "$3/bin/python"; exit 0; fi
exit 1
PY
cat > "$fixture/uv" <<'UV'
#!/usr/bin/env bash
if [[ "$1" == '--version' ]]; then
  printf 'uv 0.12.15 (x86_64-unknown-linux-gnu)\n'
  exit 0
fi
[[ "$*" == 'sync --extra all --extra hindsight --locked' || "$*" == 'sync --extra all --locked' ]]
UV
chmod 755 "$fixture/python313" "$fixture/uv"
HADES_HERMES_PYTHON="$fixture/python313" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/uv-prefix" \
  --artifact "$fixture/source.tar.gz" --sha256 "$sha" >"$fixture/uv.out" 2>&1
grep -q 'PASS Hermes 0.21.2 installed' "$fixture/uv.out"
test -f "$fixture/uv-prefix/provenance"
mkdir -p "$fixture/candidate-source"
mkdir -p "$fixture/candidate-source/scripts"
printf '[project]\nname = "hermes-agent"\n[project.optional-dependencies]\nall = []\n' > "$fixture/candidate-source/pyproject.toml"
printf '# test stub\n' > "$fixture/candidate-source/scripts/write_install_stamp.py"
tar -czf "$fixture/candidate-source.tar.gz" -C "$fixture" candidate-source
candidate_sha=$(sha256sum "$fixture/candidate-source.tar.gz" | awk '{print $1}')
HADES_HERMES_VERSION=0.21.5 HADES_HERMES_SOURCE_VERSION=0.21.5 \
  HADES_HERMES_SOURCE_COMMIT=1111111111111111111111111111111111111111 \
  HERMES_TEST_STAMP_ARGS="$fixture/candidate-stamp.args" \
  HADES_HERMES_PYTHON="$fixture/python313" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/candidate-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" --sha256 "$candidate_sha" >"$fixture/candidate.out" 2>&1
grep -q 'PASS Hermes 0.21.5 installed' "$fixture/candidate.out"
grep -q 'artifact_version=0.21.5' "$fixture/candidate-prefix/provenance"
test -f "$fixture/candidate-prefix/provenance"
grep -q -- '--base-version' "$fixture/candidate-stamp.args"
grep -q '^0.21.5$' "$fixture/candidate-stamp.args"
grep -q '^1111111111111111111111111111111111111111$' "$fixture/candidate-stamp.args"
grep -q '^external$' "$fixture/candidate-stamp.args"
cat > "$fixture/python314" <<'PY'
#!/usr/bin/env bash
if [[ "$1" == */scripts/write_install_stamp.py ]]; then printf '%s\n' "$@" >"$HERMES_TEST_STAMP_ARGS"; exit 0; fi
if [[ "$1" == '-c' ]]; then printf '3.14\n'; exit 0; fi
if [[ "$1" == '-' ]]; then grep -q 'hindsight' pyproject.toml; exit $?; fi
if [[ "$1" == '-m' && "$2" == 'venv' ]]; then mkdir -p "$3/bin"; cp "$0" "$3/bin/python"; exit 0; fi
exit 1
PY
chmod 755 "$fixture/python314"
if HADES_HERMES_PYTHON="$fixture/python315" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/candidate-python315-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" --sha256 "$candidate_sha" >"$fixture/candidate-python315.out" 2>&1; then
  echo 'FAIL Hermes candidate accepted Python 3.15'; exit 1
fi
grep -q 'requires Python >=3.11,<3.15 (found 3.15)' "$fixture/candidate-python315.out"
test ! -e "$fixture/candidate-python315-prefix"
if HADES_HERMES_PYTHON="$fixture/python314" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/production-python314-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" --sha256 "$candidate_sha" >"$fixture/production-python314.out" 2>&1; then
  echo 'FAIL production Hermes accepted Python 3.14'; exit 1
fi
grep -q 'requires Python >=3.11,<3.14 (found 3.14)' "$fixture/production-python314.out"
test ! -e "$fixture/production-python314-prefix"
HERMES_TEST_STAMP_ARGS="$fixture/python314-stamp.args" \
  HADES_HERMES_PYTHON="$fixture/python314" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/python314-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" --sha256 "$candidate_sha" >"$fixture/python314.out" 2>&1
grep -q 'PASS Hermes 0.21.6 installed' "$fixture/python314.out"
grep -q '^818c13be1dc4fd28987e1e881a9408224afd4535$' "$fixture/python314-stamp.args"
grep -q '^0.21.6$' "$fixture/python314-stamp.args"
grep -q '^external$' "$fixture/python314-stamp.args"
grep -q 'artifact_version=0.21.6' "$fixture/python314-prefix/provenance"
grep -q 'source_commit=818c13be1dc4fd28987e1e881a9408224afd4535' "$fixture/python314-prefix/provenance"
echo 'PASS Hermes artifact checksum and fresh-venv contract'
