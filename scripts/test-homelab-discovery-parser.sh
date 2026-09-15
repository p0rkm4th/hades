#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/homelab-readonly" && pwd)" python3 - <<'PY'
from discovery import parse_nmap_xml

xml = '''<nmaprun><host><status state="up"/><address addr="192.0.2.2" addrtype="ipv4"/>
<hostnames><hostname name="router-synthetic"/></hostnames><ports>
<port protocol="tcp" portid="80"><state state="open"/><service name="http"/></port>
<port protocol="tcp" portid="22"><state state="closed"/></port></ports></host>
<host><status state="down"/><address addr="192.0.2.3" addrtype="ipv4"/></host></nmaprun>'''
result = parse_nmap_xml(xml, target="192.0.2.0/29", allowed_networks=["192.0.2.0/29"], retrieved_at="2026-09-15T12:00:00Z")
assert result["source"] == "nmap.xml"
assert result["retrieved_at"] == "2026-09-15T12:00:00Z"
assert result["hosts"] == [{"ip": "192.0.2.2", "hostname": "router-synthetic", "ports": [{"port": 80, "protocol": "tcp", "service": "http"}]}]

for target in ("10.0.0.0/8", "192.0.2.0/28"):
    try:
        parse_nmap_xml(xml, target=target, allowed_networks=["192.0.2.0/29"], retrieved_at="2026-09-15T12:00:00Z")
    except ValueError as exc:
        assert "scope" in str(exc)
    else:
        raise AssertionError("out-of-scope target accepted")

out_of_scope = xml.replace("192.0.2.2", "192.0.2.7")
try:
    parse_nmap_xml(out_of_scope, target="192.0.2.0/29", allowed_networks=["192.0.2.0/30"], retrieved_at="2026-09-15T12:00:00Z")
except ValueError as exc:
    assert "scope" in str(exc)
else:
    raise AssertionError("out-of-scope host accepted")

for bad in (b"not xml", b"", b"x" * (2 * 1024 * 1024 + 1)):
    try:
        parse_nmap_xml(bad, target="192.0.2.0/29", allowed_networks=["192.0.2.0/29"], retrieved_at="2026-09-15T12:00:00Z")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid or oversized evidence accepted")

for timestamp in ("", "not-a-timestamp"):
    try:
        parse_nmap_xml(xml, target="192.0.2.0/29", allowed_networks=["192.0.2.0/29"], retrieved_at=timestamp)
    except ValueError as exc:
        assert "timestamp" in str(exc)
    else:
        raise AssertionError("missing or invalid retrieval timestamp accepted")

print("PASS bounded Nmap XML evidence normalization")
print("PASS scanner evidence enforces target and host CIDR scope")
print("PASS closed/down hosts and ports remain non-authoritative evidence")
PY
