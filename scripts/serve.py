#!/usr/bin/env python3
"""
VCF Camera Wall server — zero-dependency (stdlib only).

Serves the wall (index.html) and a phone-friendly admin page (admin.html), and
exposes a small JSON API to configure the appliance from a phone on the same LAN:

  Public (no auth — read only, safe to expose to the wall):
    GET  /                     -> the wall
    GET  /admin                -> admin page
    GET  /api/config           -> effective config (no secrets) + adminUrl/lanIp
    GET  /api/qr               -> QR PNG/SVG for the admin URL (needs `qrencode`)

  Admin (PIN-gated, cookie session):
    POST /api/admin/login      -> { pin } -> sets session cookie
    POST /api/admin/logout
    GET  /api/admin/config     -> full config
    POST /api/admin/config     -> replace config (bumps version, cameras/site/etc.)
    POST /api/admin/pin        -> { current, next } change PIN
    POST /api/admin/scan       -> { subnet? } discover cameras on the LAN
    GET  /api/admin/wifi       -> current + saved + scanned networks
    POST /api/admin/wifi       -> { ssid, password, hidden? } add/connect
    GET  /api/admin/system     -> host/ip/uptime/temp/disk + camera health
    POST /api/admin/system     -> { action: reboot|poweroff|restart-server|reload-wall }

Binds 0.0.0.0 so a phone can reach the admin page; the kiosk still uses localhost.
Only the admin surface mutates anything, and it is PIN-gated.

Usage: python3 serve.py [--port 8770] [--open]
"""
import argparse, os, sys, json, threading, socket, subprocess, time, hashlib, secrets
import base64, urllib.request, http.cookies, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
DEFAULT_CONFIG_PATH = os.path.join(SRC, "config.default.json")
DEFAULT_PIN = "2468"                       # change in the admin page!
SERVICE = "vcf-camera-wall-server"
QUALITY = {
    "native": "fps=12",
    "low":    "resolution=640x480&fps=8",
    "medium": "resolution=1280x720&fps=12",
    "high":   "resolution=1920x1080&fps=15",
}

_lock = threading.Lock()
_sessions = {}                             # token -> expiry epoch
SESSION_TTL = 3600 * 8

# ----------------------------------------------------------------------------- config
def _load_default():
    with open(DEFAULT_CONFIG_PATH) as f:
        return json.load(f)

def load_config():
    with _lock:
        if not os.path.isfile(CONFIG_PATH):
            cfg = _load_default()
            _seed_pin(cfg)
            _write(cfg)
            return cfg
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
        except Exception:
            cfg = _load_default()
        if "admin" not in cfg or not cfg["admin"].get("pinHash"):
            _seed_pin(cfg)
            _write(cfg)
        return cfg

def _seed_pin(cfg, pin=DEFAULT_PIN):
    salt = secrets.token_hex(8)
    cfg["admin"] = {"salt": salt, "pinHash": _pin_hash(pin, salt)}

def _pin_hash(pin, salt):
    return hashlib.sha256((salt + ":" + str(pin)).encode()).hexdigest()

def _write(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_PATH)

def save_config(cfg):
    with _lock:
        cfg["version"] = int(cfg.get("version", 0)) + 1
        _write(cfg)
        return cfg

def public_config(cfg, port):
    """Config the wall/admin may read without secrets."""
    out = {k: v for k, v in cfg.items() if k != "admin"}
    ip = lan_ip()
    out["lanIp"] = ip
    out["adminUrl"] = "http://%s:%d/admin" % (ip, port)
    return out

# ----------------------------------------------------------------------------- helpers
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def sh(args, timeout=15):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", str(e)

def stream_url(cam, default_quality):
    if cam.get("stream"):
        return cam["stream"]
    q = QUALITY.get(cam.get("quality") or default_quality, QUALITY["native"])
    return "http://%s/axis-cgi/mjpg/video.cgi%s" % (cam["ip"], ("?" + q if q else ""))

def snap_url(cam):
    return "http://%s/axis-cgi/jpg/image.cgi" % cam["ip"]

# ----------------------------------------------------------------------------- camera scan
def probe_camera(ip, timeout=1.4):
    try:
        socket.create_connection((ip, 80), timeout=timeout).close()
    except OSError:
        return None
    for path in ("/axis-cgi/jpg/image.cgi?resolution=320x240",
                 "/axis-cgi/jpg/image.cgi", "/jpg/image.jpg"):
        try:
            with urllib.request.urlopen("http://%s%s" % (ip, path), timeout=timeout) as r:
                data = r.read(300000)
                if data[:2] == b"\xff\xd8":     # JPEG magic
                    return {"ip": ip, "kind": "axis" if "axis" in path else "mjpeg",
                            "snapshot": "data:image/jpeg;base64," + base64.b64encode(data).decode()}
        except Exception:
            continue
    return None

def scan_cameras(subnet=None, timeout=1.4):
    if not subnet:
        subnet = ".".join(lan_ip().split(".")[:3])
    subnet = subnet.rstrip(".")
    hosts = ["%s.%d" % (subnet, i) for i in range(1, 255)]
    found = []
    with ThreadPoolExecutor(max_workers=64) as ex:
        for res in ex.map(lambda h: probe_camera(h, timeout), hosts):
            if res:
                found.append(res)
    found.sort(key=lambda c: tuple(int(x) for x in c["ip"].split(".")))
    return {"subnet": subnet, "count": len(found), "cameras": found}

# ----------------------------------------------------------------------------- wifi (nmcli)
def wifi_status():
    out = {"current": None, "saved": [], "scan": []}
    _, o, _ = sh(["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device", "status"])
    for line in o.splitlines():
        p = line.split(":")
        if len(p) >= 3 and p[0] == "wlan0" and p[1] == "connected":
            out["current"] = p[2]
    _, o, _ = sh(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    for line in o.splitlines():
        p = line.split(":")
        if len(p) >= 2 and "wireless" in p[1]:
            out["saved"].append(p[0])
    _, o, _ = sh(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"], timeout=12)
    seen = set()
    for line in o.splitlines():
        p = line.split(":")
        if len(p) >= 4 and p[1] and p[1] not in seen:
            seen.add(p[1])
            out["scan"].append({"ssid": p[1], "signal": p[2], "security": p[3],
                                "inUse": p[0] == "*"})
    out["scan"].sort(key=lambda n: int(n["signal"] or 0), reverse=True)
    return out

def wifi_connect(ssid, password, hidden=False):
    args = ["sudo", "-n", "nmcli", "device", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    if hidden:
        args += ["hidden", "yes"]
    rc, o, e = sh(args, timeout=40)
    return {"ok": rc == 0, "output": (o + e).strip()}

# ----------------------------------------------------------------------------- system
def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None

def system_status(cfg):
    _, up, _ = sh(["uptime", "-p"])
    _, disk, _ = sh(["df", "-h", "/"])
    disk_line = disk.splitlines()[1].split() if len(disk.splitlines()) > 1 else []
    model = ""
    try:
        with open("/proc/device-tree/model") as f:
            model = f.read().strip("\x00")
    except Exception:
        pass
    # camera health: server-side snapshot probe
    health = []
    def check(cam):
        ok = False
        try:
            with urllib.request.urlopen(snap_url(cam), timeout=2) as r:
                ok = r.read(2)[:2] == b"\xff\xd8"
        except Exception:
            ok = False
        return {"id": cam.get("id"), "name": cam.get("name"), "ip": cam.get("ip"), "live": ok}
    cams = [c for c in cfg.get("cameras", []) if c.get("enabled", True)]
    if cams:
        with ThreadPoolExecutor(max_workers=min(8, len(cams))) as ex:
            health = list(ex.map(check, cams))
    return {
        "hostname": socket.gethostname(),
        "model": model,
        "lanIp": lan_ip(),
        "uptime": up.strip(),
        "cpuTemp": cpu_temp(),
        "disk": {"size": disk_line[1], "used": disk_line[2], "avail": disk_line[3],
                 "pct": disk_line[4]} if len(disk_line) >= 5 else None,
        "cameras": health,
    }

def system_action(action):
    if action == "reboot":
        subprocess.Popen(["sudo", "-n", "reboot"], start_new_session=True); return {"ok": True}
    if action == "poweroff":
        subprocess.Popen(["sudo", "-n", "poweroff"], start_new_session=True); return {"ok": True}
    if action == "restart-server":
        subprocess.Popen(["sudo", "-n", "systemctl", "restart", SERVICE], start_new_session=True)
        return {"ok": True}
    if action == "reload-wall":
        cfg = load_config(); save_config(cfg)         # bump version -> wall reloads on poll
        return {"ok": True, "version": cfg["version"]}
    return {"ok": False, "error": "unknown action"}

# ----------------------------------------------------------------------------- qr
def qr_bytes(url):
    for args, ctype in ((["qrencode", "-t", "SVG", "-m", "1", "-o", "-", url], "image/svg+xml"),
                        (["qrencode", "-t", "PNG", "-s", "6", "-m", "1", "-o", "-", url], "image/png")):
        try:
            r = subprocess.run(args, capture_output=True, timeout=8)
            if r.returncode == 0 and r.stdout:
                return r.stdout, ctype
        except Exception:
            continue
    return None, None

# ----------------------------------------------------------------------------- auth
def new_session():
    tok = secrets.token_urlsafe(24)
    _sessions[tok] = time.time() + SESSION_TTL
    return tok

def valid_session(tok):
    exp = _sessions.get(tok)
    if not exp:
        return False
    if exp < time.time():
        _sessions.pop(tok, None); return False
    return True

# ----------------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "VCFWall/2.0"
    PORT = 8770

    def log_message(self, format, *args):
        pass

    # --- io helpers ---
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self._bytes(f.read(), ctype)
        except FileNotFoundError:
            self._bytes(b"not found", "text/plain", 404)

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _token(self):
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return c["adm"].value if "adm" in c else None

    def _auth(self):
        return valid_session(self._token())

    def _need_auth(self):
        self._json({"error": "auth"}, 401); return False

    # --- routing ---
    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p in ("/", "/index.html"):
            return self._file(os.path.join(SRC, "index.html"), "text/html; charset=utf-8")
        if p in ("/admin", "/admin.html"):
            return self._file(os.path.join(SRC, "admin.html"), "text/html; charset=utf-8")
        if p == "/config.js":
            return self._file(os.path.join(SRC, "config.js"), "application/javascript")
        if p == "/config.default.json":
            return self._file(DEFAULT_CONFIG_PATH, "application/json")
        if p == "/api/config":
            return self._json(public_config(load_config(), self.PORT))
        if p == "/api/qr":
            cfg = load_config()
            body, ctype = qr_bytes(public_config(cfg, self.PORT)["adminUrl"])
            if body:
                return self._bytes(body, ctype)
            return self._json({"error": "qrencode not installed"}, 501)
        if p == "/api/admin/wifi":
            if not self._auth(): return self._need_auth()
            return self._json(wifi_status())
        if p == "/api/admin/config":
            if not self._auth(): return self._need_auth()
            return self._json(load_config())
        if p == "/api/admin/system":
            if not self._auth(): return self._need_auth()
            return self._json(system_status(load_config()))
        # static assets in src/
        safe = os.path.normpath(p).lstrip("/")
        fp = os.path.join(SRC, safe)
        if os.path.isfile(fp) and fp.startswith(SRC):
            ext = os.path.splitext(fp)[1]
            ctype = {".js": "application/javascript", ".css": "text/css",
                     ".png": "image/png", ".svg": "image/svg+xml",
                     ".json": "application/json", ".ico": "image/x-icon"}.get(ext, "application/octet-stream")
            return self._file(fp, ctype)
        return self._bytes(b"not found", "text/plain", 404)

    def do_POST(self):
        p = self.path.split("?", 1)[0]
        body = self._read_json()

        if p == "/api/admin/login":
            cfg = load_config()
            adm = cfg.get("admin", {})
            if _pin_hash(body.get("pin", ""), adm.get("salt", "")) == adm.get("pinHash"):
                tok = new_session()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                ck = http.cookies.SimpleCookie()
                ck["adm"] = tok
                ck["adm"]["path"] = "/"
                ck["adm"]["httponly"] = True
                ck["adm"]["max-age"] = SESSION_TTL
                self.send_header("Set-Cookie", ck["adm"].OutputString())
                out = json.dumps({"ok": True}).encode()
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
                return
            return self._json({"ok": False, "error": "bad pin"}, 403)

        if p == "/api/admin/logout":
            _sessions.pop(self._token(), None)
            return self._json({"ok": True})

        # everything below requires auth
        if not self._auth():
            return self._need_auth()

        if p == "/api/admin/config":
            cfg = load_config()
            for k in ("site", "cameras", "layout", "quality", "display", "behavior"):
                if k in body:
                    cfg[k] = body[k]
            saved = save_config(cfg)
            return self._json({"ok": True, "version": saved["version"]})

        if p == "/api/admin/pin":
            cfg = load_config()
            adm = cfg.get("admin", {})
            if _pin_hash(body.get("current", ""), adm.get("salt", "")) != adm.get("pinHash"):
                return self._json({"ok": False, "error": "current pin wrong"}, 403)
            nxt = str(body.get("next", "")).strip()
            if len(nxt) < 4:
                return self._json({"ok": False, "error": "pin must be >= 4 digits"}, 400)
            _seed_pin(cfg, nxt)
            save_config(cfg)
            return self._json({"ok": True})

        if p == "/api/admin/scan":
            return self._json(scan_cameras(body.get("subnet")))

        if p == "/api/admin/wifi":
            return self._json(wifi_connect(body.get("ssid", ""), body.get("password", ""),
                                           bool(body.get("hidden"))))

        if p == "/api/admin/system":
            return self._json(system_action(body.get("action", "")))

        return self._json({"error": "not found"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(os.path.join(SRC, "index.html")):
        print("ERROR: src/index.html not found.", file=sys.stderr); sys.exit(1)

    load_config()                          # seed data/config.json on first run
    Handler.PORT = args.port

    class Server(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    port = args.port
    for _ in range(20):
        try:
            httpd = Server(("0.0.0.0", port), Handler); break
        except OSError:
            port += 1
    else:
        print("ERROR: could not bind a port.", file=sys.stderr); sys.exit(1)
    Handler.PORT = port

    ip = lan_ip()
    print("=" * 60)
    print("  VCF Camera Wall is running.")
    print("  Wall:   http://localhost:%d/" % port)
    print("  Admin:  http://%s:%d/admin" % (ip, port))
    print("=" * 60)
    if args.open:
        try: webbrowser.open("http://localhost:%d/" % port)
        except Exception: pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
