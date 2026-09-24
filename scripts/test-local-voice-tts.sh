#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/local-voice" && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import io
import wave
from tts import synthesize

audio = io.BytesIO()
with wave.open(audio, "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16000)
    output.writeframes(b"\0\0" * 1600)

result = synthesize("  Hello   household  ", lambda text: audio.getvalue())
assert result["status"] == "SUCCEEDED"
assert result["text"] == "Hello household"
assert result["voice_authenticated"] is False
assert result["action_authorized"] is False
assert synthesize("hello", lambda _: b"not wav")["status"] == "FAILED"
assert synthesize("hello", lambda _: (_ for _ in ()).throw(RuntimeError()))["status"] == "FAILED"
assert synthesize("", lambda _: audio.getvalue())["status"] == "FAILED"
assert synthesize("x" * 2001, lambda _: audio.getvalue())["status"] == "FAILED"
print("PASS local TTS output is bounded and validates WAV audio")
print("PASS TTS failures remain explicit and non-authorizing")
PY
