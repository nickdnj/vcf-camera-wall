/* ============================================================================
 * VCF Camera Wall — configuration
 * ----------------------------------------------------------------------------
 * Edit this file to change which cameras appear. It is plain JavaScript so it
 * loads fine even when you open index.html directly (file://) with no server.
 *
 * Each camera:
 *   name    - label shown on the tile
 *   ip      - camera IP address
 *   stream  - (optional) full MJPEG URL override. If omitted, the URL is built
 *             as:  http://<ip>/axis-cgi/mjpg/video.cgi?<quality>
 *   snap    - (optional) still-image URL used for the health watchdog
 *
 * IMPORTANT: these three are older AXIS M3203 domes. Do NOT force a big
 * resolution on them — they only do up to ~SVGA and reject 720p/1080p with an
 * HTTP 400. Leaving quality on "native" keeps them streaming.
 * ==========================================================================*/

window.WALL_CONFIG = {
  title: "VCF Museum — Security Wall",

  cameras: [
    { name: "Mini",      ip: "10.130.2.86" },
    { name: "Mainframe", ip: "10.130.2.87" },
    { name: "Modern",    ip: "10.130.2.89" },
  ],

  // MJPEG quality appended to the stream URL.
  //   "native"  -> fps=12                 (works on ALL cameras, incl. old M3203)
  //   "low"     -> resolution=640x480&fps=8
  //   "medium"  -> resolution=1280x720&fps=12   (newer 1080p domes only)
  //   "high"    -> resolution=1920x1080&fps=15   (newer 1080p domes only)
  quality: "native",

  // Default layout: "grid" | "spotlight" | "solo"
  layout: "grid",

  // Auto-reconnect / watchdog
  reconnectDelayMs: 3000,     // wait before retrying a dropped stream
  maxReconnectDelayMs: 30000, // backoff ceiling
  watchdogReloadMin: 10,      // soft-reload every N minutes to clear silent stalls (0 = off)

  // Kiosk behavior
  hideCursorAfterSec: 5,      // hide mouse pointer when idle (0 = never)
  showClock: true,
};
