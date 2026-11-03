from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modeling_studio.config import WorkflowConfig
from modeling_studio.job import Job, create_job, read_json, stage_done, stage_status, stage_task

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample-assembly.png"


def make_config(root: Path) -> WorkflowConfig:
    return WorkflowConfig.model_validate(
        {
            "schema_version": 1,
            "server": {"executable": str(root / "llama-server.exe")},
            "models": {
                "planner": {
                    "path": str(root / "model.gguf"),
                    "alias": "planner-alias",
                }
            },
            "blender": {"executable": str(root / "blender.exe")},
            "jobs_root": str(root / "jobs"),
            "runtime": {
                "lock_path": str(root / "runtime" / "lock"),
                "task_root": str(root / "runtime" / "tasks"),
            },
        }
    )


class StageTaskTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = make_config(self.root)
        self.job = Job("job-1", self.root / "jobs" / "job-1")
        self.job.root.mkdir(parents=True)
        (self.job.root / "job.json").write_text(
            json.dumps({"job_id": "job-1", "stages": {}}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_success_writes_completed_record(self):
        with stage_task(
            self.job,
            self.config,
            stage="plan",
            task_type="modeling.plan",
            model_key="planner",
            input_artifacts=["visual_analysis.json"],
            output_artifacts=["model_plan.json"],
            context_budget={"limit_tokens": 32768, "estimated_input_tokens": 100},
        ):
            pass
        self.assertEqual(stage_status(self.job, "plan"), "completed")
        record = json.loads((self.job.tasks_dir / "modeling-job-1-plan.json").read_text("utf-8"))
        self.assertEqual(record["status"], "completed")
        self.assertTrue((self.config.runtime.task_root_resolved / "modeling-job-1-plan.json").is_file())

    def test_failure_is_persisted_in_job_and_task(self):
        with self.assertRaises(RuntimeError):
            with stage_task(
                self.job,
                self.config,
                stage="plan",
                task_type="modeling.plan",
                model_key="planner",
                input_artifacts=["visual_analysis.json"],
                output_artifacts=["model_plan.json"],
            ):
                raise RuntimeError("model unavailable")
        data = read_json(self.job.metadata)
        self.assertEqual(data["stages"]["plan"]["status"], "failed")
        self.assertIn("model unavailable", data["stages"]["plan"]["error"])
        record = json.loads((self.job.tasks_dir / "modeling-job-1-plan.json").read_text("utf-8"))
        self.assertEqual(record["status"], "failed")
        self.assertIn("model unavailable", record["error"])

    def test_resume_only_skips_completed_stage_with_artifact(self):
        artifact = self.job.root / "model_plan.json"
        self.assertFalse(stage_done(self.job, "plan", artifact, resume=True))
        self.job.metadata.write_text(
            json.dumps({"job_id": "job-1", "stages": {"plan": {"status": "completed"}}}),
            encoding="utf-8",
        )
        self.assertFalse(stage_done(self.job, "plan", artifact, resume=True))
        artifact.write_text("{}", encoding="utf-8")
        self.assertTrue(stage_done(self.job, "plan", artifact, resume=True))
        self.assertFalse(stage_done(self.job, "plan", artifact, resume=False))
        self.job.metadata.write_text(
            json.dumps({"job_id": "job-1", "stages": {"plan": {"status": "failed"}}}),
            encoding="utf-8",
        )
        self.assertFalse(stage_done(self.job, "plan", artifact, resume=True))


class CreateJobTest(unittest.TestCase):
    def test_duplicate_job_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = make_config(root)
            create_job(config, FIXTURE, job_id="same-id")
            with self.assertRaises(FileExistsError):
                create_job(config, FIXTURE, job_id="same-id")


if __name__ == "__main__":
    unittest.main()
