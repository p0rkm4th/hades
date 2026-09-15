"""Provider-neutral boundaries for a local push-to-talk voice path.

This module validates transport evidence and transcription confidence. It does
not perform speech recognition, authenticate a speaker, or execute actions.
"""

from __future__ import annotations

import io
import re
import wave
from typing import Any

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 60
MAX_TRANSCRIPT_CHARS = 2_000
MIN_CONFIDENCE = 0.72


def validate_wav(audio: bytes) -> dict[str, Any]:
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("voice audio is empty or exceeds the bounded size")
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.getnframes()
            duration = frames / rate if rate else 0
    except (EOFError, wave.Error) as exc:
        raise ValueError("voice input must be a valid WAV stream") from exc
    if channels not in (1, 2) or sample_width != 2 or not 8_000 <= rate <= 48_000:
        raise ValueError("voice WAV must be 16-bit mono/stereo audio at 8-48 kHz")
    if frames <= 0 or duration > MAX_AUDIO_SECONDS:
        raise ValueError("voice recording duration is outside the bounded range")
    return {
        "format": "wav",
        "channels": channels,
        "sample_width": sample_width,
        "sample_rate": rate,
        "duration_seconds": round(duration, 3),
        "source": "local push-to-talk",
    }


def classify_transcript(text: str | None, confidence: float | None) -> dict[str, Any]:
    value = re.sub(r"\s+", " ", (text or "")).strip()
    if not value:
        return {
            "status": "SILENCE", "text": "", "transcript_ready": False,
            "action_authorized": False, "voice_authenticated": False,
        }
    if len(value) > MAX_TRANSCRIPT_CHARS:
        return {
            "status": "FAILED", "text": "", "error": "transcript exceeds bounded size",
            "transcript_ready": False, "action_authorized": False,
            "voice_authenticated": False,
        }
    if confidence is None or not 0 <= confidence <= 1:
        return {
            "status": "CLARIFY", "text": value,
            "reason": "speech confidence is unavailable", "transcript_ready": True,
            "action_authorized": False, "voice_authenticated": False,
        }
    if confidence < MIN_CONFIDENCE:
        return {
            "status": "CLARIFY", "text": value, "confidence": confidence,
            "reason": "speech confidence is below the action threshold",
            "transcript_ready": True, "action_authorized": False,
            "voice_authenticated": False,
        }
    return {
        "status": "ACCEPTED", "text": value, "confidence": confidence,
        "transcript_ready": True, "action_authorized": False,
        "voice_authenticated": False,
    }
