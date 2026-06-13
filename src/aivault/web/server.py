"""Thin stdlib HTTP transport for the web frontend (ARCHITECTURE §12a).

Routes ``/api/*`` to the pure functions in ``api.py`` and serves the static
SPA. A fresh ``Vault`` (SQLite connection) is opened per request so the
threading server stays thread-safe. Bound to 127.0.0.1 by default.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..config import VaultConfig
from ..service import Vault
from . import api

STATIC_DIR = Path(__file__).parent / "static"
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def _make_handler(vault_root: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AIVault/0.4"

        def log_message(self, *args):  # quiet by default
            pass

        # -- helpers --
        def _send_json(self, payload, code: int = 200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, rel: str):
            if rel in ("", "/"):
                rel = "index.html"
            target = (STATIC_DIR / rel).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                self.send_error(404, "Not found")
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type", _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # -- routing --
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if not path.startswith("/api/"):
                self._send_static(path.lstrip("/"))
                return

            qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            cfg = VaultConfig.load(vault_root)
            vault = Vault(cfg)
            try:
                if path == "/api/stats":
                    self._send_json(api.stats(vault))
                elif path == "/api/projects":
                    self._send_json(api.projects(vault))
                elif path == "/api/sessions":
                    self._send_json(
                        api.list_sessions(
                            vault,
                            group=qs.get("group", "project"),
                            q=qs.get("q"),
                            source=qs.get("source"),
                            project=qs.get("project"),
                            status=qs.get("status"),
                            os_context=qs.get("os"),
                            limit=int(qs.get("limit", 500)),
                        )
                    )
                elif path.startswith("/api/session/"):
                    sid = path[len("/api/session/"):]
                    detail = api.session_detail(vault, sid)
                    if detail is None:
                        self._send_json({"error": "not found"}, 404)
                    else:
                        self._send_json(detail)
                else:
                    self._send_json({"error": "unknown endpoint"}, 404)
            except Exception as exc:  # never crash the dev server on one bad request
                self._send_json({"error": str(exc)}, 500)
            finally:
                vault.close()

    return Handler


def run(vault_root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    # validate vault up front for a clear error
    VaultConfig.load(vault_root)
    httpd = ThreadingHTTPServer((host, port), _make_handler(vault_root))
    url = f"http://{host}:{port}/"
    print(f"AIVault web UI serving {vault_root}\n  -> {url}\n(Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()
