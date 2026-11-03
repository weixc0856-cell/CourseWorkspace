from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

from modeling_studio.validator import _glb_summary


def write_glb(path: Path, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    padded = data + b" " * ((4 - len(data) % 4) % 4)
    total = 12 + 8 + len(padded)
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<II", len(padded), 0x4E4F534A)
        + padded
    )


class GlbCheckTest(unittest.TestCase):
    def test_valid_glb(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.glb"
            write_glb(path, {"meshes": [{"primitives": []}], "nodes": [{}]})
            ok, detail = _glb_summary(path)
        self.assertTrue(ok, detail)
        self.assertIn("1 meshes", detail)

    def test_garbage_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.glb"
            path.write_bytes(b"not a glb")
            ok, _ = _glb_summary(path)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
