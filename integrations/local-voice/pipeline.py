"""Push-to-talk composition from Wyoming audio through HADES and local TTS."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import time
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
    started = time.perf_counter()
    timings: dict[str, float] = {}

    def finish(result: dict[str, Any]) -> dict[str, Any]:
        timings["total_seconds"] = round(time.perf_counter() - started, 6)
        result["timings"] = dict(timings)
        return result

    try:
        capture_started = time.perf_counter()
        audio = collect_audio(events)
        timings["audio_capture_seconds"] = round(time.perf_counter() - capture_started, 6)
        stt_started = time.perf_counter()
        transcript = transcribe(audio, stt_provider)
        timings["stt_seconds"] = round(time.perf_counter() - stt_started, 6)
    except ValueError as exc:
        return finish({"status": "FAILED", "error": str(exc), "voice_authenticated": False, "action_authorized": False})
    if not transcript.get("transcript_ready"):
        return finish({"status": transcript.get("status", "FAILED"), "transcript": transcript, "voice_authenticated": False, "action_authorized": False})

    request_context = {
        "voice_authenticated": False,
        "action_authorized": False,
        "transcript_status": transcript["status"],
    }
    try:
        model_started = time.perf_counter()
        response_text = chat_provider(transcript["text"], request_context)
        timings["model_response_seconds"] = round(time.perf_counter() - model_started, 6)
        timings["time_to_first_response_seconds"] = round(time.perf_counter() - started, 6)
    except Exception:
        return finish({"status": "FAILED", "transcript": transcript, "error": "HADES request failed", "voice_authenticated": False, "action_authorized": False})
    tts_started = time.perf_counter()
    spoken = synthesize(response_text, tts_provider)
    timings["tts_seconds"] = round(time.perf_counter() - tts_started, 6)
    if spoken.get("status") != "SUCCEEDED":
        return finish({"status": "FAILED", "transcript": transcript, "response": response_text, "tts": spoken, "voice_authenticated": False, "action_authorized": False})
    return finish({
        "status": "SUCCEEDED", "transcript": transcript, "response": response_text,
        "audio": spoken["audio"], "voice_authenticated": False, "action_authorized": False,
    })
