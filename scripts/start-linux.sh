#!/bin/bash
# VCF Camera Wall — Linux launcher (great for a Raspberry Pi / mini-PC kiosk).
# Starts the local server and opens the wall fullscreen (kiosk) in Chromium/Chrome.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8770
URL="http://localhost:${PORT}/index.html"

PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python 3 not found. Install it (sudo apt install python3), or open src/index.html directly."
  exit 1
fi

"$PY" "$DIR/serve.py" --port "$PORT" >/tmp/vcf-wall.log 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT
sleep 1

BROWSER=""
for b in chromium-browser chromium google-chrome google-chrome-stable brave-browser; do
  if command -v "$b" >/dev/null 2>&1; then BROWSER="$b"; break; fi
done

if [ -n "$BROWSER" ]; then
  # --noerrdialogs + --disable-session-crashed-bubble keep a kiosk clean after power loss
  "$BROWSER" --kiosk --start-fullscreen --incognito --noerrdialogs \
    --disable-infobars --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required \
    "$URL"
else
  echo "No Chromium/Chrome found. Open this URL in any browser and press F: $URL"
  xdg-open "$URL" >/dev/null 2>&1 || true
  wait $SERVER_PID
fi
