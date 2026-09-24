#!/usr/bin/env bash
set -euo pipefail

# Verify the pinned Open WebUI mention encoding without starting a model
# backend. Execution of a mentioned model remains a separate acceptance.
docker run --rm --entrypoint python3 hades-open-webui:channel-stage -c '
from open_webui.utils.channels import extract_mentions, replace_mentions

message = "Please ask <@M:synthetic-channel-model|HADES> about dinner."
mentions = extract_mentions(message)
assert mentions == [{"id_type": "M", "id": "synthetic-channel-model"}]
assert replace_mentions(message) == "Please ask HADES about dinner."
assert replace_mentions(message, use_label=False) == "Please ask synthetic-channel-model about dinner."
assert extract_mentions("<@U:beta-user|Beta>") == [{"id_type": "U", "id": "beta-user"}]
print("PASS pinned Open WebUI model-mention encoding and replacement")
'
