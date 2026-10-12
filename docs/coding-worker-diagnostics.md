# Coding worker latency diagnostics

Coding worker timing diagnostics are disabled unless `HADES_CODING_WORKER_DIAGNOSTICS=1` is set for the worker service. The setting is intended for bounded acceptance or profiling windows and should be removed afterward.

An enabled turn records its task ID, total worker time, time to first tool/file/edit/test operation, test-call count and duration, cumulative native-tool duration, duplicate discovery-call count, and the tool-name sequence. It does not record prompts, tool arguments, file paths, source, command output, or model responses.

The worker hashes discovery arguments in process memory only to recognize exact repeated calls. Those hashes and the raw trace are discarded before the worker result is returned. A duplicate count of zero means no exact repeat; semantically similar searches may still be distinct.

Worker and tool timings include Hermes orchestration. They do not isolate model-server time or measure when the UI first renders progress. Use them to identify whether coding latency is dominated by tool execution or by the wider agent/inference interval, then collect a focused trace if more precision is needed.
