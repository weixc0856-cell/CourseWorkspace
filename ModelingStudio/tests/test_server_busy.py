from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from modeling_studio.config import WorkflowConfig
from modeling_studio.server import ServerBusy, managed_server


class _OtherModel(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/health":
            payload = {"status": "ok"}
        elif self.path == "/v1/models":
            payload = {"data": [{"id": "someone-elses-model"}]}
        else:
            self.send_error(404)
            return
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class BusyServiceTest(unittest.TestCase):
    """FR-09: ModelingStudio must never stop another owner's server."""

    def test_other_model_on_port_is_busy(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), _OtherModel)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "llama-server.exe").write_bytes(b"")
                (root / "planner.gguf").write_bytes(b"")
                (root / "blender.exe").write_bytes(b"")
                config = WorkflowConfig.model_validate(
                    {
                        "schema_version": 1,
                        "server": {
                            "executable": str(root / "llama-server.exe"),
                            "port": httpd.server_port,
                        },
                        "models": {
                            "planner": {
                                "path": str(root / "planner.gguf"),
                                "alias": "planner-alias",
                            }
                        },
                        "blender": {"executable": str(root / "blender.exe")},
                        "runtime": {
                            "lock_path": str(root / "runtime" / "lock"),
                            "task_root": str(root / "runtime" / "tasks"),
                        },
                    }
                )
                with self.assertRaises(ServerBusy):
                    with managed_server(config, "planner", root / "server.log"):
                        pass
                self.assertFalse((root / "runtime" / "lock").exists())
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
