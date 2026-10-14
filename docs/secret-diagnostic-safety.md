# Secret-safe diagnostics

Never enable Bash xtrace while protected configuration is in the environment or
being sourced. Do not use `env` or `printenv` to inspect production process
environments. Operational entrypoints that source protected inputs must clear
inherited xtrace before reading them.

For deployment identity, use the bounded fingerprint command. It reads the
protected file as bytes and prints only a configuration label and SHA-256:

```sh
python3 scripts/hermes-runtime-artifact.py fingerprint \
  --config-input hermes-profile=/path/to/protected/hermes.env
```

The fingerprint is diagnostic identity, not a substitute for secret rotation
after a value has been disclosed. Do not pass secrets as command-line
arguments, echo them, or include them in test output. Regression coverage uses
synthetic sentinel values only.
