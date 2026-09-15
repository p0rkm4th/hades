#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import importlib.util
import io
import sys
import wave

spec = importlib.util.spec_from_file_location("voice", sys.argv[1] + "/integrations/local-voice/contract.py")
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)

audio = io.BytesIO()
with wave.open(audio, "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16000)
    output.writeframes(b"\0\0" * 1600)
assert voice.validate_wav(audio.getvalue())["duration_seconds"] == 0.1
for bad in (b"", b"not wav"):
    try:
        voice.validate_wav(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid audio accepted")
assert voice.classify_transcript("", 0.99)["status"] == "SILENCE"
assert voice.classify_transcript("  add   milk  ", 0.4)["status"] == "CLARIFY"
accepted = voice.classify_transcript("  check the pantry  ", 0.9)
assert accepted["status"] == "ACCEPTED"
assert accepted["transcript_ready"] is True
assert accepted["action_authorized"] is False
assert accepted["voice_authenticated"] is False
clarify = voice.classify_transcript("restart that container", None)
assert clarify["status"] == "CLARIFY"
assert clarify["transcript_ready"] is True
assert clarify["action_authorized"] is False
assert voice.classify_transcript("x" * (voice.MAX_TRANSCRIPT_CHARS + 1), 1)["status"] == "FAILED"
print("PASS bounded push-to-talk WAV contract")
print("PASS silence and low-confidence clarification contract")
print("PASS voice never authenticates speaker")
PY
