"""A small localhost HTTP server that carries the UI and its data.

pywebview's JavaScript bridge starts a fresh OS thread for every call and
answers it with a blocking evaluate_js. Called on a timer that buries the
process in threads; called to close the window it waits forever, because the
reply is evaluated in a webview that destroy() has already torn down. So the
bridge carries nothing: every interaction travels over this server instead.
Window dragging is the one exception, and pywebview handles that internally
without going near the bridge's threading.
"""
from __future__ import annotations

import json
import secrets
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Methods the page is allowed to POST. Anything absent here is unreachable.
ACTIONS = {
    "add_urls", "save_settings", "cancel", "cancel_all", "clear_finished",
    "retry", "read_clipboard", "install_ffmpeg", "open_path", "reveal",
    "choose_folder", "win_close", "win_minimize", "win_zoom", "win_resize",
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class _Handler(BaseHTTPRequestHandler):
    # Keep-alive matters: without it every poll would open a new connection
    # and ThreadingHTTPServer would spawn a thread for each one.
    protocol_version = "HTTP/1.1"
    server_version = "KitchenSink"

    def __init__(self, api, web_dir: Path, token: str, *args, **kwargs):
        self.api = api
        self.web_dir = web_dir
        self.token = token
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):
        pass  # the app keeps its own log

    # ---------------------------------------------------------------- replies
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def _json(self, payload, code: int = 200):
        self._send(code, json.dumps(payload).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _authorised(self) -> bool:
        """A custom header forces a CORS preflight, which is never answered.
        That keeps a web page in the user's browser from driving the app."""
        return self.headers.get("X-KS-Token") == self.token

    # ------------------------------------------------------------------ verbs
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            if not self._authorised():
                return self._json({"error": "forbidden"}, 403)
            if path == "/api/state":
                return self._json(self.api.get_state())
            if path == "/api/poll":
                return self._json(self.api.poll())
            return self._json({"error": "not found"}, 404)
        return self._static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        if not self._authorised():
            return self._json({"error": "forbidden"}, 403)

        name = path[len("/api/"):]
        if name not in ACTIONS:
            return self._json({"ok": False, "error": f"unknown action {name}"}, 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}
        try:
            return self._json({"ok": True, "result": getattr(self.api, name)(**body)})
        except Exception as exc:
            return self._json({"ok": False, "error": str(exc)}, 500)

    # ----------------------------------------------------------------- static
    def _static(self, path: str):
        rel = path.lstrip("/") or "index.html"
        target = (self.web_dir / rel).resolve()
        try:
            target.relative_to(self.web_dir.resolve())
        except ValueError:
            return self._json({"error": "forbidden"}, 403)
        if not target.is_file():
            return self._json({"error": "not found"}, 404)

        data = target.read_bytes()
        ctype = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        if target.name == "index.html":
            data = data.replace(b"__KS_TOKEN__", self.token.encode("ascii"))
        self._send(200, data, ctype)


def start(api, web_dir: Path) -> str:
    """Serve the interface on a free loopback port. Returns its URL."""
    token = secrets.token_urlsafe(24)
    handler = partial(_Handler, api, Path(web_dir), token)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True,
                     name="ks-http").start()
    return f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
