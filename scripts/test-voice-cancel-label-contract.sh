#!/usr/bin/env bash
set -euo pipefail

theme="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/webui/hades-theme.js"
grep -q "function labelVoiceRecordingCancel" "$theme" || { echo 'FAIL voice cancel label helper missing'; exit 1; }
grep -q "Cancel recording" "$theme" || { echo 'FAIL voice cancel accessible label missing'; exit 1; }
grep -q "confirm-recording-button" "$theme" || { echo 'FAIL voice cancel anchor missing'; exit 1; }
grep -q "function showVoiceFailureNotice" "$theme" || { echo 'FAIL voice failure notice helper missing'; exit 1; }
grep -q "audio/transcriptions" "$theme" || { echo 'FAIL voice transcription failure boundary missing'; exit 1; }
grep -q "Voice transcription is unavailable right now" "$theme" || { echo 'FAIL voice transcription failure copy missing'; exit 1; }
grep -q "function showTtsFailureNotice" "$theme" || { echo 'FAIL TTS failure notice helper missing'; exit 1; }
grep -q "Read Aloud is unavailable right now" "$theme" || { echo 'FAIL TTS failure copy missing'; exit 1; }
echo 'PASS voice recording cancellation is labeled through the HADES-owned UI layer'
