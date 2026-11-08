from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from content_qa.review import run_review
from content_qa.splitter import chunk_page, pair_pages, split_notes, split_slides

SLIDES = """# Slide 1

The shell is a program launcher.

---

# Slide 2

A pipe connects stdout to stdin.
"""

NOTES = """### Slide 1: Shell

- 时长预算：60 秒
- 动画切入：无
- 技术核查：shell 是解释器
- 逐字口播：shell 启动程序。

### Slide 2: Pipes

- 时长预算：60 秒
- 动画切入：无
- 技术核查：管道连接 stdout 与 stdin
- 逐字口播：管道把输出接到输入。
"""


class _Handler(BaseHTTPRequestHandler):
    mode = "ok"
    requests = 0

    def log_message(self, *_args):
        pass

    def do_POST(self):
        type(self).requests += 1
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        if self.mode == "slow":
            time.sleep(2)
        if self.mode == "error" or (self.mode == "flaky" and type(self).requests > 1):
            body = json.dumps({"error": "boom"}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.mode == "invalid":
            content = "this is not json"
        else:
            content = json.dumps(
                {
                    "findings": [
                        {
                            "slide": 1,
                            "claim": "shell 是程序启动器",
                            "verdict": "needs_human_review",
                            "rationale": "no source",
                            "source_refs": [],
                        }
                    ]
                }
            )
        body = json.dumps(
            {"choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": {}}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve(mode: str):
    handler = type("Handler", (_Handler,), {"mode": mode, "requests": 0})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, handler


class SplitterTest(unittest.TestCase):
    def test_slide_and_notes_pairing(self):
        slides = split_slides(SLIDES)
        self.assertEqual(len(slides), 2)
        notes = split_notes(NOTES)
        self.assertEqual(sorted(notes), [1, 2])
        pages = pair_pages(SLIDES, NOTES)
        self.assertEqual([page.slide for page in pages], [1, 2])
        self.assertIn("pipe", pages[1].slide_text)

    def test_long_notes_are_chunked(self):
        page = pair_pages(SLIDES, NOTES)[0]
        page.notes_text = "\n\n".join(["段落" * 100] * 20)
        chunks = chunk_page(page, max_chars=500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk.slide == 1 for chunk in chunks))


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lesson_dir = self.root / "lessons" / "test-lesson"
        self.lesson_dir.mkdir(parents=True)
        (self.lesson_dir / "slides.md").write_text(SLIDES, encoding="utf-8")
        (self.lesson_dir / "lecture_notes.md").write_text(NOTES, encoding="utf-8")
        self.config_dir = self.root / "config"
        self.config_dir.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def _write_config(self, base_url: str = "http://127.0.0.1:9/v1", limit: int = 16384, timeout: int = 10):
        import yaml

        payload = {
            "schema_version": 1,
            "backend": "api",
            "model": {
                "base_url": base_url,
                "model": "test-model",
                "api_key_env": "CONTENT_QA_API_KEY",
                "timeout_s": timeout,
                "max_tokens": 512,
                "retries": 0,
            },
            "context_limit": limit,
        }
        (self.config_dir / "content-qa.yaml").write_text(
            yaml.safe_dump(payload), encoding="utf-8"
        )

    def test_blocked_without_config(self):
        report, path = run_review(
            self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
        )
        self.assertEqual(report.status, "blocked")
        self.assertTrue(path.is_file())
        self.assertIn("not configured", report.errors[0])

    def test_blocked_without_credentials(self):
        self._write_config()
        os.environ.pop("CONTENT_QA_API_KEY", None)
        report, _ = run_review(
            self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
        )
        self.assertEqual(report.status, "blocked")
        self.assertIn("CONTENT_QA_API_KEY", report.errors[0])

    def test_completed_with_mock_model(self):
        server, handler = _serve("ok")
        try:
            self._write_config(f"http://127.0.0.1:{server.server_port}/v1")
            os.environ["CONTENT_QA_API_KEY"] = "test-key"
            before = {
                name: (self.lesson_dir / name).read_bytes()
                for name in ("slides.md", "lecture_notes.md")
            }
            report, path = run_review(
                self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
            )
            self.assertEqual(report.status, "completed", report.errors)
            after = {
                name: (self.lesson_dir / name).read_bytes()
                for name in ("slides.md", "lecture_notes.md")
            }
            self.assertEqual(before, after, "ContentQA must not modify lesson content")
            self.assertFalse((self.root / "build" / "test-lesson" / "shots.json").exists())
            self.assertFalse(
                (self.root / "build" / "test-lesson" / "final" / "build-report.json").exists()
            )
            self.assertEqual(len(report.findings), 2)
            self.assertEqual(len(report.tasks), 2)
            self.assertTrue(path.is_file())
            self.assertTrue((self.root / "build" / "test-lesson" / "review" / "review.md").is_file())
            self.assertEqual(handler.requests, 2)
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key in ("schema_version", "lesson", "generated_at", "model", "base_url", "status", "tasks", "findings", "errors"):
                self.assertIn(key, payload)
            self.assertEqual(payload["lesson"], "test-lesson")
            self.assertEqual(len(payload["tasks"]), 2)
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("CONTENT_QA_API_KEY", None)

    def test_invalid_json_marks_run_failed(self):
        server, handler = _serve("invalid")
        try:
            self._write_config(f"http://127.0.0.1:{server.server_port}/v1")
            os.environ["CONTENT_QA_API_KEY"] = "test-key"
            report, _ = run_review(
                self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
            )
            self.assertEqual(report.status, "failed")
            self.assertTrue(all(task.status == "failed" for task in report.tasks))
            raw = self.root / "build" / "test-lesson" / "review" / "raw"
            self.assertTrue(any(raw.glob("*.txt")))
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("CONTENT_QA_API_KEY", None)

    def test_context_overflow_fails_without_calling_model(self):
        (self.lesson_dir / "slides.md").write_text(
            "# Big\n\n" + "字" * 5000, encoding="utf-8"
        )
        (self.lesson_dir / "lecture_notes.md").write_text(
            "### Slide 1: Big\n\n- 时长预算：60 秒\n", encoding="utf-8"
        )
        server, handler = _serve("ok")
        try:
            self._write_config(f"http://127.0.0.1:{server.server_port}/v1", limit=2048)
            os.environ["CONTENT_QA_API_KEY"] = "test-key"
            report, _ = run_review(
                self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
            )
            self.assertEqual(report.status, "failed")
            self.assertIn("context budget exceeded", report.errors[0])
            self.assertEqual(handler.requests, 0)
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("CONTENT_QA_API_KEY", None)

    def test_server_error_marks_run_failed(self):
        server, handler = _serve("error")
        try:
            self._write_config(f"http://127.0.0.1:{server.server_port}/v1")
            os.environ["CONTENT_QA_API_KEY"] = "test-key"
            report, _ = run_review(
                self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
            )
            self.assertEqual(report.status, "failed")
            self.assertIn("500", report.errors[0])
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("CONTENT_QA_API_KEY", None)

    def test_mid_run_failure_keeps_earlier_findings(self):
        server, handler = _serve("flaky")
        try:
            self._write_config(f"http://127.0.0.1:{server.server_port}/v1")
            os.environ["CONTENT_QA_API_KEY"] = "test-key"
            report, path = run_review(
                self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
            )
            self.assertEqual(report.status, "failed")
            self.assertEqual([task.status for task in report.tasks], ["completed", "failed"])
            self.assertEqual(len(report.findings), 1)
            self.assertEqual(handler.requests, 2)
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key in ("schema_version", "lesson", "generated_at", "model", "base_url", "status", "tasks", "findings", "errors"):
                self.assertIn(key, payload)
            self.assertEqual(payload["lesson"], "test-lesson")
            self.assertEqual(len(payload["tasks"]), 2)
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("CONTENT_QA_API_KEY", None)

    def test_timeout_marks_run_failed(self):
        server, handler = _serve("slow")
        try:
            self._write_config(
                f"http://127.0.0.1:{server.server_port}/v1", timeout=1
            )
            os.environ["CONTENT_QA_API_KEY"] = "test-key"
            report, _ = run_review(
                self.root, self.lesson_dir, config_path=self.config_dir / "content-qa.yaml"
            )
            self.assertEqual(report.status, "failed")
            self.assertTrue(all(task.status == "failed" for task in report.tasks))
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("CONTENT_QA_API_KEY", None)


if __name__ == "__main__":
    unittest.main()
