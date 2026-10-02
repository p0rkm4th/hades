# Epsilon integration preparation

Epsilon integrations use bounded, typed sources and preserve authorization at
the source boundary. They must identify the source and observation time,
report partial failure honestly, and avoid treating repository artifacts as
canonical application state.

Private service URLs, credentials, artifact locations, and custody settings are
configured outside public HADES source. Synthetic tests cover source outage,
malformed responses, and non-mutating verification.
