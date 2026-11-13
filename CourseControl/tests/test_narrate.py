from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from course_control.voice.narrate import (
    TtsService,
    segment_cache_key,
    synthesize,
)

WAV_BYTES = b"RIFF" + b"\x00" * 40 + b"WAVEfmt " + b"\x00" * 60


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test output
        return

    def do_GET(self):
        if self.path == "/health":
            payload = json.dumps(
                {"status": "ready", "model": "VoxCPM2", "sample_rate": 48000}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path != "/tts":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(WAV_BYTES)))
        self.send_header("X-Audio-Seconds", "1.25")
        self.send_header("X-Synth-Seconds", "4.5")
        self.send_header("X-Sample-Rate", "48000")
        self.send_header("X-Prompt-Mode", "prompt_reference")
        self.end_headers()
        self.wfile.write(WAV_BYTES)


class NarrationTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.voice = self.root / "voice.wav"
        self.voice.write_bytes(b"voice")

    def tearDown(self):
        try:
            self.server.shutdown()
        except KeyboardInterrupt:
            # The hosted Windows runner delivers a real console Ctrl-C into the
            # test process while the suite runs.  The test body has already
            # finished, so a signal landing inside shutdown must not fail it.
            pass
        self.server.server_close()
        self.temp.cleanup()

    def test_synthesize_parses_headers(self):
        output = self.root / "segment.wav"
        details = synthesize(
            f"http://127.0.0.1:{self.port}",
            "测试",
            self.voice,
            "参考",
            output,
        )
        self.assertTrue(output.is_file())
        self.assertEqual(details["audio_seconds"], 1.25)
        self.assertEqual(details["sample_rate"], 48000)
        self.assertEqual(details["prompt_mode"], "prompt_reference")

    def test_cache_key_is_stable_and_text_sensitive(self):
        first = segment_cache_key("你好", self.voice, "参考")
        second = segment_cache_key("你好", self.voice, "参考")
        third = segment_cache_key("你好。", self.voice, "参考")
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_service_reuses_running_instance(self):
        workspace = self.root
        (workspace / "runtime" / "locks").mkdir(parents=True)
        with TtsService(
            workspace,
            ai_root=self.root,
            runtime_dir=self.root,
            log_path=self.root / "tts.log",
            start_service=False,
            port=self.port,
        ) as service:
            self.assertEqual(service.mode, "reused")
            self.assertEqual(service.base_url, f"http://127.0.0.1:{self.port}")
        self.assertFalse((workspace / "runtime" / "locks" / f"tts-{self.port}.lock").exists())


if __name__ == "__main__":
    unittest.main()
