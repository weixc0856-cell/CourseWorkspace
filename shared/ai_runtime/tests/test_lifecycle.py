from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from ai_runtime.locks import FileLock
from ai_runtime.service import (
    ModelSpec,
    ServerConfig,
    ServerStartError,
    is_healthy,
    model_service,
    port_in_use,
)

FAKE = Path(__file__).with_name("fake_server.py")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_healthy(server: ServerConfig, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_healthy(server, timeout=0.5):
            return True
        time.sleep(0.1)
    return False


class LifecycleTest(unittest.TestCase):
    """FR-09: service start, stop, reuse and switching with a fake server."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lock_path = self.root / "model.lock"
        self.log_path = self.root / "server.log"

    def tearDown(self):
        self.temp.cleanup()

    def _config(self, port: int, startup_timeout: int = 10) -> ServerConfig:
        return ServerConfig(
            executable=sys.executable,
            port=port,
            startup_timeout_s=startup_timeout,
            stop_timeout_s=3,
        )

    def _model(self, port: int, alias: str, *extra: str) -> ModelSpec:
        return ModelSpec(
            key=alias,
            alias=alias,
            args=[str(FAKE), "--port", str(port), "--alias", alias, *extra],
            context=4096,
        )

    def test_start_and_stop_owns_the_service(self):
        port = free_port()
        server = self._config(port)
        lock = FileLock(self.lock_path, task_id="start", timeout_s=5)
        with model_service(server, self._model(port, "fake-a"), lock, self.log_path) as mode:
            self.assertEqual(mode, "started")
            self.assertTrue(is_healthy(server))
        self.assertFalse(port_in_use(server), "server must be stopped on exit")
        self.assertFalse(self.lock_path.exists(), "lock must be released")

    def test_switch_models_between_stages(self):
        port = free_port()
        server = self._config(port)
        lock_a = FileLock(self.lock_path, task_id="a", timeout_s=5)
        with model_service(server, self._model(port, "alpha"), lock_a, self.log_path) as mode:
            self.assertEqual(mode, "started")
            self.assertEqual(server.port, port)
        self.assertFalse(port_in_use(server))
        lock_b = FileLock(self.lock_path, task_id="b", timeout_s=5)
        with model_service(server, self._model(port, "beta"), lock_b, self.log_path) as mode:
            self.assertEqual(mode, "started")
        self.assertFalse(port_in_use(server))

    def test_foreign_server_is_reused_and_not_stopped(self):
        port = free_port()
        server = self._config(port)
        process = subprocess.Popen(
            [sys.executable, str(FAKE), "--port", str(port), "--alias", "foreign"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            self.assertTrue(wait_healthy(server), "fake server did not start")
            lock = FileLock(self.lock_path, task_id="reuse", timeout_s=5)
            with model_service(server, self._model(port, "foreign"), lock, self.log_path) as mode:
                self.assertEqual(mode, "reused")
            self.assertIsNone(process.poll(), "foreign server must keep running")
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def test_start_timeout_releases_lock(self):
        port = free_port()
        server = self._config(port, startup_timeout=2)
        lock = FileLock(self.lock_path, task_id="timeout", timeout_s=5)
        with self.assertRaises(ServerStartError):
            with model_service(
                server,
                self._model(port, "unhealthy", "--unhealthy"),
                lock,
                self.log_path,
            ):
                pass
        self.assertFalse(self.lock_path.exists(), "lock must be released after timeout")
        self.assertFalse(port_in_use(server), "failed server must not be left running")


if __name__ == "__main__":
    unittest.main()
