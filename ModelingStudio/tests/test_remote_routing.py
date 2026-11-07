from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from ai_runtime import ModelRoute

from modeling_studio.config import RemoteSettings
from modeling_studio.llm import LLMClient


class _Handler(BaseHTTPRequestHandler):
    expected_key = "test-key"
    seen_model = ""

    def log_message(self, *_args):
        pass

    def do_POST(self):
        if self.headers.get("Authorization") != f"Bearer {self.expected_key}":
            self.send_error(401)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        type(self).seen_model = payload.get("model", "")
        body = json.dumps(
            {
                "model": payload.get("model"),
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _FakeModel:
    alias = "local-alias"


class _FakeConfig:
    llm = SimpleNamespace(
        base_url="http://127.0.0.1:9/v1",
        api_key="sk-local",
        request_timeout_s=5,
        max_retries=0,
    )

    def model(self, key):
        return _FakeModel()

    def budget_for(self, stage):
        return None


class RemoteRouteTest(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_llm_client_uses_remote_route_model_and_key(self):
        route = ModelRoute(
            provider="remote",
            base_url=f"http://127.0.0.1:{self.httpd.server_port}/v1",
            api_key="test-key",
            model="remote-model",
            mode="remote",
            trust_env=False,
        )
        client = LLMClient(_FakeConfig())
        content, usage = client.chat(
            [{"role": "user", "content": "hi"}], "planner", route=route
        )
        self.assertEqual(content, "ok")
        self.assertEqual(usage["finish_reason"], "stop")
        self.assertEqual(_Handler.seen_model, "remote-model")

    def test_remote_settings_convert_to_runtime_config(self):
        settings = RemoteSettings(
            enabled=True,
            model="deepseek-chat",
            api_key_env="NO_SUCH_KEY",
            fallback_on=["busy", "start_error"],
        )
        runtime = settings.runtime()
        self.assertTrue(runtime.enabled)
        self.assertEqual(runtime.model, "deepseek-chat")
        self.assertEqual(runtime.fallback_on, ("busy", "start_error"))


if __name__ == "__main__":
    unittest.main()
