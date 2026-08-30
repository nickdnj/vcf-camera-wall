# Raspberry Pi kiosk setup

Turn a Raspberry Pi into a boot-to-wall appliance: power on → fullscreen camera
wall, no keyboard needed. Do this at home; on Wednesday just plug it into the
museum network and a monitor.

## What you need

- Raspberry Pi 3/4/5 (a 4 or 5 is smoother for MJPEG).
- **Raspberry Pi OS *with desktop*** (not Lite — the kiosk uses Chromium in the
  graphical session).
- Network + a monitor (HDMI).

## 1. Get the project onto the Pi

Either clone it (if you push this repo to GitHub):
```bash
git clone <your-repo-url> ~/vcf-camera-wall
```
…or copy the folder over with a USB stick / `scp` from your Mac:
```bash
scp -r /Users/nickd/Workspaces/vcf-camera-wall  pi@<pi-ip>:~/
```

## 2. Enable desktop auto-login (so it boots straight to the wall)

```bash
sudo raspi-config
#   → 1 System Options → S5 Boot / Auto Login → "Desktop Autologin"
```

## 3. Run the installer

```bash
cd ~/vcf-camera-wall
bash scripts/install-raspi.sh
```

It will:
- install Chromium + helpers,
- run the wall as a **systemd service** (`vcf-camera-wall-server`, starts on boot),
- add a **desktop autostart** that launches Chromium fullscreen kiosk at login,
- disable screen blanking.

## 4. Verify

Without rebooting, launch the kiosk to eyeball it:
```bash
bash scripts/kiosk-chromium.sh      # Ctrl+W / Alt+F4 to close
```
Then do the real test:
```bash
sudo reboot
```
The Pi should come up straight into the fullscreen wall.

> **At home the tiles will show OFFLINE / reconnecting** — the cameras
> (`10.130.2.x`) aren't on your home network. That's expected and correct. On the
> museum network they connect automatically. **Nothing to change on Wednesday.**

## Managing it

```bash
sudo systemctl status  vcf-camera-wall-server    # is the server up?
sudo systemctl restart vcf-camera-wall-server    # restart server
journalctl -u vcf-camera-wall-server -e          # server logs
bash scripts/install-raspi.sh --uninstall        # remove service + autostart
```

To change cameras/layout/quality: edit `src/config.js`, then
`sudo systemctl restart vcf-camera-wall-server` (or just reload the page).

## Tips for a clean appliance

- **Hide the mouse:** already handled (`unclutter`, and the app hides the cursor
  when idle).
- **Rotate the display** (portrait wall): Screen settings, or add
  `display_rotate=1` to `/boot/firmware/config.txt`.
- **Prevent SD-card wear:** consider read-only overlay FS (`raspi-config` →
  Performance) once you're happy with the config.
- **Auto-recover after power loss:** the systemd service restarts itself; Chromium
  relaunches at login. The app also auto-reconnects dropped feeds and soft-reloads
  every 10 min to clear stalls.
- **Screen blanking still happening?** On Bookworm (Wayland) run
  `sudo raspi-config` → Display Options → Screen Blanking → Disable.

## Which Pi network?

The Pi just needs to reach `10.130.2.86/.87/.89`. Wired Ethernet on the museum
LAN is most reliable. If Wi-Fi, make sure it joins a network/VLAN that can route
to the `10.130.2.x` cameras (the same reachability we confirmed from the Mac).
