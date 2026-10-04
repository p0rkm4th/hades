# Optional voice integration

Voice input and read-aloud are optional UI integrations. The deployment may
use an operator-configured speech endpoint and a local or remote transcription
and synthesis runtime. Endpoint URLs, model choices, device paths, and runtime
credentials are private operator inputs, not product defaults.

Voice does not authenticate a speaker or grant authority. The normal identity,
capability, and confirmation checks apply to every request. Speech recognition
may be ambiguous; consequential actions require the same explicit confirmation
as typed requests.

Health checks must distinguish endpoint reachability from successful
transcription or synthesis. When speech services are unavailable, the text
composer remains usable and HADES should report the failed voice operation
without changing the request's authorization state.
