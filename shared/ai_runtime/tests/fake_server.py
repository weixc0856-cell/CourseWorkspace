"""Minimal OpenAI/llama.cpp-compatible server used by lifecycle tests.

Started as a subprocess with an arbitrary port and alias; never touches the real
llama-server or port 8080.
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--unhealthy", action="store_true")
    parser.add_argument("--startup-delay", type=float, default=0.0)
    args = parser.parse_args()

    if args.startup_delay:
        time.sleep(args.startup_delay)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            if self.path == "/health":
                if args.unhealthy:
                    self.send_response(503)
                    self.end_headers()
                    return
                self._json({"status": "ok"})
            elif self.path == "/v1/models":
                self._json({"data": [{"id": args.alias}]})
            else:
                self.send_error(404)

        def _json(self, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
