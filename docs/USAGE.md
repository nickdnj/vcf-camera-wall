# Usage & Troubleshooting

## Running the wall

Three ways, in order of convenience:

1. **Double-click the OS launcher** (`scripts/start-macos.command`,
   `start-windows.bat`, or `start-linux.sh`). It starts the local server and
   opens a browser in **fullscreen kiosk** mode.
2. **Command line:** `python3 scripts/serve.py --open` then open the printed URL.
3. **Direct file:** open `src/index.html` in a browser. Press **F** for
   fullscreen. (If images stay blank this way, use option 1 or 2 — a few
   browsers block `file://` pages from loading `http://` images.)

## Layouts

- **Grid** (`G`) — all cameras equal size. Best default for 3 cameras.
- **Spotlight** (`S`) — one large feed plus a side rail of the rest. Click a rail
  tile to promote it.
- **Solo** (`1`–`9`) — a single camera full-frame.

## Quality vs. these cameras (important)

`src/config.js` → `quality`:

| Value | Request | Works on |
|-------|---------|----------|
| `native` *(default)* | `fps=12` | **all cameras** incl. old M3203 |
| `low` | `640x480 · 8fps` | all cameras |
| `medium` | `1280x720 · 12fps` | **newer 1080p domes only** |
| `high` | `1920x1080 · 15fps` | newer 1080p domes only |

The three VCF cameras (`.86/.87/.89`) are **AXIS M3203**, which top out around
SVGA. Asking them for 720p/1080p returns **HTTP 400** and the tile goes blank.
Keep them on `native` or `low`.

## Auto-reconnect & watchdog

- If a feed drops, the tile shows **CONNECTING** and retries with backoff; after
  repeated failure it shows **OFFLINE** and keeps trying.
- `watchdogReloadMin` (default 10) soft-reloads every feed periodically to clear
  silent stalls (MJPEG can freeze without erroring). Set to `0` to disable.

## Kiosk on boot

### Raspberry Pi / Linux (recommended appliance)
Add to autostart, e.g. `~/.config/lxsession/LXDE-pi/autostart`:
```
@/full/path/to/vcf-camera-wall/scripts/start-linux.sh
```
Or a systemd user service that runs the script after the graphical target.
Tip: also disable screen blanking (`xset s off -dpms`).

### Windows
Create a shortcut to `start-windows.bat` and drop it in:
`shell:startup` (Win+R → `shell:startup`).

### macOS
System Settings → General → Login Items → add `start-macos.command`.

## Troubleshooting

**A tile is blank / "OFFLINE".**
- Confirm the camera is reachable from this machine:
  `curl -m4 -o /dev/null -w "%{http_code}\n" "http://10.130.2.86/axis-cgi/jpg/image.cgi?resolution=640x480"`
  — expect `200`.
- If you switched quality to Medium/High, switch back to `native` (M3203 can't do it).
- Camera may be on a different subnet/VLAN than this machine.

**All tiles blank when opening `src/index.html` directly.**
- Use the launcher or `serve.py` instead (real `http://` origin).

**Kiosk won't exit.** Press `Esc` (leaves fullscreen); to fully quit, close the
browser window / the server terminal.

**Change the port.** `python3 scripts/serve.py --port 9000`. The server also
auto-hops to the next free port if the default is busy.

**Wrong time on the clock.** It uses the machine's local clock — set the OS time.

## Adding recording later

This app only *displays*. For recording, motion alerts, or 24/7 retention, pair
these MJPEG/RTSP feeds with an NVR such as **Frigate**, **go2rtc**, **Shinobi**,
or **Blue Iris**. Ask and we can scaffold that as a next milestone.
