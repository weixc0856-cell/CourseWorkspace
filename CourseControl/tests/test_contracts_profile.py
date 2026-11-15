from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.production.contracts import (
    ContractModelError,
    export_schemas,
    load_contract,
)


def product(**overrides):
    data = {
        "schema_version": 1,
        "product": "demo",
        "title": "Demo",
        "format": "news",
        "time_authority": "timeline",
        "duration": {"target_s": 262, "min_s": 230, "max_s": 300},
        "visual_sources": ["schematic"],
        "narration": {"enabled": True, "segments": 35},
        "evidence": {"requirements": ["every claim carries a label"], "data_authority": "filings", "render_only": []},
        "acceptance": {"rubric": "100-point", "gates": ["G0", "G7"]},
    }
    data.update(overrides)
    return data


def ledger(**overrides):
    data = {
        "schema_version": 1,
        "product": "demo",
        "records": [
            {
                "asset_id": "fig-1",
                "kind": "book_figure",
                "role": "evidence",
                "source": "book ch.1",
                "license": "internal",
                "captured_at": "2026-11-15T10:00:00+08:00",
            }
        ],
    }
    data.update(overrides)
    return data


def timeline(**overrides):
    data = {
        "schema_version": 1,
        "product": "demo",
        "fps": 30,
        "resolution": [1920, 1080],
        "duration_s": 262,
        "entries": [{"id": "e1", "kind": "scene", "start_s": 0, "duration_s": 12.5}],
    }
    data.update(overrides)
    return data


class ContractProfileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, data, name="contract.yaml"):
        path = self.root / name
        if path.suffix == ".json":
            path.write_text(json.dumps(data), encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def test_product_valid_yaml(self):
        model = load_contract("product", self._write(product()))
        self.assertEqual(model.product, "demo")

    def test_product_valid_json(self):
        model = load_contract("product", self._write(product(), "contract.json"))
        self.assertEqual(model.time_authority, "timeline")

    def test_product_extra_field_fails(self):
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(product(surprise=True)))

    def test_product_missing_required_fails(self):
        data = product()
        data.pop("acceptance")
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(data))

    def test_product_enum_out_of_range_fails(self):
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(product(format="podcast")))

    def test_product_duration_must_be_positive(self):
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(product(duration={"target_s": 0})))

    def test_ledger_valid(self):
        model = load_contract("ledger", self._write(ledger()))
        self.assertEqual(model.records[0].asset_id, "fig-1")

    def test_ledger_bad_role_fails(self):
        data = ledger()
        data["records"][0]["role"] = "data_source"
        with self.assertRaises(ContractModelError):
            load_contract("ledger", self._write(data))

    def test_ledger_extra_field_fails(self):
        data = ledger()
        data["records"][0]["sha256"] = "x"
        with self.assertRaises(ContractModelError):
            load_contract("ledger", self._write(data))

    def test_timeline_valid(self):
        model = load_contract("timeline", self._write(timeline()))
        self.assertEqual(model.fps, 30)

    def test_timeline_bad_kind_fails(self):
        data = timeline()
        data["entries"][0]["kind"] = "sticker"
        with self.assertRaises(ContractModelError):
            load_contract("timeline", self._write(data))

    def test_timeline_entry_negative_start_fails(self):
        data = timeline()
        data["entries"][0]["start_s"] = -1
        with self.assertRaises(ContractModelError):
            load_contract("timeline", self._write(data))

    def test_unknown_kind_fails(self):
        with self.assertRaises(ContractModelError):
            load_contract("podcast", self._write(product()))

    def test_export_schemas_marks_provenance(self):
        targets = export_schemas(self.root / "schemas")
        self.assertEqual(len(targets), 3)
        for target in targets:
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertTrue(data["$id"].endswith(target.name))
            self.assertIn("title", data)

    def test_missing_schema_version_fails(self):
        data = product()
        data.pop("schema_version")
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(data))

    def test_wrong_schema_version_fails(self):
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(product(schema_version=99)))

    def test_explicit_null_is_not_an_optional_value(self):
        with self.assertRaises(ContractModelError):
            load_contract("product", self._write(product(title=None)))

    def test_exported_required_sets_match_the_contract(self):
        expected = {
            "product": {"schema_version", "product", "format", "time_authority", "duration", "evidence", "acceptance"},
            "ledger": {"schema_version", "product", "records"},
            "production-timeline": {"schema_version", "product", "fps", "duration_s", "entries"},
        }
        export_schemas(self.root / "schemas")
        for name, required in expected.items():
            data = json.loads((self.root / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
            self.assertEqual(set(data["required"]), required, name)
            self.assertEqual(data["properties"]["schema_version"]["const"], 1, name)


if __name__ == "__main__":
    unittest.main()
