# Delta local voice — current boundary and acceptance

Status: **staged, node-live; owner direct dogfood pending**.

## What is live now

The daily-use voice path is push-to-talk only:

```text
authenticated Open WebUI session
    → browser microphone
    → Open WebUI audio endpoint
    → Hermes Compute <PRIVATE_LAN_ADDRESS>:8766
    → local faster-whisper tiny.en
    → authenticated HADES text turn
```

The node runtime also exposes local Piper speech synthesis through the same
bounded, bearer-protected OpenAI-compatible endpoint. It is not a speaker
authentication system and it does not authorize actions. HADES identity,
tool policy, and resource authorization remain authoritative.

Runtime custody:

- user service: `hades-node-local-voice.service`
- node: Hermes Compute (`<PRIVATE_LAN_ADDRESS>`)
- port: `8766`, LAN-reachable and token-protected for POST routes
- STT: faster-whisper `tiny.en` on Hermes Compute; the runtime attempts CUDA
  and currently falls back to node-local CPU/int8 because `libcublas.so.12` is
  unavailable on the host
- TTS: Piper `en_US-lessac-medium`
- model data: node-local protected cache under `.cache/hades-voice`
- production UI: Open WebUI audio configuration, no laptop model processing

The service health endpoint deliberately reports that voice itself does not
authenticate speakers or authorize actions. Health is not a substitute for the
authenticated HADES session.

## Evidence completed

- runtime health: STT ready, TTS ready; current health reports CPU fallback
  after the CUDA library load failure
- after restart, health reports `cuda-pending` until the first real inference;
  it then reports the effective device (`cpu` on the current node) rather than
  claiming CUDA solely from configuration
- direct authenticated transcription and speech routes: pass
- Open WebUI container rendered with immutable image reference and remote audio
  endpoint environment configuration
- synthetic authenticated browser session: real Voice Input control, fake
  microphone capture, and real `/api/v1/audio/transcriptions` request returned
  successfully without browser errors
- existing local voice contract, pipeline, service, TTS, bridge, and Wyoming
  tests remain green
- user systemd manager has linger enabled, so the node service is restart-safe
  across user logout

## Current Open WebUI state

The persisted audio configuration has now been reconciled through Open WebUI's
configuration model using the protected deployment endpoint values:

- STT engine: OpenAI-compatible remote transport
- TTS engine: OpenAI-compatible remote transport
- remote endpoint: Hermes Compute `<PRIVATE_LAN_ADDRESS>:8766/v1`

Authenticated browser evidence now shows:

- production browser push-to-talk transcription: green, including 390×844
- real HADES chat submission after transcription: green
- real `Read Aloud` DOM action: HTTP 200 audio response, no browser errors
- Read Aloud interruption control: green in a browser session, with no page
  errors
- recording cancel control: green at 390×844; HADES labels the native cancel
  button for keyboard/screen-reader discovery and cancellation leaves no
  transcript
- spoken-style Grocy read (`Do we have eggs?`): reached HADES and returned the
  canonical household response
- node-local TTS transport: green
- bounded warm-node timing sample: STT `0.31–0.33s` per synthetic utterance;
  TTS `0.05–0.08s` for a short spoken response
- household synthetic voice authority probe remained non-authorizing: the
  deliberately protected request was transcribed imperfectly, routed through
  the household session, and produced no consequential action; this is
  evidence of fail-closed behavior, not a substitute for full owner/device
  confirmation acceptance

## Explicitly deferred

Home Assistant is not installed or live in this environment. No endpoint,
token, entity allowlist, or exposure path is available, so no HA integration is
enabled. The read-only adapter remains future-ready and fails closed until
owner-authorized inputs exist.

Also deferred:

- wake word and always-listening capture
- speaker identification or voice-based authorization
- owner direct physical-device dogfood
- long-duration mobile microphone and spoken-TTS acceptance

## Safety boundary

Voice transcripts enter the same authenticated actor/session policy as text.
The node audio runtime cannot select HADES tools, broaden authority, or act as
an alternative login path. A transcript is not proof of who spoke.
