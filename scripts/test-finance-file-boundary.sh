#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import importlib.util
import sys

path = "integrations/actual-finance-import/file_boundary.py"
spec = importlib.util.spec_from_file_location("finance_file", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

fixtures = {
    "statement.csv": b"Date,Payee,Amount\n2026-09-01,Store,-3.00\n",
    "statement.qif": b"!Type:Bank\nD09/01/2026\nT-3.00\nPStore\n^\n",
    "statement.ofx": b"<OFX><BANKMSGSRSV1>statement</BANKMSGSRSV1></OFX>",
    "statement.qfx": b"OFXHEADER:100\nDATA:OFXSGML\n<OFX>statement",
    "statement.camt": b"<Document xmlns='urn:iso:std:iso:20022:tech:xsd:camt.053.001.08'></Document>",
}
digests = set()
for filename, data in fixtures.items():
    result = module.build_native_handoff(data, filename)
    assert result["status"] == "PREVIEW"
    assert result["format"] == filename.rsplit(".", 1)[1].upper()
    assert result["native_import_required"] is True
    assert result["canonical_target"] == "Actual Budget native file import"
    assert result["writes_performed"] is False
    assert len(result["file_sha256"]) == 64
    digests.add(result["file_sha256"])
assert len(digests) == len(fixtures)

for filename, data in (
    ("statement.txt", b"Date,Payee,Amount\n2026,Store,1\n"),
    ("statement.qif", b"Date,Payee,Amount\n2026,Store,1\n"),
    ("statement.ofx", b"not an ofx document"),
):
    try:
        module.build_native_handoff(data, filename)
    except module.FinanceFileError:
        pass
    else:
        raise AssertionError(f"invalid financial file accepted: {filename}")

try:
    module.build_native_handoff(b"x" * (module.MAX_FILE_BYTES + 1), "statement.csv")
except module.FinanceFileError:
    pass
else:
    raise AssertionError("oversized financial file accepted")

print("PASS Actual-supported CSV/QIF/OFX/QFX/CAMT handoff classification")
print("PASS financial handoff is metadata-only, bounded, and confirmation-gated")
print("PASS invalid formats and content fail closed")
PY
