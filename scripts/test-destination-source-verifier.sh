#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
verifier=$repo_dir/scripts/verify-destination-source.sh
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/bin"
cat > "$fixture/bin/ssh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
command=${*: -1}
case "$command" in
  *'rev-parse --verify HEAD') printf '%s\n' "${FAKE_HEAD:?}" ;;
  *'status --porcelain=v1 --untracked-files=all') printf '%s\n' "${FAKE_STATUS:-}" ;;
  *) exit 1 ;;
esac
EOF
chmod 755 "$fixture/bin/ssh"
export PATH="$fixture/bin:$PATH"
revision=0123456789abcdef0123456789abcdef01234567

FAKE_HEAD=$revision FAKE_STATUS= bash "$verifier" fake-ssh /destination/repo "$revision" >/dev/null
if FAKE_HEAD=$revision FAKE_STATUS=' M scripts/example.sh' bash "$verifier" fake-ssh /destination/repo "$revision" >/dev/null 2>&1; then
  echo 'FAIL dirty destination was accepted' >&2
  exit 1
fi
if FAKE_HEAD=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa FAKE_STATUS= bash "$verifier" fake-ssh /destination/repo "$revision" >/dev/null 2>&1; then
  echo 'FAIL wrong destination revision was accepted' >&2
  exit 1
fi
echo 'PASS destination source verifier clean, dirty, and revision-mismatch paths'
