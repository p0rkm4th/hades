#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import importlib.util
import io
import sys

spec = importlib.util.spec_from_file_location("wyoming", sys.argv[1] + "/integrations/local-voice/wyoming.py")
wyoming = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wyoming)

events = [
    {"type": "audio-start", "data": {"rate": 16000, "width": 2, "channels": 1}},
    {"type": "audio-chunk", "data": {"rate": 16000, "width": 2, "channels": 1}, "payload": b"\0\0" * 80},
    {"type": "audio-stop"},
]
decoded = wyoming.round_trip(events)
assert [event["type"] for event in decoded] == ["audio-start", "audio-chunk", "audio-stop"]
assert decoded[1]["payload"] == b"\0\0" * 80
assert decoded[0]["data"]["rate"] == 16000
for encoded in (
    b'{"type":"audio-chunk","data_length":4,"payload_length":0}\nxx',
    b'{"type":"audio-chunk","data_length":0,"payload_length":4}\nxx',
    b'{"type":"audio-chunk","data_length":-1,"payload_length":0}\n',
):
    try:
        wyoming.read_event(io.BytesIO(encoded))
    except ValueError:
        pass
    else:
        raise AssertionError("malformed Wyoming event accepted")
try:
    wyoming.encode_event("audio-chunk", payload=b"x" * (wyoming.MAX_EVENT_BYTES + 1))
except ValueError:
    pass
else:
    raise AssertionError("oversized Wyoming event accepted")
print("PASS Wyoming push-to-talk event framing")
print("PASS truncated and invalid event rejection")
print("PASS bounded voice transport payload")
PY
