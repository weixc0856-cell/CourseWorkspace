from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from course_control.production.checks import run_checks
from course_control.production.episode_spec import EpisodeSpecError, load_episode_spec
from course_control.production.preflight import run_preflight
from course_control.production.quality_rubric import QualityRubricError, load_quality_rubric


def _spec(**overrides):
    data = {
        "schema_version": 1,
        "episode": "T1-01",
        "title": "Why",
        "core_question": "Why?",
        "target_seconds": 600,
        "min_seconds": 480,
        "max_seconds": 900,
        "claims": [
            {
                "id": "C01",
                "text": "claim",
                "source": {"chapter": "3", "page": 156},
                "status": "must_teach",
            }
        ],
        "beats": [
            {"id": "B1", "type": "question", "seconds": 100, "claims": ["C01"]},
            {"id": "B2", "type": "case", "seconds": 100, "claims": ["C01"]},
            {"id": "B3", "type": "mechanism", "seconds": 100, "claims": ["C01"]},
            {"id": "B4", "type": "derivation", "seconds": 100, "claims": ["C01"]},
            {"id": "B5", "type": "evidence", "seconds": 100, "claims": ["C01"]},
            {"id": "B6", "type": "conclusion", "seconds": 100, "claims": ["C01"]},
        ],
        "cut_list": ["history"],
        "not_claimed": ["market data"],
        "voice": {"status": "tbd"},
        "rights": {"figures_checked": False},
        "assets": [],
    }
    data.update(overrides)
    return data


class EpisodeSpecTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, data, name="episode.spec.yaml"):
        path = self.root / "authoring" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def _rubric(self, weights=(30, 30, 20, 20)):
        data = {
            "schema_version": 1,
            "dimensions": {
                "content": {"weight": weights[0], "checks": [{"id": "claim_source", "kind": "auto", "rule": "claim_source_coverage"}]},
                "visual": {"weight": weights[1], "checks": [{"id": "frames_present", "kind": "auto", "rule": "frames_present"}]},
                "narrative": {"weight": weights[2], "checks": [{"id": "mechanism_depth", "kind": "review", "prompt": "why"}]},
                "delivery": {"weight": weights[3], "checks": [{"id": "voice_decided", "kind": "auto", "rule": "voice_decided"}]},
            },
            "hard_fails": ["missing_source"],
            "pass_threshold": 80,
        }
        path = self.root / "authoring" / "quality.rubric.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return path

    def test_valid_spec(self):
        spec = load_episode_spec(self._write(_spec()))
        self.assertEqual(spec.total_seconds, 600)
        self.assertEqual(spec.episode, "T1-01")

    def test_unknown_beat_claim(self):
        data = _spec()
        data["beats"][0]["claims"] = ["C99"]
        with self.assertRaises(EpisodeSpecError):
            load_episode_spec(self._write(data))

    def test_missing_beat_type(self):
        data = _spec()
        data["beats"] = [b for b in data["beats"] if b["type"] != "evidence"]
        with self.assertRaises(EpisodeSpecError):
            load_episode_spec(self._write(data))

    def test_source_must_be_locatable(self):
        data = _spec()
        data["claims"][0]["source"] = {"chapter": "3"}
        with self.assertRaises(EpisodeSpecError):
            load_episode_spec(self._write(data))

    def test_preflight_warns_voice_tbd(self):
        self._write(_spec())
        self._rubric()
        report = run_preflight(self.root)
        self.assertTrue(report.ok)
        self.assertTrue(any("voice.status" in w for w in report.warnings))

    def test_preflight_strict_promotes_warning(self):
        self._write(_spec())
        self._rubric()
        report = run_preflight(self.root, strict=True)
        self.assertFalse(report.ok)

    def test_preflight_rejects_drivaer_as_data(self):
        data = _spec()
        data["assets"] = [{"source": "DrivAer", "role": "data"}]
        self._write(data)
        self._rubric()
        report = run_preflight(self.root)
        self.assertTrue(any("render-only" in e for e in report.errors))

    def test_rubric_weights_must_sum_100(self):
        with self.assertRaises(QualityRubricError):
            load_quality_rubric(self._rubric(weights=(30, 30, 20, 10)))

    def test_checks_auto_fail_and_review_queue(self):
        spec = load_episode_spec(self._write(_spec()))
        rubric = load_quality_rubric(self._rubric())
        report = run_checks(spec, rubric, self.root, self.root / "build")
        self.assertTrue(any(r.id == "voice_decided" and r.status == "fail" for r in report.results))
        self.assertTrue(any(r.id == "mechanism_depth" and r.status == "review" for r in report.review_open))
        self.assertTrue(any(r.id == "frames_present" and r.status == "not_run" for r in report.not_run))

    def _index(self, entries):
        path = self.root / "book" / "index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sources": entries}), encoding="utf-8")
        return path

    def _report(self, book_index=None):
        spec = load_episode_spec(self._write(_spec()))
        rubric = load_quality_rubric(self._rubric())
        return run_checks(spec, rubric, self.root, self.root / "build", book_index=book_index)

    def test_claim_source_not_run_without_book_index(self):
        report = self._report()
        claim = next(r for r in report.results if r.id == "claim_source")
        self.assertEqual(claim.status, "not_run")
        self.assertNotIn(claim, report.auto_failed)

    def test_claim_source_fails_when_claim_not_indexed(self):
        index = self._index([{"chapter": "9", "page": 1}])
        report = self._report(book_index=index)
        claim = next(r for r in report.results if r.id == "claim_source")
        self.assertEqual(claim.status, "fail")
        self.assertEqual(claim.actual, ["C01"])

    def test_claim_source_passes_when_indexed(self):
        index = self._index([{"chapter": "3", "page": 156}])
        report = self._report(book_index=index)
        claim = next(r for r in report.results if r.id == "claim_source")
        self.assertEqual(claim.status, "pass")

    def test_exceptions_include_not_run_when_warn(self):
        spec = load_episode_spec(self._write(_spec()))
        rubric_path = self.root / "authoring" / "quality.rubric.yaml"
        rubric_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "dimensions": {
                "content": {"weight": 40, "checks": [{"id": "voice_decided", "kind": "auto", "rule": "voice_decided"}]},
                "visual": {"weight": 30, "checks": [{"id": "frames_warn", "kind": "auto", "rule": "frames_present", "severity": "warn"}]},
                "narrative": {"weight": 15, "checks": [{"id": "z", "kind": "review", "prompt": "p"}]},
                "delivery": {"weight": 15, "checks": [{"id": "w", "kind": "review", "prompt": "p"}]},
            },
            "hard_fails": ["missing_source"],
            "pass_threshold": 80,
        }), encoding="utf-8")
        rubric = load_quality_rubric(rubric_path)
        report = run_checks(spec, rubric, self.root, self.root / "build")
        payload = report.as_dict("spec")
        ids = [entry["id"] for entry in payload["exceptions"]]
        self.assertIn("frames_warn", ids)

    def test_checks_accept_non_course_spec(self):
        spec = SimpleNamespace(episode="NEWS-01", claims=[], beats=[], voice={})
        rubric = load_quality_rubric(self._rubric())
        report = run_checks(spec, rubric, self.root, self.root / "build")
        self.assertEqual(report.lesson, "NEWS-01")
        claim = next(r for r in report.results if r.id == "claim_source")
        self.assertEqual(claim.status, "not_run")

    def test_unknown_auto_rule_fails(self):
        data = _spec()
        spec = load_episode_spec(self._write(data))
        rubric_path = self.root / "authoring" / "quality.rubric.yaml"
        rubric_path.write_text(yaml.safe_dump({
            "schema_version": 1,
            "dimensions": {
                "content": {"weight": 50, "checks": [{"id": "x", "kind": "auto", "rule": "nope"}]},
                "visual": {"weight": 25, "checks": [{"id": "y", "kind": "review", "prompt": "p"}]},
                "narrative": {"weight": 10, "checks": [{"id": "z", "kind": "review", "prompt": "p"}]},
                "delivery": {"weight": 15, "checks": [{"id": "w", "kind": "review", "prompt": "p"}]},
            },
            "hard_fails": ["missing_source"],
            "pass_threshold": 80,
        }), encoding="utf-8")
        rubric = load_quality_rubric(rubric_path)
        report = run_checks(spec, rubric, self.root, self.root / "build")
        self.assertTrue(any(r.id == "x" and r.status == "fail" for r in report.auto_failed))

    def test_beat_coverage_fails_on_a_missing_type(self):
        from types import SimpleNamespace

        rubric = load_quality_rubric(self._rubric())
        beats = [
            SimpleNamespace(type="question", claims=["C1"]),
            SimpleNamespace(type="conclusion", claims=["C1"]),
        ]
        spec = SimpleNamespace(episode="X", claims=[SimpleNamespace(id="C1", status="must_teach")], beats=beats)
        report = run_checks(spec, rubric, self.root, self.root / "build")
        result = next(r for r in report.results if r.id == "claim_source")
        self.assertEqual(result.status, "not_run")
        # beat_coverage is exercised through a rubric that names the rule.
        from course_control.production.checks import _beat_coverage, EvalContext

        status, actual, _expected, _evidence = _beat_coverage(EvalContext(spec=spec, lesson_dir=self.root, build_root=self.root / "build"))
        self.assertEqual(status, "fail")
        self.assertIn("mechanism", actual["missing_types"])

    def test_timeline_assets_reports_missing_files(self):
        from course_control.production.checks import _timeline_assets, EvalContext
        from types import SimpleNamespace

        contracts = self.root / "build" / "contracts"
        contracts.mkdir(parents=True)
        (contracts / "timeline.spec.json").write_text(
            json.dumps({"video": [{"shot_id": "s1", "asset": {"path": str(self.root / "missing.png")}}], "audio": []}),
            encoding="utf-8",
        )
        spec = SimpleNamespace(episode="X")
        status, actual, _expected, _evidence = _timeline_assets(EvalContext(spec=spec, lesson_dir=self.root, build_root=self.root / "build"))
        self.assertEqual(status, "fail")
        self.assertEqual(len(actual), 1)

    def test_narration_measured_uses_the_spec_window(self):
        from course_control.production.checks import _narration_measured, EvalContext
        from types import SimpleNamespace

        narration = self.root / "build" / "narration"
        narration.mkdir(parents=True)
        (narration / "narration.meta.json").write_text(
            json.dumps({"segments": [{"end_s": 700.0}, {"end_s": 719.2}]}),
            encoding="utf-8",
        )
        spec = SimpleNamespace(episode="X", total_seconds=600, min_seconds=480, max_seconds=900)
        status, actual, _expected, _evidence = _narration_measured(EvalContext(spec=spec, lesson_dir=self.root, build_root=self.root / "build"))
        self.assertEqual(status, "pass")
        self.assertAlmostEqual(actual["measured_s"], 719.2)

        spec.max_seconds = 600
        status, _actual, _expected, _evidence = _narration_measured(EvalContext(spec=spec, lesson_dir=self.root, build_root=self.root / "build"))
        self.assertEqual(status, "fail")

    def test_beat_plan_must_carry_every_must_teach_claim(self):
        from types import SimpleNamespace
        from course_control.production.checks import EvalContext, _beat_plan_coverage

        authoring = self.root / "authoring"
        authoring.mkdir(parents=True, exist_ok=True)
        (authoring / "beat-segments.yaml").write_text(
            yaml.safe_dump({
                "beats": [
                    {"id": "B1", "type": "question", "claims": ["C01"]},
                    {"id": "B2", "type": "case", "claims": ["C01"]},
                    {"id": "B3", "type": "mechanism", "claims": ["C01"]},
                    {"id": "B4", "type": "derivation", "claims": ["C01"]},
                    {"id": "B5", "type": "evidence", "claims": ["C01"]},
                    {"id": "B6", "type": "conclusion", "claims": ["C01"]},
                ]
            }, sort_keys=False),
            encoding="utf-8",
        )
        spec = SimpleNamespace(claims=[
            SimpleNamespace(id="C01", status="must_teach"),
            SimpleNamespace(id="C02", status="must_teach"),
        ])
        status, actual, _expected, _evidence = _beat_plan_coverage(
            EvalContext(spec=spec, lesson_dir=self.root, build_root=self.root / "build")
        )
        self.assertEqual(status, "fail")
        self.assertEqual(actual["missing_claims"], ["C02"])


if __name__ == "__main__":
    unittest.main()
