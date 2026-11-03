from __future__ import annotations

import json
import unittest
from pathlib import Path

from content_qa.contracts import Finding, ModelReply, ReviewReport, ReviewTask

PROJECT = Path(__file__).resolve().parents[1]
SCHEMAS = PROJECT / "schemas"


class SchemaDriftTest(unittest.TestCase):
    def test_committed_schemas_match_models(self):
        models = {
            "content-review": ReviewReport,
            "content-finding": Finding,
            "content-reply": ModelReply,
            "content-task": ReviewTask,
        }
        for name, model in models.items():
            with self.subTest(name=name):
                committed = (SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8")
                rendered = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
                self.assertEqual(rendered, committed)


if __name__ == "__main__":
    unittest.main()
