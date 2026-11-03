from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ai_runtime.locks import FileLock
from ai_runtime.service import (
    ModelSpec,
    ServerBusy,
    ServerConfig,
    ServerStartError,
    model_service,
)


class _Handler(BaseHTTPRequestHandler):
    alias = "test-alias"
    healthy = True

    def log_message(self, *_args):  # silence test output
        pass

    def do_GET(self):
        if self.path == "/health" and self.healthy:
            self._json({"status": "ok"})
        elif self.path == "/v1/models":
            self._json({"data": [{"id": self.alias}]})
        else:
            self.send_error(404)

    def _json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(alias: str, healthy: bool = True):
    handler = type("Handler", (_Handler,), {"alias": alias, "healthy": healthy})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class ModelServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lock_path = Path(self.temp.name) / "llama.lock"
        self.log_path = Path(self.temp.name) / "server.log"

    def tearDown(self):
        self.temp.cleanup()

    def _server(self, port: int) -> ServerConfig:
        return ServerConfig(
            executable=str(Path(self.temp.name) / "missing-llama-server.exe"),
            host="127.0.0.1",
            port=port,
            startup_timeout_s=2,
            stop_timeout_s=2,
        )

    def test_reuses_healthy_matching_server(self):
        httpd = _serve("test-alias")
        try:
            server = self._server(httpd.server_port)
            model = ModelSpec(key="planner", alias="test-alias")
            lock = FileLock(self.lock_path, task_id="t", timeout_s=2)
            with model_service(server, model, lock, self.log_path) as mode:
                self.assertEqual(mode, "reused")
            self.assertFalse(self.lock_path.exists(), "lock must be released")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_refuses_foreign_model(self):
        httpd = _serve("other-alias")
        try:
            server = self._server(httpd.server_port)
            model = ModelSpec(key="planner", alias="test-alias")
            lock = FileLock(self.lock_path, task_id="t", timeout_s=2)
            with self.assertRaises(ServerBusy):
                with model_service(server, model, lock, self.log_path):
                    pass
            self.assertFalse(self.lock_path.exists(), "lock must be released after refusal")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_releases_lock_when_start_fails(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        server = self._server(port)
        model = ModelSpec(key="planner", alias="test-alias")
        lock = FileLock(self.lock_path, task_id="t", timeout_s=2)
        with self.assertRaises(ServerStartError):
            with model_service(server, model, lock, self.log_path):
                pass
        self.assertFalse(self.lock_path.exists(), "lock must be released on start failure")

    def test_unhealthy_port_is_busy(self):
        httpd = _serve("test-alias", healthy=False)
        try:
            server = self._server(httpd.server_port)
            server.startup_timeout_s = 1
            model = ModelSpec(key="planner", alias="test-alias")
            lock = FileLock(self.lock_path, task_id="t", timeout_s=2)
            with self.assertRaises(ServerBusy):
                with model_service(server, model, lock, self.log_path):
                    pass
            self.assertFalse(self.lock_path.exists())
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
