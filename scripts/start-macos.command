#!/bin/bash
# VCF Camera Wall — macOS launcher.
# Double-click this file in Finder. Starts the local server and opens the wall
# fullscreen (kiosk) in Chrome/Edge/Brave if available, else the default browser.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8770
URL="http://localhost:${PORT}/index.html"

# Start the server in the background (find python)
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  osascript -e 'display alert "Python not found" message "Install Python 3, or open src/index.html directly in your browser."'
  exit 1
fi
"$PY" "$DIR/serve.py" --port "$PORT" >/tmp/vcf-wall.log 2>&1 &
SERVER_PID=$!
sleep 1

open_kiosk() {
  local app="$1"
  if [ -d "/Applications/$app.app" ]; then
    open -na "$app" --args --kiosk --start-fullscreen --disable-infobars --incognito "$URL"
    return 0
  fi
  return 1
}

if   open_kiosk "Google Chrome"; then :
elif open_kiosk "Microsoft Edge"; then :
elif open_kiosk "Brave Browser"; then :
elif open_kiosk "Chromium";      then :
else
  # Fallback: default browser (no kiosk flag). Press F for fullscreen.
  open "$URL"
fi

echo "Camera wall running at $URL  (server PID $SERVER_PID)."
echo "Close this Terminal window to stop the server."
wait $SERVER_PID
