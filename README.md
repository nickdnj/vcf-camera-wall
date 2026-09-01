# VCF Camera Wall

A lightweight, cross-platform **security-camera wall** for displaying live AXIS
camera feeds on a monitor — Mac, Windows, or Linux (including a Raspberry Pi /
mini-PC kiosk). No install, no cloud, no accounts. It runs entirely on your LAN.

Built for the three VCF Museum cameras:

| Tile | Camera | IP |
|------|--------|----|
| Mini | AXIS M3203 | `10.130.2.86` |
| Mainframe | AXIS M3203 | `10.130.2.87` |
| Modern | AXIS M3203 | `10.130.2.89` |

## How it works

The cameras expose **MJPEG over HTTP** (`/axis-cgi/mjpg/video.cgi`), which every
browser renders natively in an `<img>` — no plugins, transcoding, or media
server. The app is a single HTML page (`src/index.html`) that lays the feeds out
in a grid with live status, auto-reconnect, and a fullscreen kiosk mode. A tiny
Python static server (`scripts/serve.py`, stdlib only) hosts it so it runs from a
proper `http://` origin on any OS.

> These are older M3203 domes (max ~SVGA). The app defaults to **native**
> quality on purpose — forcing 720p/1080p makes them return HTTP 400 and go
> blank. Leave quality on `native` (or `low`) for these cameras.

## Quick start

**Easiest — double-click the launcher for your OS** (opens fullscreen kiosk):

- macOS → `scripts/start-macos.command`
- Windows → `scripts/start-windows.bat`
- Linux → `scripts/start-linux.sh`

**Or run the server by hand:**

```bash
python3 scripts/serve.py --open      # serves src/ and opens your browser
```

Then browse to the printed `http://localhost:8770/index.html`.

**Or just open `src/index.html`** directly in a browser (most browsers allow a
`file://` page to load the cameras; the server path is more reliable).

## Controls

| Key | Action |
|-----|--------|
| `F` | Fullscreen (kiosk) |
| `G` | Grid layout |
| `S` | Spotlight (one big + rail) |
| `1`–`9` | Solo that camera |
| `R` | Reconnect all |
| `Esc` | Exit fullscreen |

Click a tile in Solo/Spotlight to promote it.

## Configuration

Everything lives in **`src/config.js`** — add/remove cameras, rename tiles, set
quality, layout, reconnect timing, clock, and cursor-hide. It's plain JS, so no
build step: edit and reload.

### Add or change cameras

```js
cameras: [
  { name: "Mini",         ip: "10.130.2.86" },
  { name: "Loading Dock", ip: "10.130.9.177",
    stream: "http://10.130.9.177/axis-cgi/mjpg/video.cgi?fps=10" },
]
```

Use `stream:` to point at a full custom URL (e.g. a non-AXIS camera or a
specific resolution).

## Run it on boot (kiosk appliance)

### Raspberry Pi — one command (recommended)
On the Pi (Raspberry Pi OS *with desktop*), from the repo folder:
```bash
bash scripts/install-raspi.sh
```
Installs Chromium, runs the wall as a systemd service, and auto-launches
fullscreen kiosk at boot. Full walkthrough: **`docs/RASPBERRY-PI.md`**.

### Other
- **Windows:** put a shortcut to `start-windows.bat` in the Startup folder.
- **macOS:** add `start-macos.command` as a Login Item.
- **Generic Linux:** add `scripts/start-linux.sh` to your desktop autostart.

See `docs/USAGE.md` for details and troubleshooting.

## Admin panel (from your phone)

The wall shows a small **QR badge**; scan it (same Wi-Fi) to open the admin page
at `http://<pi>:8770/admin`, or browse there directly. It is PIN-gated (default
`2468` — **change it** under System → Change PIN). From the panel you can:

- **Cameras** — add / rename / reorder / disable feeds, set quality, or paste a
  custom stream URL. Changes apply to the wall within a few seconds, no reboot.
- **Scan** — discover AXIS / MJPEG cameras on the network and add them with a tap.
- **Wi-Fi** — see the current network and join another (best over Ethernet).
- **Display** — site name, layout, rotation, clock, and the QR badge.
- **System** — live status (IP, temp, disk, per-camera health), reboot / shutdown /
  restart, and software updates.

This makes the appliance reusable: point a new Pi at a different museum's cameras
entirely from the phone — no reflash, no editing files.

## Updating

If the Pi is a git checkout of this repo (cloned into `~/vcf-camera-wall`), the
admin **System → Software update** button checks GitHub and fast-forwards to the
latest `main`, then restarts — the wall reloads itself. By hand:

    cd ~/vcf-camera-wall && git pull && sudo systemctl restart vcf-camera-wall-server

## What this is not

No recording/NVR or motion detection. It's a live **display** wall (the admin
panel is PIN-gated, but the feeds themselves are shown, not authenticated). If you
later want recording, that's a separate NVR (or go2rtc/Frigate) — ask and we can add it.

---
Software project, team: Software Project Team. Provisioned by AgentArchitect (2026-08-30).
