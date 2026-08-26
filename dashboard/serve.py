#!/usr/bin/env python3
"""
Local live dashboard: serves HTML and /api/data from personal Jira (.env).

  source .venv/bin/activate
  python dashboard/serve.py

Open http://127.0.0.1:8765/ — auto-refreshes from Jira. Does not push to git.
Credentials stay on this machine only (never sent to the browser).
"""

from __future__ import annotations

import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DASH = Path(__file__).resolve().parent
ROOT = DASH.parent
sys.path.insert(0, str(DASH))

from build import build_payload, fetch, render  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765
REFRESH_MS = 60_000
CACHE_SECONDS = 20

_lock = threading.Lock()
_cache: dict = {"payload": None, "ts": 0.0, "error": None}


def get_payload(*, force: bool = False) -> dict:
    now = time.time()
    with _lock:
        if (
            not force
            and _cache["payload"] is not None
            and now - _cache["ts"] < CACHE_SECONDS
        ):
            return _cache["payload"]
    try:
        payload = build_payload(fetch())
        with _lock:
            _cache["payload"] = payload
            _cache["ts"] = time.time()
            _cache["error"] = None
        return payload
    except Exception as exc:  # noqa: BLE001 — surface to HTTP client
        with _lock:
            _cache["error"] = str(exc)
        if _cache["payload"] is not None:
            return _cache["payload"]
        raise


def live_shell_html() -> str:
    template = (DASH / "index.template.html").read_text()
    # Placeholder so static parse still works if JS falls back
    empty = {
        "site": "",
        "generated": "…",
        "overall": {
            "total": 0,
            "done": 0,
            "ip": 0,
            "todo": 0,
            "pct": 0,
            "pct_w": 0,
            "epics": 0,
            "epics_with_work": 0,
        },
        "epics": [],
        "assignees": [],
    }
    html = render(empty, template)
    inject = (
        f"<script>window.DASHBOARD_LIVE=true;"
        f"window.DASHBOARD_REFRESH_MS={REFRESH_MS};</script>\n"
    )
    return html.replace("<head>", "<head>\n  " + inject, 1)


class Handler(BaseHTTPRequestHandler):
    server_version = "VainerHomeDashboard/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = live_shell_html().encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return
        if path == "/api/data":
            force = "refresh=1" in (urlparse(self.path).query or "")
            try:
                payload = get_payload(force=force)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
            except Exception as exc:  # noqa: BLE001
                err = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self._send(502, err, "application/json; charset=utf-8")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")


def main() -> None:
    # Warm cache once so first paint is fast
    print("Fetching Jira (initial)…", flush=True)
    try:
        payload = get_payload(force=True)
        print(
            f"OK · {payload['overall']['pct']}% done "
            f"({payload['overall']['done']}/{payload['overall']['total']})",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Initial fetch failed: {exc}", flush=True)
        print("Server will still start; fix .env and hit Refresh.", flush=True)

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Live dashboard: {url}", flush=True)
    print(f"Auto-refresh every {REFRESH_MS // 1000}s · Ctrl+C to stop", flush=True)
    print("(Not pushing to GitHub — local only)", flush=True)
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    main()
