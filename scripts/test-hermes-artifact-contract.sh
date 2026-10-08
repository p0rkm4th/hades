#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
printf 'not a Hermes release\n' > "$fixture/artifact"
chmod 600 "$fixture/artifact"
production_sha=$(awk -F= '$1 == "HADES_HERMES_SOURCE_SHA256" {print $2}' "$repo_dir/config/versions.env")
test -n "$(bash "$repo_dir/scripts/install-hermes-artifact.sh" --help)"
grep -q -- '--candidate' < <(bash "$repo_dir/scripts/install-hermes-artifact.sh" --help)
if bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/prefix" \
  --artifact "$fixture/artifact" --sha256 "$production_sha" \
  >/tmp/hades-hermes-artifact-contract.out 2>&1; then
  echo 'FAIL checksum mismatch was accepted'; exit 1
fi
grep -q 'checksum mismatch' /tmp/hades-hermes-artifact-contract.out
test ! -e "$fixture/prefix"
if bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/prefix-bad-sha" \
  --artifact "$fixture/artifact" --sha256 0000000000000000000000000000000000000000000000000000000000000000 \
  >"$fixture/production-bad-sha.out" 2>&1; then
  echo 'FAIL production Hermes accepted a source checksum override'; exit 1
fi
grep -q 'source checksum must match the pinned production source checksum' "$fixture/production-bad-sha.out"
test ! -e "$fixture/prefix-bad-sha"
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
production_repo="$fixture/production-repo"
mkdir -p "$production_repo/scripts" "$production_repo/config"
cp "$repo_dir/scripts/install-hermes-artifact.sh" "$production_repo/scripts/"
cp "$repo_dir/config/versions.env" "$production_repo/config/"
python3 - "$production_repo/config/versions.env" "$sha" <<'PY'
import pathlib, sys
manifest = pathlib.Path(sys.argv[1])
values = {
    "HADES_HERMES_SOURCE_SHA256": sys.argv[2],
    "HADES_HERMES_SOURCE_COMMIT": "2222222222222222222222222222222222222222",
}
lines = manifest.read_text().splitlines()
manifest.write_text("\n".join(
    f"{line.split('=', 1)[0]}={values[line.split('=', 1)[0]]}"
    if line.split("=", 1)[0] in values else line
    for line in lines
) + "\n")
PY
HADES_HERMES_PYTHON="$fixture/python313" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$production_repo/scripts/install-hermes-artifact.sh" --prefix "$fixture/uv-prefix" \
  --artifact "$fixture/source.tar.gz" >"$fixture/uv.out" 2>&1
grep -q 'PASS Hermes 0.21.2 installed' "$fixture/uv.out"
test -f "$fixture/uv-prefix/provenance"
mkdir -p "$fixture/candidate-source"
mkdir -p "$fixture/candidate-source/scripts"
printf '[project]\nname = "hermes-agent"\n[project.optional-dependencies]\nall = []\n' > "$fixture/candidate-source/pyproject.toml"
printf '# test stub\n' > "$fixture/candidate-source/scripts/write_install_stamp.py"
tar -czf "$fixture/candidate-source.tar.gz" -C "$fixture" candidate-source
candidate_sha=$(sha256sum "$fixture/candidate-source.tar.gz" | awk '{print $1}')
candidate_repo="$fixture/candidate-repo"
mkdir -p "$candidate_repo/scripts" "$candidate_repo/config"
cp "$repo_dir/scripts/install-hermes-artifact.sh" "$candidate_repo/scripts/"
cp "$repo_dir/config/versions.env" "$candidate_repo/config/"
python3 - "$candidate_repo/config/versions.env" "$candidate_sha" <<'PY'
import pathlib, sys
manifest = pathlib.Path(sys.argv[1])
values = {
    "HADES_HERMES_SOURCE_SHA256": sys.argv[2],
    "HADES_HERMES_SOURCE_COMMIT": "2222222222222222222222222222222222222222",
    "HADES_HERMES_CANDIDATE_SOURCE_URL": "https://example.invalid/hermes-v0.21.6.tar.gz",
    "HADES_HERMES_CANDIDATE_SOURCE_SHA256": sys.argv[2],
    "HADES_HERMES_CANDIDATE_SOURCE_COMMIT": "1111111111111111111111111111111111111111",
}
lines = manifest.read_text().splitlines()
manifest.write_text("\n".join(
    f"{line.split('=', 1)[0]}={values[line.split('=', 1)[0]]}"
    if line.split("=", 1)[0] in values else line
    for line in lines
) + "\n")
PY
  HERMES_TEST_STAMP_ARGS="$fixture/candidate-stamp.args" \
  HADES_HERMES_PYTHON="$fixture/python313" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$candidate_repo/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/candidate-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" >"$fixture/candidate.out" 2>&1
grep -q 'PASS Hermes 0.21.6 installed' "$fixture/candidate.out"
grep -q 'artifact_version=0.21.6' "$fixture/candidate-prefix/provenance"
test -f "$fixture/candidate-prefix/provenance"
grep -q -- '--base-version' "$fixture/candidate-stamp.args"
grep -q '^0.21.6$' "$fixture/candidate-stamp.args"
grep -q '^1111111111111111111111111111111111111111$' "$fixture/candidate-stamp.args"
grep -q '^external$' "$fixture/candidate-stamp.args"
grep -q 'source_commit=1111111111111111111111111111111111111111' "$fixture/candidate-prefix/provenance"
if bash "$candidate_repo/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/candidate-bad-url" \
  --url https://attacker.invalid/hermes.tar.gz --artifact "$fixture/candidate-source.tar.gz" \
  >"$fixture/candidate-bad-url.out" 2>&1; then
  echo 'FAIL Hermes candidate accepted a source URL override'; exit 1
fi
grep -q 'candidate URL must match the pinned candidate source URL' "$fixture/candidate-bad-url.out"
test ! -e "$fixture/candidate-bad-url"
if bash "$candidate_repo/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/candidate-bad-sha" \
  --sha256 0000000000000000000000000000000000000000000000000000000000000000 \
  --artifact "$fixture/candidate-source.tar.gz" >"$fixture/candidate-bad-sha.out" 2>&1; then
  echo 'FAIL Hermes candidate accepted a source checksum override'; exit 1
fi
grep -q 'candidate checksum must match the pinned candidate source checksum' "$fixture/candidate-bad-sha.out"
test ! -e "$fixture/candidate-bad-sha"
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
  bash "$candidate_repo/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/candidate-python315-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" >"$fixture/candidate-python315.out" 2>&1; then
  echo 'FAIL Hermes candidate accepted Python 3.15'; exit 1
fi
grep -q 'requires Python >=3.11,<3.15 (found 3.15)' "$fixture/candidate-python315.out"
test ! -e "$fixture/candidate-python315-prefix"
if HADES_HERMES_PYTHON="$fixture/python314" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$candidate_repo/scripts/install-hermes-artifact.sh" --prefix "$fixture/production-python314-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" --sha256 "$candidate_sha" >"$fixture/production-python314.out" 2>&1; then
  echo 'FAIL production Hermes accepted Python 3.14'; exit 1
fi
grep -q 'requires Python >=3.11,<3.14 (found 3.14)' "$fixture/production-python314.out"
test ! -e "$fixture/production-python314-prefix"
HERMES_TEST_STAMP_ARGS="$fixture/python314-stamp.args" \
  HADES_HERMES_PYTHON="$fixture/python314" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$candidate_repo/scripts/install-hermes-artifact.sh" --candidate --prefix "$fixture/python314-prefix" \
  --artifact "$fixture/candidate-source.tar.gz" >"$fixture/python314.out" 2>&1
grep -q 'PASS Hermes 0.21.6 installed' "$fixture/python314.out"
grep -q '^1111111111111111111111111111111111111111$' "$fixture/python314-stamp.args"
grep -q '^0.21.6$' "$fixture/python314-stamp.args"
grep -q '^external$' "$fixture/python314-stamp.args"
grep -q 'artifact_version=0.21.6' "$fixture/python314-prefix/provenance"
grep -q 'source_commit=1111111111111111111111111111111111111111' "$fixture/python314-prefix/provenance"
echo 'PASS Hermes artifact checksum and fresh-venv contract'
