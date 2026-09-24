#!/usr/bin/env bash
set -euo pipefail

voice_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../integrations/local-voice" && pwd)"
PYTHONPATH="$voice_dir" python3 - <<'PY'
import io
import wave
from pipeline import handle_voice_turn

audio = io.BytesIO()
with wave.open(audio, "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16000)
    output.writeframes(b"\0\0" * 1600)
wav = audio.getvalue()
events = [
    {"type": "audio-start", "data": {"rate": 16000, "width": 2, "channels": 1}},
    {"type": "audio-chunk", "data": {"rate": 16000, "width": 2, "channels": 1}, "payload": b"\0\0" * 1600},
    {"type": "audio-stop"},
]
spoken = []
seen_contexts = []

def tts(text):
    spoken.append(text)
    return wav

def run(transcript, response):
    def chat(text, context):
        assert text == transcript
        seen_contexts.append(context)
        return response
    return handle_voice_turn(
        events,
        stt_provider=lambda _: {"text": transcript, "confidence": 0.91},
        chat_provider=chat,
        tts_provider=tts,
    )

pantry = run("check the pantry", "Grocy says there are 2 tomatoes.")
assert pantry["status"] == "SUCCEEDED" and "Grocy" in pantry["response"]
web = run("what's the weather", "The web source reports a synthetic forecast.")
assert web["status"] == "SUCCEEDED" and "web" in web["response"]
preference = run("uh remember I like basil", "I can use that in this conversation, but voice is not authenticated for durable memory.")
assert preference["status"] == "SUCCEEDED"
mutation = run("add milk", "I need an authenticated confirmation before changing the shared list.")
assert mutation["status"] == "SUCCEEDED"
assert all(context == {
    "voice_authenticated": False,
    "action_authorized": False,
    "transcript_status": "ACCEPTED",
} for context in seen_contexts)

def fail_stt(_):
    raise RuntimeError("synthetic STT outage")
failure = handle_voice_turn(events, stt_provider=fail_stt, chat_provider=lambda *_: "must not run", tts_provider=tts)
assert failure["status"] == "FAILED" and failure["action_authorized"] is False

low = handle_voice_turn(
    events,
    stt_provider=lambda _: {"text": "add milk", "confidence": 0.2},
    chat_provider=lambda text, context: (
        (_ for _ in ()).throw(AssertionError("low-confidence voice was authorized"))
        if context["action_authorized"]
        else "Please repeat that; I will not change the shopping list from uncertain speech."
    ),
    tts_provider=tts,
)
assert low["status"] == "SUCCEEDED" and low["action_authorized"] is False
assert low["transcript"]["status"] == "CLARIFY"

assert len(spoken) == 5
print("PASS synthetic voice dogfood composes pantry, web, preference, and mutation-boundary turns")
print("PASS voice context never authenticates or authorizes an action")
print("PASS STT outage and low-confidence speech fail closed")
PY
