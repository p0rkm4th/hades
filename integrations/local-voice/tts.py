"""Provider-neutral local TTS output boundary.

Synthesis is presentation only. This module never authenticates a speaker,
selects a user, or authorizes an action.
"""

from __future__ import annotations

import io
import wave
from collections.abc import Callable
from typing import Any

MAX_TEXT_CHARS = 2_000
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 60


def synthesize(text: str, provider: Callable[[str], bytes]) -> dict[str, Any]:
    value = " ".join(str(text or "").split())
    if not value:
        return {"status": "FAILED", "error": "TTS text is empty", "voice_authenticated": False}
    if len(value) > MAX_TEXT_CHARS:
        return {"status": "FAILED", "error": "TTS text exceeds bounded size", "voice_authenticated": False}
    try:
        audio = provider(value)
    except Exception:
        return {"status": "FAILED", "error": "TTS provider unavailable", "voice_authenticated": False}
    if not isinstance(audio, bytes) or not audio or len(audio) > MAX_AUDIO_BYTES:
        return {"status": "FAILED", "error": "TTS provider returned invalid audio", "voice_authenticated": False}
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            duration = source.getnframes() / source.getframerate()
            valid = (
                source.getnchannels() in (1, 2)
                and source.getsampwidth() == 2
                and 8_000 <= source.getframerate() <= 48_000
                and source.getnframes() > 0
                and duration <= MAX_AUDIO_SECONDS
            )
    except (EOFError, wave.Error):
        valid = False
    if not valid:
        return {"status": "FAILED", "error": "TTS provider returned an invalid WAV", "voice_authenticated": False}
    return {
        "status": "SUCCEEDED", "text": value, "audio": audio,
        "voice_authenticated": False, "action_authorized": False,
    }
