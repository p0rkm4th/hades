# Epsilon live adapter verification

This is the final authenticated verification gate for the private n8n
canary. It requires an API key created for the selected n8n owner account.
Do not commit, paste, or echo the key.

From the HADES checkout on the host that can reach the private runner:

```bash
read -r -s N8N_API_KEY
export N8N_API_KEY
export N8N_BASE_URL=http://127.0.0.1:5678
bash scripts/test-n8n-live-adapter.sh
unset N8N_API_KEY N8N_BASE_URL
```

The check must report one inactive `epsilon-server-health-watch-core`
workflow and only the bounded execution projection. It deliberately does not
run, activate, pause, edit, or delete the workflow. A 401 response means the
key is absent, invalid, or not authorized for the selected private runner; it
must not be worked around by weakening the adapter or exposing n8n publicly.
