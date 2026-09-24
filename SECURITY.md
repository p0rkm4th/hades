# HADES security and privacy

Identity and household authorization are server-side; UI hiding is not the
security boundary. Secrets use protected files/upstream secret storage and are
never committed, logged, or echoed. Default network exposure is local.

Cloud fallback is optional and may transmit selected context to the configured
provider under the configured privacy policy. Provider changes never change
authority. Protected domains are local-only by default.
