# Local voice evaluation

Status: SELECTED / STAGED.

The first voice milestone is push-to-talk, not wake word: capture audio,
transcribe locally, send the resulting request through the existing HADES
runtime, and synthesize the response locally. Voice proximity is not
authentication, so owner-only mutations remain excluded until an explicit
identity and confirmation mechanism exists.

## Selected composition

| Layer | Candidate | Decision |
|---|---|---|
| Audio transport | Wyoming protocol | Selected as the interoperable local voice boundary |
| Speech-to-text | whisper.cpp | Selected for local, self-hosted STT evaluation |
| Text-to-speech | Piper-compatible service | Evaluate current maintained implementation and license before pinning |
| Wake word | openWakeWord-class service | Deferred until push-to-talk is green |
| HADES request | Existing Hermes/Open WebUI path | Canonical runtime; no second voice agent |

Wyoming is intentionally limited to a trusted private network because its
protocol has no authentication or encryption. The archived
wyoming-satellite repository is not selected as a new dependency; future
satellites should use a maintained implementation or the protocol directly.

## First acceptance contract

Exercise ordinary conversation, Grocy reads, web/current information, personal
memory, and follow-ups. Also exercise silence, low confidence, background
noise, partial phrases, interruption, STT outage, TTS outage, and HADES
timeouts. A low-confidence transcription must not trigger a mutation; it must
clarify.

The provider-neutral input contract in
integrations/local-voice/contract.py validates bounded WAV input and maps
silence, unavailable confidence, low confidence, and accepted transcripts.
Its regression script does not require an audio device or an STT dependency;
the actual whisper.cpp/Wyoming composition remains the next staging step.

The provider-neutral Wyoming framing contract in
integrations/local-voice/wyoming.py now round-trips audio-start,
audio-chunk, and audio-stop events, rejects truncated/invalid frames, and
enforces a bounded payload. It remains transport-only and does not assert
identity or execute a HADES action.

## Current STT staging result

The official whisper.cpp amd64 image was pulled by immutable digest
sha256:f2190b995d27f6cd5bb9890792d598f2221893e9a1424fac6848ad904920eb5f.
Its bundled base English model reached model initialization but the
whisper-server process exited with status 132 before opening HTTP, including
when explicitly passed no-GPU mode. This is classified as
HOST-SENSITIVE / IMAGE-RUNTIME and is not a HADES defect. The image is not
promoted or registered as a live voice service until a compatible pinned
runtime or alternate STT implementation passes the same synthetic inference
contract.

As an alternate lane, the pinned HADES Open WebUI artifact contains
faster-whisper 1.2.1. A disposable CPU/int8 tiny.en run transcribed the
synthetic phrase “check the pantry and remember dinner” correctly. This is a
candidate reuse of an existing artifact, not a new production dependency; it
still needs an explicit service wrapper, immutable dependency record, Wyoming
wiring, latency measurement, and voice dogfood before promotion.

The candidate check is reproducible with
scripts/test-faster-whisper-staging.sh. It uses a generated local speech
fixture and the existing artifact's cached model path; it does not contact
HADES, Open WebUI, or a live external service.

The Wyoming-to-STT bridge primitives in integrations/local-voice/bridge.py now
assemble a complete audio-start/chunk/stop sequence into validated WAV bytes
and preserve missing provider confidence as CLARIFY. The contract rejects
incomplete streams, changed formats, and empty chunks; it is covered by
scripts/test-local-voice-bridge.sh.

Measure STT, HADES/model, tool, TTS, and total round-trip latency. Keep voice
metadata separate from private memory unless the user explicitly asks to
retain a personal fact.

No microphone, speaker, voice service, wake word, or production setting was
changed by this evaluation.

Upstream references:
https://github.com/ggml-org/whisper.cpp,
https://github.com/OHF-Voice/wyoming, and
https://github.com/rhasspy/wyoming-satellite.
