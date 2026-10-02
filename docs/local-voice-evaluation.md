# Voice acceptance contract

This public document defines deployment-neutral acceptance for optional
speech-to-text and text-to-speech integrations. It does not contain private
endpoints, node identities, or model placement.

Acceptance should cover authentication, bounded request size, clear handling of
provider errors, cancellation, transcript correction, accessible controls,
and the fact that speech never authenticates a person or authorizes a write.
Use synthetic audio for CI. Owner-device and long-duration acceptance remain
separate deployment gates.
