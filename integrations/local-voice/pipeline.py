"""Push-to-talk composition from Wyoming audio through HADES and local TTS."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from bridge import collect_audio, transcribe
from tts import synthesize


def handle_voice_turn(
    events: list[Mapping[str, Any]],
    *,
    stt_provider: Callable[[bytes], Mapping[str, Any]],
    chat_provider: Callable[[str, Mapping[str, Any]], str],
    tts_provider: Callable[[str], bytes],
) -> dict[str, Any]:
    """Process one turn without making voice an identity or authority signal."""
    try:
        transcript = transcribe(collect_audio(events), stt_provider)
    except ValueError as exc:
        return {"status": "FAILED", "error": str(exc), "voice_authenticated": False, "action_authorized": False}
    if not transcript.get("transcript_ready"):
        return {"status": transcript.get("status", "FAILED"), "transcript": transcript, "voice_authenticated": False, "action_authorized": False}

    request_context = {
        "voice_authenticated": False,
        "action_authorized": False,
        "transcript_status": transcript["status"],
    }
    try:
        response_text = chat_provider(transcript["text"], request_context)
    except Exception:
        return {"status": "FAILED", "transcript": transcript, "error": "HADES request failed", "voice_authenticated": False, "action_authorized": False}
    spoken = synthesize(response_text, tts_provider)
    if spoken.get("status") != "SUCCEEDED":
        return {"status": "FAILED", "transcript": transcript, "response": response_text, "tts": spoken, "voice_authenticated": False, "action_authorized": False}
    return {
        "status": "SUCCEEDED", "transcript": transcript, "response": response_text,
        "audio": spoken["audio"], "voice_authenticated": False, "action_authorized": False,
    }
