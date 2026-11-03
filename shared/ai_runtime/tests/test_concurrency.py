from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
SRC = WORKSPACE / "shared" / "ai_runtime" / "src"

WORKER = """
import json, sys, time
from pathlib import Path
from ai_runtime.locks import FileLock

lock_path, out_path, name = sys.argv[1:4]
with FileLock(Path(lock_path), task_id=name, timeout_s=20, poll_s=0.02):
    with open(out_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"name": name, "event": "start", "t": time.time()}) + "\\n")
    time.sleep(0.4)
    with open(out_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"name": name, "event": "end", "t": time.time()}) + "\\n")
"""


class MultiProcessLockTest(unittest.TestCase):
    """FR-09: two processes must never hold the local-model lock at once."""

    def test_two_processes_are_serialized(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock_path = root / "model.lock"
            events_path = root / "events.jsonl"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")

            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", WORKER, str(lock_path), str(events_path), name],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for name in ("first", "second")
            ]
            for process in processes:
                stdout, stderr = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 0, f"{stdout}\n{stderr}")

            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(events), 4, events)
            by_name = {}
            for event in events:
                by_name.setdefault(event["name"], {})[event["event"]] = event["t"]
            first, second = by_name["first"], by_name["second"]
            ordered = sorted([first, second], key=lambda item: item["start"])
            self.assertLessEqual(ordered[0]["end"], ordered[1]["start"] + 0.05)


if __name__ == "__main__":
    unittest.main()
