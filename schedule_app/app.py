from __future__ import annotations

import json
import mimetypes
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
AGENDA_PATH = PROJECT_ROOT / "agenda.json"
DEFAULT_PORT = 8000


class ScheduleAppHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/agenda":
            self._handle_agenda_api()
            return
        if parsed.path in {"/api/health", "/health"}:
            self._handle_health_api()
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _handle_health_api(self) -> None:
        payload = {"ok": True}
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(json.dumps(payload).encode("utf-8"))))
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _handle_agenda_api(self) -> None:
        if AGENDA_PATH.exists():
            try:
                agenda = json.loads(AGENDA_PATH.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": f"Failed to read agenda.json: {exc}"},
                )
                return
        else:
            agenda = []

        if not isinstance(agenda, list):
            agenda = []

        self._send_json(
            HTTPStatus.OK,
            {
                "source": str(AGENDA_PATH),
                "count": len(agenda),
                "agenda": agenda,
            },
        )

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    handler = partial(ScheduleAppHandler, directory=str(APP_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", DEFAULT_PORT), handler)
    print(f"Schedule app running at http://127.0.0.1:{DEFAULT_PORT}")
    print(f"Reading agenda data from {AGENDA_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping schedule app...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
