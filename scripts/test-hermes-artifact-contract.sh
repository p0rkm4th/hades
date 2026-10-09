#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
fixture=$(mktemp -d)
trap 'find "$fixture" -depth -mindepth 1 -delete; rmdir "$fixture" 2>/dev/null || true' EXIT
printf 'not a Hermes release\n' > "$fixture/artifact"
chmod 600 "$fixture/artifact"
test -n "$(bash "$repo_dir/scripts/install-hermes-artifact.sh" --help)"
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
grep -q 'hermes_sync_args=' "$repo_dir/scripts/install-hermes-artifact.sh"
grep -q 'installation=python-venv-uv-locked-editable' "$repo_dir/scripts/install-hermes-artifact.sh"
! grep -qE 'cp .*venv|copy.*venv' "$repo_dir/scripts/install-hermes-artifact.sh"
mkdir -p "$fixture/source"
printf '[project]\nname = "hermes-agent"\n' > "$fixture/source/pyproject.toml"
mkdir -p "$fixture/source/scripts"
printf '# upstream stamp writer fixture\n' > "$fixture/source/scripts/write_install_stamp.py"
tar -czf "$fixture/source.tar.gz" -C "$fixture" source
sha=$(sha256sum "$fixture/source.tar.gz" | awk '{print $1}')
cat > "$fixture/python314" <<'PY'
#!/usr/bin/env bash
if [[ "$1" == -c ]]; then printf '3.14\n'; exit 0; fi
if [[ "$1" == '-m' && "$2" == 'venv' ]]; then mkdir -p "$3/bin"; exit 0; fi
if [[ "$1" == */scripts/write_install_stamp.py ]]; then
  [[ "$2" == '--output' && "$4" == '--commit' && "$6" == '--base-version' ]]
  printf '{"baseVersion":"%s","commit":"%s"}\n' "$7" "$5" > "$3"
  exit 0
fi
exit 1
PY
chmod 755 "$fixture/python314"
if HADES_HERMES_PYTHON="$fixture/python314" bash "$repo_dir/scripts/install-hermes-artifact.sh" \
  --prefix "$fixture/python-prefix" --artifact "$fixture/source.tar.gz" --sha256 "$sha" \
  >"$fixture/python.out" 2>&1; then
  echo 'FAIL unsupported Hermes Python version was accepted'; exit 1
fi
grep -q 'requires Python >=3.11,<3.14 (found 3.14)' "$fixture/python.out"
test ! -e "$fixture/python-prefix"
cat > "$fixture/python313" <<'PY'
#!/usr/bin/env bash
if [[ "$1" == '-c' ]]; then printf '3.13\n'; exit 0; fi
if [[ "$1" == '-m' && "$2" == 'venv' ]]; then mkdir -p "$3/bin"; exit 0; fi
exit 1
PY
cat > "$fixture/uv" <<'UV'
#!/usr/bin/env bash
if [[ "$1" == '--version' ]]; then
  printf 'uv 0.12.15 (x86_64-unknown-linux-gnu)\n'
  exit 0
fi
printf '%s\n' "$*" >> "$HADES_INSTALL_UV_LOG"
[[ "$*" == 'sync --extra all --extra hindsight --locked' || \
   "$*" == 'sync --extra all --locked' ]]
UV
chmod 755 "$fixture/python313" "$fixture/uv"
export HADES_INSTALL_UV_LOG="$fixture/uv-calls.log"
HADES_HERMES_PYTHON="$fixture/python314" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/python314-prefix" \
  --artifact "$fixture/source.tar.gz" --sha256 "$sha" --version 0.21.6 \
  >"$fixture/python314-candidate.out" 2>&1
grep -q 'PASS Hermes 0.21.6 installed' "$fixture/python314-candidate.out"
grep -q '^artifact_version=0.21.6$' "$fixture/python314-prefix/provenance"
grep -q '"baseVersion":"0.21.6","commit":"818c13be1dc4fd28987e1e881a9408224afd4535"' \
  "$fixture/python314-prefix/source/install-stamp.json"
grep -q '^sync --extra all --locked$' "$fixture/uv-calls.log"
HADES_HERMES_PYTHON="$fixture/python313" HADES_UV_EXECUTABLE="$fixture/uv" \
  bash "$repo_dir/scripts/install-hermes-artifact.sh" --prefix "$fixture/uv-prefix" \
  --artifact "$fixture/source.tar.gz" --sha256 "$sha" >"$fixture/uv.out" 2>&1
grep -q 'PASS Hermes 0.21.2 installed' "$fixture/uv.out"
test -f "$fixture/uv-prefix/provenance"
grep -q '^sync --extra all --extra hindsight --locked$' "$fixture/uv-calls.log"
echo 'PASS Hermes artifact checksum and fresh-venv contract'
