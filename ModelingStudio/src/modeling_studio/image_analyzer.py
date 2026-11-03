from __future__ import annotations

import base64
import json

from PIL import Image

from .config import PROJECT_ROOT, WorkflowConfig
from .contracts import VisualAnalysis
from .job import Job, stage_task, update_metadata, write_json
from .llm import LLMClient
from .server import managed_server

PROMPT = PROJECT_ROOT / "prompts" / "image_analysis.md"


def _data_uri(path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def analyze_image(config: WorkflowConfig, job: Job) -> VisualAnalysis:
    if not job.image.is_file():
        raise FileNotFoundError(f"job image not found: {job.image}")
    schema = json.dumps(VisualAnalysis.model_json_schema(), ensure_ascii=False)
    system = PROMPT.read_text(encoding="utf-8").replace("{schema}", schema)
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Analyze this image for 3D reconstruction. Return the JSON object only.",
                },
                {"type": "image_url", "image_url": {"url": _data_uri(job.image)}},
            ],
        },
    ]
    with Image.open(job.image) as image:
        width, height = image.size
    budget = config.budget_for("analyze")
    budget_report = budget.check(messages, images=[(width, height)])

    client = LLMClient(config, budget=budget, images=[(width, height)])
    try:
        with stage_task(
            job,
            config,
            stage="analyze",
            task_type="modeling.analyze",
            model_key="vision",
            input_artifacts=["input/input.png"],
            output_artifacts=["visual_analysis.json"],
            context_budget=budget_report.as_dict(),
            timeout_s=config.llm.request_timeout_s,
        ):
            with managed_server(config, "vision", job.logs_dir / "server-vision.log") as mode:
                analysis, usage = client.chat_json(
                    messages, "vision", VisualAnalysis, max_tokens=1600
                )
    except Exception:
        if client.last_raw:
            (job.logs_dir / "analyze-last-response.txt").write_text(
                client.last_raw, encoding="utf-8"
            )
        raise
    write_json(job.visual_analysis, analysis)
    update_metadata(
        job,
        stage="analyze",
        status="pass",
        model=config.model("vision").alias,
        server=mode,
        usage=usage,
        parts=len(analysis.parts),
    )
    return analysis
