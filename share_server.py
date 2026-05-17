"""Tiny one-shot LAN HTTP server for handing a single GIF to a phone via QR code.

Usage:
    session = serve_file(Path("dog_dancing.gif"))
    print(session.url)       # http://192.168.1.42:5173/<token>/dog_dancing.gif
    session.stop()           # idempotent; also auto-stops after timeout
"""

from __future__ import annotations

import secrets
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote


def detect_lan_ip() -> str:
    """Pick the active outbound interface IP. Works around Windows quirks
    where socket.gethostbyname returns 127.0.0.1 or a stale virtual adapter."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


@dataclass
class ShareSession:
    url: str
    _server: ThreadingHTTPServer
    _thread: threading.Thread
    _stopped: threading.Event

    def stop(self) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception:
            pass


def serve_file(file_path: Path, port: int = 0, auto_stop_seconds: int = 600) -> ShareSession:
    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    token = secrets.token_urlsafe(8)
    expected_path = f"/{token}/{quote(file_path.name)}"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if unquote(self.path) != unquote(expected_path):
                self.send_error(404)
                return
            try:
                data = file_path.read_bytes()
            except OSError:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{file_path.name}"',
            )
            self.end_headers()
            try:
                self.wfile.write(data)
            except (ConnectionResetError, BrokenPipeError):
                pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    bound_port = server.server_address[1]
    ip = detect_lan_ip()
    url = f"http://{ip}:{bound_port}{expected_path}"

    stopped = threading.Event()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    session = ShareSession(url=url, _server=server, _thread=thread, _stopped=stopped)

    if auto_stop_seconds > 0:
        threading.Timer(auto_stop_seconds, session.stop).start()

    return session
