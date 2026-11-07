from __future__ import annotations

import base64
import json

from PIL import Image

from .config import PROJECT_ROOT, WorkflowConfig
from .contracts import Revision
from .job import Job, save_task, stage_task, update_metadata, write_json
from .llm import LLMClient
from .server import managed_model

PROMPT = PROJECT_ROOT / "prompts" / "visual_revision.md"
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _data_uri(path) -> str:
    mime = MIME.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _size(path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def revise(config: WorkflowConfig, job: Job) -> Revision:
    preview = job.scene_dir / "preview.png"
    if not job.original.is_file():
        raise FileNotFoundError(f"reference image not found: {job.original}")
    if not preview.is_file():
        raise FileNotFoundError(f"preview not found: {preview}")
    schema = json.dumps(Revision.model_json_schema(), ensure_ascii=False)
    system = PROMPT.read_text(encoding="utf-8").replace("{schema}", schema)
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Original reference image:"},
                {"type": "image_url", "image_url": {"url": _data_uri(job.original)}},
                {"type": "text", "text": "Current rendered preview:"},
                {"type": "image_url", "image_url": {"url": _data_uri(preview)}},
                {
                    "type": "text",
                    "text": "Compare them and return the revision JSON only.",
                },
            ],
        },
    ]
    image_sizes = [_size(job.original), _size(preview)]
    budget = config.budget_for("revise")
    budget_report = budget.check(messages, images=image_sizes)

    client = LLMClient(config, budget=budget, images=image_sizes)
    with stage_task(
        job,
        config,
        stage="revise",
        task_type="modeling.revise",
        model_key="vision",
        input_artifacts=["input/original", "scene/preview.png"],
        output_artifacts=["revision.json"],
        context_budget=budget_report.as_dict(),
        timeout_s=config.llm.request_timeout_s,
    ) as record:
        with managed_model(
            config, "vision", job.logs_dir / "server-revision.log", vision=True
        ) as route:
            record.assigned_model = route.model
            record.provider = route.provider
            save_task(config, job, record)
            revision, usage = client.chat_json(
                messages, "vision", Revision, max_tokens=1200, route=route
            )
    write_json(job.revision, revision)
    update_metadata(
        job,
        stage="revise",
        status="pass",
        model=route.model,
        provider=route.provider,
        server=route.mode,
        usage=usage,
        differences=len(revision.differences),
    )
    return revision
