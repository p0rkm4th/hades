# Coding worker latency diagnostics

Coding worker timing diagnostics are disabled unless `HADES_CODING_WORKER_DIAGNOSTICS=1` is set for the worker service. The setting is intended for bounded acceptance or profiling windows and should be removed afterward.

An enabled turn records its task ID, total worker time, time to first tool/file/edit/test operation, test-call count and duration, cumulative native-tool duration, duplicate discovery-call count, the tool-name sequence, and model request count, total/maximum duration, and failed-request count. Model metrics are collected by the fixed-endpoint relay and reduced to these totals; they do not include request bodies. The worker does not record prompts, tool arguments, file paths, source, command output, or model responses.

The worker hashes discovery arguments in process memory only to recognize exact repeated calls. Those hashes and the raw trace are discarded before the worker result is returned. A duplicate count of zero means no exact repeat; semantically similar searches may still be distinct.

The opt-in trace flag is passed through the isolated worker's private task config, so it does not broaden the worker's environment. Worker timing includes Hermes orchestration; relay timing measures each approved inference round trip. UI first-visible timing is measured separately through synthetic-owner UI acceptance and is not stored by the coding worker.
