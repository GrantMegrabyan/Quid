#!/usr/bin/env bash
# Launch the Quid API + webui together in dev mode, reachable from other
# machines on the LAN (e.g. a laptop hitting this devbox).
#
#   ./dev.sh                  # auto-detect this box's LAN IP
#   HOST=devbox.local ./dev.sh   # override the host the laptop will use
#
# Then open http://<HOST>:5173 from your laptop. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

# Host/IP the laptop uses to reach this devbox. Default: primary LAN IP.
HOST="${HOST:-$(hostname -I | awk '{print $1}')}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

# Tear down both children on Ctrl-C / exit (otherwise uvicorn + vite leak).
trap 'kill 0' EXIT

# Regex-escape dots in HOST for the CORS origin pattern.
HOST_RE="${HOST//./\\.}"

# Backend: bind all interfaces; allow the laptop's browser origin through CORS.
(
  cd api
  QUID_CORS_ORIGIN_REGEX="^http://(localhost|127\.0\.0\.1|${HOST_RE})(:[0-9]+)?$" \
    uv run quid-api serve --reload --host 0.0.0.0 --port "$API_PORT"
) &

# Frontend: bind all interfaces; point the laptop's browser at the devbox API.
(
  cd webui
  PUBLIC_API_BASE_URL="http://${HOST}:${API_PORT}" \
    npm run dev -- --host 0.0.0.0 --port "$WEB_PORT"
) &

echo ""
echo "  → Open  http://${HOST}:${WEB_PORT}  from your laptop"
echo "    API:  http://${HOST}:${API_PORT}  (docs at /docs)"
echo ""

wait
