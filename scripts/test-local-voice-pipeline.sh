#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/local-voice" && pwd)"
PYTHONPATH="$repo_dir" python3 - <<'PY'
import io
import wave
from pipeline import handle_voice_turn

audio = io.BytesIO()
with wave.open(audio, "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16000)
    output.writeframes(b"\0\0" * 1600)
events = [
    {"type": "audio-start", "data": {"rate": 16000, "width": 2, "channels": 1}},
    {"type": "audio-chunk", "data": {"rate": 16000, "width": 2, "channels": 1}, "payload": b"\0\0" * 1600},
    {"type": "audio-stop"},
]
seen = {}
def chat(text, context):
    seen.update(text=text, context=context)
    return "The pantry is ready."

result = handle_voice_turn(events, stt_provider=lambda _: {"text": "check the pantry", "confidence": 0.91}, chat_provider=chat, tts_provider=lambda _: audio.getvalue())
assert result["status"] == "SUCCEEDED" and result["response"] == "The pantry is ready."
assert result["transcript"]["transcript_ready"] is True
assert seen["context"] == {"voice_authenticated": False, "action_authorized": False, "transcript_status": "ACCEPTED"}

silence = handle_voice_turn(events, stt_provider=lambda _: {"text": "", "confidence": 0.99}, chat_provider=lambda *_: (_ for _ in ()).throw(AssertionError("silence reached HADES")), tts_provider=lambda _: audio.getvalue())
assert silence["status"] == "SILENCE"

tts_failure = handle_voice_turn(events, stt_provider=lambda _: {"text": "check the pantry", "confidence": 0.91}, chat_provider=lambda *_: "reply", tts_provider=lambda _: b"invalid wav")
assert tts_failure["status"] == "FAILED" and tts_failure["action_authorized"] is False
print("PASS Wyoming audio composes through transcript, HADES, and TTS boundaries")
print("PASS silence stops before HADES request")
print("PASS voice pipeline never authorizes an action")
PY
