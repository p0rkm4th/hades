#!/usr/bin/env bash
set -euo pipefail

marker='<!-- HADES ODYSSEUS THEME -->'
asset_version='remote-prefs-1'
if ! grep -q "$marker" /app/build/index.html; then
  sed -i "s|</head>|$marker<link rel=\"stylesheet\" href=\"/static/hades-theme.css?v=$asset_version\"><script src=\"/static/hades-theme.js?v=$asset_version\"></script></head>|" /app/build/index.html
fi
exec "$@"
