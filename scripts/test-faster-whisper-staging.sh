#!/usr/bin/env bash
set -euo pipefail

# Disposable candidate check against the local HADES Open WebUI artifact.
image="hades-open-webui:channel-stage"
command -v espeak-ng >/dev/null || { echo 'SKIP espeak-ng is unavailable'; exit 0; }
docker image inspect "$image" >/dev/null || { echo "SKIP STT staging image is unavailable: $image"; exit 0; }

audio="/tmp/hades-faster-whisper-staging-$$.wav"
espeak-ng -v en-us -s 145 -w "$audio" "check the pantry and remember dinner"
result="$(docker run --rm --entrypoint python3 -v "$audio":/audio.wav:ro "$image" -c 'from faster_whisper import WhisperModel; model=WhisperModel("tiny.en", device="cpu", compute_type="int8", download_root="/tmp/whisper-model"); segments, _ = model.transcribe("/audio.wav", beam_size=1, vad_filter=True); print(" ".join(segment.text.strip() for segment in segments))')"
printf 'STT: %s\n' "$result"
lower="$(printf '%s' "$result" | tr '[:upper:]' '[:lower:]')"
[[ "$lower" == *pantry* && "$lower" == *dinner* ]] || { echo 'FAIL synthetic phrase was not transcribed'; exit 1; }
printf 'PASS disposable faster-whisper CPU/int8 transcription\n'
