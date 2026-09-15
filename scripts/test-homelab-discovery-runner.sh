#!/usr/bin/env bash
set -euo pipefail

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
fake="$tmp/nmap"
cat >"$fake" <<'EOF'
#!/usr/bin/env python3
import sys

assert sys.argv[1:] == [
    "-n", "-Pn", "-sT", "--open", "--max-retries", "1", "--host-timeout", "12s",
    "-T2", "-p", "80,443", "-oX", "-", "192.0.2.0/30",
], sys.argv[1:]
print('<nmaprun><host><status state="up"/><address addr="192.0.2.2" addrtype="ipv4"/>'
      '<hostnames><hostname name="synthetic-router"/></hostnames><ports>'
      '<port protocol="tcp" portid="80"><state state="open"/></port>'
      '</ports></host></nmaprun>')
EOF
chmod 0555 "$fake"

PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/homelab-readonly" && pwd)" \
FAKE_NMAP="$fake" python3 - <<'PY'
import os
from scan import run_bounded_scan

result = run_bounded_scan(
    "192.0.2.0/30",
    allowed_networks=["192.0.2.0/29"],
    nmap_binary=os.environ["FAKE_NMAP"],
    ports="80,443",
    timeout_seconds=12,
)
assert result["source"] == "nmap.xml"
assert result["hosts"] == [{"ip": "192.0.2.2", "hostname": "synthetic-router", "ports": [{"port": 80, "protocol": "tcp"}]}]
assert result["retrieved_at"].endswith("Z")

for target in ("198.51.100.0/24", "192.0.2.0/28"):
    try:
        run_bounded_scan(target, allowed_networks=["192.0.2.0/29"], nmap_binary=os.environ["FAKE_NMAP"])
    except ValueError as exc:
        assert "scope" in str(exc)
    else:
        raise AssertionError("out-of-scope scan started")

for ports in ("0", "22;80", "65536", "1-0", ""):
    try:
        run_bounded_scan("192.0.2.0/30", allowed_networks=["192.0.2.0/29"], nmap_binary=os.environ["FAKE_NMAP"], ports=ports)
    except ValueError as exc:
        assert "port" in str(exc)
    else:
        raise AssertionError("invalid port specification accepted")

print("PASS bounded Nmap runner emits timestamped read-only evidence")
print("PASS scanner uses an explicit argv contract and target scope")
print("PASS invalid targets and port specifications fail before scanning")
PY
