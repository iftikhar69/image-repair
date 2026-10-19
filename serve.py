"""Start the Campus Event Booking website on your own computer.

Usage:
    python serve.py            # http://127.0.0.1:8000
    python serve.py 8001       # use another port if 8000 is busy

Press Ctrl+C in the terminal to stop the server.

Why not just `python -m http.server`? This script does the same job, but
  * it only listens on your own computer (127.0.0.1), so Windows does not
    show a firewall pop-up and nobody else on the network can reach it, and
  * it states the file types explicitly, so the page looks the same on every
    computer (some Windows machines map .css/.js to the wrong type).
"""
import functools
import http.server
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent / "app"
HOST = "127.0.0.1"


class AppHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the files in the app/ folder."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
    }


def make_server(port=8000, handler_class=AppHandler):
    """Create (but do not start) the web server. port=0 means 'any free port'."""
    handler = functools.partial(handler_class, directory=str(APP_DIR))
    return http.server.ThreadingHTTPServer((HOST, port), handler)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    try:
        server = make_server(port)
    except OSError as error:
        sys.exit(f"Could not start on port {port}: {error}\nTry another port, e.g.  python serve.py {port + 1}")
    print(f"Campus Event Booking is running at http://127.0.0.1:{port}")
    print("Open that address in your browser. If localhost does not load, keep using 127.0.0.1.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
