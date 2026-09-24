#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/homelab-readonly" && pwd)" python3 - <<'PY'
from discovery import parse_nmap_xml
from catalog import propose_inventory_candidates

xml = '''<nmaprun><host><status state="up"/><address addr="192.0.2.2" addrtype="ipv4"/>
<hostnames><hostname name="router-synthetic"/></hostnames><ports>
<port protocol="tcp" portid="80"><state state="open"/><service name="http"/></port>
<port protocol="tcp" portid="22"><state state="closed"/></port></ports></host>
<host><status state="down"/><address addr="192.0.2.3" addrtype="ipv4"/></host></nmaprun>'''
result = parse_nmap_xml(xml, target="192.0.2.0/29", allowed_networks=["192.0.2.0/29"], retrieved_at="2026-09-15T12:00:00Z")
assert result["source"] == "nmap.xml"
assert result["retrieved_at"] == "2026-09-15T12:00:00Z"
assert result["hosts"] == [{"ip": "192.0.2.2", "hostname": "router-synthetic", "ports": [{"port": 80, "protocol": "tcp", "service": "http"}]}]
projection = propose_inventory_candidates(result, {"results": [{"name": "router-synthetic", "ip": "192.0.2.2"}]})
assert projection["status"] == "REVIEW_REQUIRED"
assert projection["writes_performed"] is False
assert projection["candidates"][0]["netbox_match"]["name"] == "router-synthetic"
assert projection["candidates"][0]["open_ports"][0]["port"] == 80
assert projection["authority"]["inventory"] == "NetBox"

for target in ("198.51.100.0/24", "192.0.2.0/28"):
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

for bad in ({}, {"source": "netbox", "hosts": []}, {"source": "nmap.xml", "hosts": "bad"}):
    try:
        propose_inventory_candidates(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed discovery projection accepted")
try:
    propose_inventory_candidates(result, [])
except ValueError as exc:
    assert "NetBox" in str(exc)
else:
    raise AssertionError("malformed NetBox context accepted")
for bad in (
    {"source": "nmap.xml", "target": "not-a-network", "retrieved_at": "2026-09-15T12:00:00Z", "hosts": []},
    {"source": "nmap.xml", "target": "192.0.2.0/29", "retrieved_at": "", "hosts": []},
    {"source": "nmap.xml", "target": "192.0.2.0/29", "retrieved_at": "2026-09-15T12:00:00Z", "hosts": [{"ip": "198.51.100.2", "ports": []}]},
    {"source": "nmap.xml", "target": "192.0.2.0/29", "retrieved_at": "2026-09-15T12:00:00Z", "hosts": [{"ip": "192.0.2.2", "ports": [{"port": 0}]}]},
):
    try:
        propose_inventory_candidates(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("unprovenanceable discovery evidence accepted")

print("PASS bounded Nmap XML evidence normalization")
print("PASS scanner evidence enforces target and host CIDR scope")
print("PASS closed/down hosts and ports remain non-authoritative evidence")
print("PASS discovery produces review-only inventory candidates without writes")
PY
