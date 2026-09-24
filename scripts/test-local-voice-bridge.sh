#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir/integrations/local-voice" python3 - <<'PY'
import importlib.util

spec = importlib.util.spec_from_file_location("bridge", "integrations/local-voice/bridge.py")
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

events = [
    {"type": "audio-start", "data": {"rate": 16000, "width": 2, "channels": 1}},
    {"type": "audio-chunk", "data": {"rate": 16000, "width": 2, "channels": 1}, "payload": bytes([0, 0]) * 800},
    {"type": "audio-stop"},
]
audio = bridge.collect_audio(events)
assert bridge.transcribe(audio, lambda _: {"text": "check the pantry", "confidence": 0.91})["status"] == "ACCEPTED"
assert bridge.transcribe(audio, lambda _: {"text": "check the pantry"})["status"] == "CLARIFY"
for bad in (
    events[1:],
    events[:-1],
    [events[0], {"type": "audio-chunk", "data": {"rate": 8000, "width": 2, "channels": 1}, "payload": bytes([0, 0])}, events[2]],
):
    try:
        bridge.collect_audio(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid voice event sequence accepted")
print("PASS Wyoming audio stream assembled into validated WAV")
print("PASS missing STT confidence requires clarification")
print("PASS incomplete and format-changing voice streams rejected")
PY
