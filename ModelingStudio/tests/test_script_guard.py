from __future__ import annotations

import unittest

from modeling_studio.script_guard import ScriptRejected, extract_code, guard_script

GOOD = """
import bpy
import math

def build():
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = "cube"
"""


class ScriptGuardTest(unittest.TestCase):
    def test_accepts_minimal_script(self):
        guard_script(GOOD)

    def test_requires_build(self):
        with self.assertRaises(ScriptRejected):
            guard_script("import bpy\n")

    def test_rejects_os(self):
        with self.assertRaises(ScriptRejected):
            guard_script("import os\ndef build():\n    pass\n")

    def test_rejects_open(self):
        with self.assertRaises(ScriptRejected):
            guard_script("def build():\n    open('x')\n")

    def test_rejects_file_ops(self):
        with self.assertRaises(ScriptRejected):
            guard_script("import bpy\ndef build():\n    bpy.ops.wm.save_as_mainfile(filepath='x')\n")

    def test_rejects_getattr(self):
        with self.assertRaises(ScriptRejected):
            guard_script("def build():\n    getattr(object, 'x')\n")

    def test_extract_code(self):
        self.assertIn("def build", extract_code("text\n```python\n" + GOOD + "```\n"))


if __name__ == "__main__":
    unittest.main()


class FallbackScriptTest(unittest.TestCase):
    def test_fallback_passes_guard(self):
        from modeling_studio.contracts import ModelPlan
        from modeling_studio.script_fallback import fallback_script

        plan = ModelPlan.model_validate(
            {
                "object_name": "test",
                "parts": [
                    {"id": "base", "name": "base", "geometry": "cuboid", "size": [0.2, 0.1, 0.02]},
                    {"id": "pin", "name": "pin", "geometry": "cylinder", "size": [0.02, 0.02, 0.2]},
                ],
            }
        )
        guard_script(fallback_script(plan))


class SchemaEchoTest(unittest.TestCase):
    def test_detects_schema_echo(self):
        from modeling_studio.llm import looks_like_schema

        self.assertTrue(looks_like_schema('{"$defs": {"PlanCamera": {}}}'))
        self.assertTrue(looks_like_schema('{"properties": {"location": {}}}'))
        self.assertFalse(looks_like_schema('{"object_name": "x", "parts": []}'))
