#!/bin/bash
# Launch Chromium in kiosk mode pointing at the local camera wall.
# Called by the autostart entry on the Raspberry Pi desktop session.
# Detects the chromium binary name, waits for the server, and disables blanking.

PORT="${VCF_PORT:-8770}"
URL="http://localhost:${PORT}/index.html"

# --- keep the screen awake (X11; harmless/no-op under Wayland) ---
if command -v xset >/dev/null 2>&1; then
  xset s off      2>/dev/null || true
  xset -dpms      2>/dev/null || true
  xset s noblank  2>/dev/null || true
fi
command -v unclutter >/dev/null 2>&1 && (unclutter -idle 3 >/dev/null 2>&1 &)

# --- wait for the local server to answer (up to ~30s) ---
for i in $(seq 1 30); do
  if curl -sf -m2 -o /dev/null "$URL"; then break; fi
  sleep 1
done

# --- find the chromium binary (name varies across Pi OS releases) ---
BIN=""
for b in chromium-browser chromium chromium-browser-l10n google-chrome; do
  if command -v "$b" >/dev/null 2>&1; then BIN="$b"; break; fi
done
if [ -z "$BIN" ]; then
  echo "Chromium not found. Run scripts/install-raspi.sh first." >&2
  exit 1
fi

# Use a dedicated profile so 'restore pages?' prompts never appear
PROFILE="$HOME/.config/vcf-kiosk-profile"
mkdir -p "$PROFILE"

# --password-store=basic keeps Chromium off the GNOME login keyring. On a
# passwordless autologin appliance the keyring is never unlocked, so without
# this Chromium pops a blocking "unlock keyring" dialog over the wall at boot
# (and there's no keyboard/mouse to dismiss it). 'basic' uses an in-process
# store, which is fine here — the kiosk profile is incognito and stateless.
exec "$BIN" \
  --kiosk "$URL" \
  --user-data-dir="$PROFILE" \
  --password-store=basic \
  --start-fullscreen \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --check-for-update-interval=31536000 \
  --overscroll-history-navigation=0 \
  --autoplay-policy=no-user-gesture-required \
  --incognito
