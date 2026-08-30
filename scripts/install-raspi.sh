#!/bin/bash
# =============================================================================
# VCF Camera Wall — Raspberry Pi kiosk installer
# -----------------------------------------------------------------------------
# Turns a Raspberry Pi (Raspberry Pi OS with desktop) into a boot-to-wall
# appliance:
#   • installs Chromium + helpers
#   • runs the wall server as a systemd service (starts on boot, restarts on fail)
#   • launches Chromium fullscreen kiosk automatically at desktop login
#   • disables screen blanking
#
# Run ON THE PI, from the repo folder:
#     bash scripts/install-raspi.sh
#
# Re-runnable (idempotent). Undo with:  bash scripts/install-raspi.sh --uninstall
# =============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
PORT="${VCF_PORT:-8770}"
SERVICE="vcf-camera-wall-server"
AUTOSTART="$HOME/.config/autostart/vcf-camera-wall.desktop"

log(){ printf "\033[1;32m▶ %s\033[0m\n" "$*"; }
warn(){ printf "\033[1;33m! %s\033[0m\n" "$*"; }

if [ "${1:-}" = "--uninstall" ]; then
  log "Uninstalling…"
  sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
  sudo rm -f "/etc/systemd/system/${SERVICE}.service"
  sudo systemctl daemon-reload 2>/dev/null || true
  rm -f "$AUTOSTART"
  log "Removed service and autostart. Chromium/packages left installed."
  exit 0
fi

# --- 1. packages ---------------------------------------------------------------
log "Installing packages (chromium, unclutter, curl)…"
sudo apt-get update -y
# package name differs by release; try both
sudo apt-get install -y chromium-browser 2>/dev/null || sudo apt-get install -y chromium || true
sudo apt-get install -y unclutter curl x11-xserver-utils 2>/dev/null || true

# --- 2. python check -----------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  sudo apt-get install -y python3
fi

# --- 3. server as a systemd service -------------------------------------------
log "Creating systemd service '${SERVICE}' (serves the wall on :${PORT})…"
sudo tee "/etc/systemd/system/${SERVICE}.service" >/dev/null <<UNIT
[Unit]
Description=VCF Camera Wall static server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
ExecStart=$(command -v python3) ${REPO}/scripts/serve.py --port ${PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE"
sleep 1
if curl -sf -m3 -o /dev/null "http://localhost:${PORT}/index.html"; then
  log "Server is up on http://localhost:${PORT}/"
else
  warn "Server did not answer yet — check: sudo systemctl status ${SERVICE}"
fi

# --- 4. kiosk autostart --------------------------------------------------------
log "Installing desktop autostart (Chromium kiosk at login)…"
chmod +x "${REPO}/scripts/kiosk-chromium.sh"
mkdir -p "$(dirname "$AUTOSTART")"
cat > "$AUTOSTART" <<DESKTOP
[Desktop Entry]
Type=Application
Name=VCF Camera Wall
Comment=Fullscreen camera wall kiosk
Exec=env VCF_PORT=${PORT} ${REPO}/scripts/kiosk-chromium.sh
X-GNOME-Autostart-enabled=true
Terminal=false
DESKTOP

# --- 5. screen-blanking note ---------------------------------------------------
log "Disabling screen blanking where possible…"
# X11 sessions: handled live by kiosk-chromium.sh (xset). For the login greeter
# and Wayland (Bookworm), also flip the raspi-config setting if available:
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_blanking 1 2>/dev/null || true   # 1 = disable blanking
fi

cat <<DONE

────────────────────────────────────────────────────────────
✓ Install complete.

  • Server:    systemd service '${SERVICE}' (auto-starts on boot)
  • Kiosk:     Chromium launches fullscreen at desktop login
  • URL:       http://localhost:${PORT}/index.html

Test now without rebooting:
    bash ${REPO}/scripts/kiosk-chromium.sh      # opens the kiosk
Reboot to verify the full boot-to-wall flow:
    sudo reboot

At home the cameras (10.130.2.x) are unreachable, so tiles will show
OFFLINE / reconnecting — that is expected. On the museum network they
connect automatically. Nothing to change on Wednesday: just plug in.

Handy:
    sudo systemctl status ${SERVICE}      # server health
    sudo systemctl restart ${SERVICE}     # restart server
    bash scripts/install-raspi.sh --uninstall
────────────────────────────────────────────────────────────
DONE
