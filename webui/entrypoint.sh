#!/usr/bin/env bash
set -euo pipefail

marker='<!-- HADES ODYSSEUS THEME -->'
asset_version='remote-prefs-18-receipt-type-filter'
if ! grep -q "$marker" /app/build/index.html; then
  sed -i "s|</head>|$marker<link rel=\"stylesheet\" href=\"/static/hades-theme.css?v=$asset_version\"><script src=\"/static/hades-theme.js?v=$asset_version\"></script><script src=\"/static/finance-upload.js?v=$asset_version\"></script><script src=\"/static/receipt-upload.js?v=$asset_version\"></script></head>|" /app/build/index.html
else
  sed -i "s|<script src=\"/static/finance-upload.js?v=[^\"]*\"></script>|<script src=\"/static/finance-upload.js?v=$asset_version\"></script>|" /app/build/index.html
  sed -i "s|<script src=\"/static/receipt-upload.js?v=[^\"]*\"></script>|<script src=\"/static/receipt-upload.js?v=$asset_version\"></script>|" /app/build/index.html
  if ! grep -q "/static/finance-upload.js" /app/build/index.html; then
    sed -i "s|</head>|<script src=\"/static/finance-upload.js?v=$asset_version\"></script></head>|" /app/build/index.html
  fi
  if ! grep -q "/static/receipt-upload.js" /app/build/index.html; then
    sed -i "s|</head>|<script src=\"/static/receipt-upload.js?v=$asset_version\"></script></head>|" /app/build/index.html
  fi
fi
# The direct Hermes Compute Fast route is optional in disposable/reconstructed
# environments. When configured, apply the idempotent catalog migration after
# the persistent DB exists and before Open WebUI starts.
if [[ -n "${HADES_FAST_OPENAI_API_BASE_URL:-}" && -f /app/backend/data/webui.db ]]; then
  python3 /opt/hades/configure_fast_route.py
fi
exec "$@"
