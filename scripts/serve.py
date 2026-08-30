#!/usr/bin/env python3
"""
Tiny zero-dependency static server for the VCF Camera Wall.

Serves the src/ folder on http://localhost:<port>/ so the app runs from a real
http origin (avoids the occasional browser restriction on file:// pages loading
http camera images, and serves config.js cleanly).

Usage:
    python3 serve.py [--port 8770] [--open]

Only stdlib is used, so it runs on any Mac/Linux/Windows with Python 3.
"""
import argparse, os, sys, http.server, socketserver, webbrowser, functools

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.normpath(os.path.join(here, "..", "src"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--open", action="store_true", help="open the default browser")
    args = ap.parse_args()

    if not os.path.isfile(os.path.join(src, "index.html")):
        print("ERROR: src/index.html not found next to this script.", file=sys.stderr)
        sys.exit(1)

    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=src)

    class Reuse(socketserver.TCPServer):
        allow_reuse_address = True

    port = args.port
    for _ in range(20):                 # find a free port if the default is busy
        try:
            httpd = Reuse(("127.0.0.1", port), Handler)
            break
        except OSError:
            port += 1
    else:
        print("ERROR: could not bind a port.", file=sys.stderr); sys.exit(1)

    url = f"http://localhost:{port}/index.html"
    print("=" * 54)
    print("  VCF Camera Wall is running.")
    print(f"  Open:  {url}")
    print("  Stop:  Ctrl+C")
    print("=" * 54)
    if args.open:
        try: webbrowser.open(url)
        except Exception: pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
