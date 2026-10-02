# Local voice integration

The optional voice path uses configured speech-to-text and text-to-speech
services through Open WebUI. Endpoint URLs, model choices, device placement,
and credentials are private deployment inputs.

Voice is a convenience interface. It does not authenticate a speaker or grant
authority. Mutating actions continue to use the same identity, policy, and
confirmation checks as typed interactions. Missing speech services should
degrade gracefully to ordinary text chat.

Synthetic checks cover request shaping, bounded audio handling, provider
failure feedback, cancellation, and separation from authorization. Real-device
acceptance remains owner-gated.
