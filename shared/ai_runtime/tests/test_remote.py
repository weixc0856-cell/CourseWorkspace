from __future__ import annotations

import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ai_runtime.locks import FileLock
from ai_runtime.remote import (
    RemoteAuthError,
    RemoteConfig,
    RemoteUnavailable,
    chat_completion,
    health,
)
from ai_runtime.routing import route_model
from ai_runtime.service import ModelSpec, ServerBusy, ServerConfig
from ai_runtime.tasks import TaskRecord


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _MockHandler(BaseHTTPRequestHandler):
    alias = "local-alias"
    expected_key = "test-key"
    fail_status = 0

    def log_message(self, *_args):
        pass

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json({"status": "ok"})
        elif self.path == "/v1/models":
            self._json({"data": [{"id": self.alias}]})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.fail_status:
            self._json({"error": "boom"}, status=self.fail_status)
            return
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {self.expected_key}":
            self._json({"error": "unauthorized"}, status=401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        self._json(
            {
                "model": payload.get("model", self.alias),
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "remote-ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            }
        )


def serve(alias="local-alias", expected_key="test-key", fail_status=0):
    handler = type(
        "Handler",
        (_MockHandler,),
        {"alias": alias, "expected_key": expected_key, "fail_status": fail_status},
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def remote_config(port: int, **overrides) -> RemoteConfig:
    values = dict(
        enabled=True,
        provider="deepseek",
        base_url=f"http://127.0.0.1:{port}/v1",
        model="remote-model",
        api_key="test-key",
        trust_env=False,
        timeout_s=5,
        fallback_on=("busy", "start_error", "lock_timeout"),
    )
    values.update(overrides)
    return RemoteConfig(**values)


class RemoteProviderTest(unittest.TestCase):
    def setUp(self):
        self.httpd = serve()
        self.port = self.httpd.server_port

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_chat_completion_and_health(self):
        config = remote_config(self.port)
        result = chat_completion(
            config, [{"role": "user", "content": "hello"}], json_object=True
        )
        self.assertEqual(result.content, "remote-ok")
        self.assertEqual(result.model, "remote-model")
        self.assertEqual(result.usage["finish_reason"], "stop")
        payload = health(config)
        self.assertTrue(payload["reachable"])
        self.assertTrue(payload["key_present"])
        self.assertNotIn("test-key", json.dumps(payload))

    def test_missing_key_is_unavailable(self):
        config = remote_config(self.port, api_key=None, api_key_env="NO_SUCH_KEY")
        with self.assertRaises(RemoteUnavailable):
            chat_completion(config, [{"role": "user", "content": "x"}])
        self.assertFalse(config.available())

    def test_bad_key_is_auth_error(self):
        config = remote_config(self.port, api_key="wrong-key")
        with self.assertRaises(RemoteAuthError):
            chat_completion(config, [{"role": "user", "content": "x"}])

    def test_vision_without_vision_model_is_unavailable(self):
        config = remote_config(self.port)
        with self.assertRaises(RemoteUnavailable):
            chat_completion(config, [{"role": "user", "content": "x"}], vision=True)


class RoutingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lock = self.root / "model.lock"
        self.log = self.root / "server.log"
        self.remote = serve()
        self.local = serve(alias="other-alias")

    def tearDown(self):
        for httpd in (self.remote, self.local):
            httpd.shutdown()
            httpd.server_close()
        self.temp.cleanup()

    def _server(self, port: int) -> ServerConfig:
        return ServerConfig(
            executable=str(self.root / "missing-llama-server.exe"),
            port=port,
            startup_timeout_s=1,
            stop_timeout_s=1,
        )

    def _model(self, alias="wanted-alias") -> ModelSpec:
        return ModelSpec(key="planner", alias=alias)

    def test_local_route_is_preferred(self):
        local = serve(alias="wanted-alias")
        try:
            with route_model(
                self._server(local.server_port),
                self._model(),
                FileLock(self.lock, task_id="local", timeout_s=2),
                self.log,
                remote=remote_config(self.remote.server_port),
            ) as route:
                self.assertEqual(route.provider, "local")
                self.assertEqual(route.model, "wanted-alias")
                self.assertEqual(route.mode, "reused")
        finally:
            local.shutdown()
            local.server_close()

    def test_busy_local_falls_back_to_remote(self):
        with route_model(
            self._server(self.local.server_port),
            self._model(),
            FileLock(self.lock, task_id="remote", timeout_s=2),
            self.log,
            remote=remote_config(self.remote.server_port),
        ) as route:
            self.assertEqual(route.provider, "remote")
            self.assertEqual(route.model, "remote-model")
            self.assertFalse(route.trust_env)
        self.assertFalse(self.lock.exists(), "local lock must be released")

    def test_busy_local_without_remote_raises(self):
        with self.assertRaises(ServerBusy):
            with route_model(
                self._server(self.local.server_port),
                self._model(),
                FileLock(self.lock, task_id="no-remote", timeout_s=2),
                self.log,
                remote=None,
            ):
                pass

    def test_vision_does_not_fall_back_to_text_remote(self):
        with self.assertRaises(ServerBusy):
            with route_model(
                self._server(self.local.server_port),
                self._model(),
                FileLock(self.lock, task_id="vision", timeout_s=2),
                self.log,
                remote=remote_config(self.remote.server_port),
                vision=True,
            ):
                pass


class TaskProviderTest(unittest.TestCase):
    def test_provider_defaults_to_local(self):
        record = TaskRecord(task_id="t", task_type="x", assigned_model="m")
        self.assertEqual(record.provider, "local")
        self.assertEqual(TaskRecord.from_dict(record.as_dict()).provider, "local")

    def test_remote_provider_is_persisted(self):
        record = TaskRecord(
            task_id="t2", task_type="x", assigned_model="remote-model", provider="remote"
        )
        self.assertEqual(TaskRecord.from_dict(record.as_dict()).provider, "remote")

    def test_unknown_provider_rejected(self):
        with self.assertRaises(ValueError):
            TaskRecord(
                task_id="t3", task_type="x", assigned_model="m", provider="cloud"
            )


if __name__ == "__main__":
    unittest.main()
