from __future__ import annotations

import json

from .config import PROJECT_ROOT, WorkflowConfig
from .contracts import ModelPlan, VisualAnalysis
from .job import Job, read_json, stage_task, update_metadata, write_json
from .llm import LLMClient
from .server import managed_server

PROMPT = PROJECT_ROOT / "prompts" / "modeling_plan.md"


def _notes(job: Job) -> str | None:
    if not job.metadata.is_file():
        return None
    return read_json(job.metadata).get("notes")


def normalize_plan(plan: ModelPlan) -> ModelPlan:
    """Normalize primitive axis conventions.

    Cylinders and cones are built along local Z. The planner sometimes emits
    [diameter, height, diameter]; convert that to [diameter, diameter, height].
    """

    for part in plan.parts:
        if part.geometry not in {"cylinder", "cone"}:
            continue
        x, y, z = part.size
        if abs(x - z) < 1e-6 and abs(y - x) > 1e-6:
            part.size = (x, z, y)
    return plan


def ground_plan(plan: ModelPlan) -> ModelPlan:
    """Shift the assembly up so its lowest part sits on z=0."""
    lowest = min(part.location[2] - part.size[2] / 2 for part in plan.parts)
    if lowest < -1e-6:
        delta = -lowest
        for part in plan.parts:
            part.location = (
                part.location[0],
                part.location[1],
                part.location[2] + delta,
            )
        plan.assumptions.append(
            f"Assembly shifted up by {delta:.4f} m so the lowest part sits at z=0."
        )
    return plan


def plan_model(config: WorkflowConfig, job: Job) -> ModelPlan:
    analysis = VisualAnalysis.model_validate(read_json(job.visual_analysis))
    schema = json.dumps(ModelPlan.model_json_schema(), ensure_ascii=False)
    system = PROMPT.read_text(encoding="utf-8").replace("{schema}", schema)
    notes = _notes(job)
    user = (
        "Visual analysis:\n"
        + json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2)
        + "\n\n"
    )
    if notes:
        user += f"User constraints / scale notes:\n{notes}\n\n"
    user += "Produce the buildable modeling plan JSON."
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    budget = config.budget_for("plan")
    budget_report = budget.check(messages)

    client = LLMClient(config, budget=budget)
    try:
        with stage_task(
            job,
            config,
            stage="plan",
            task_type="modeling.plan",
            model_key="planner",
            input_artifacts=["visual_analysis.json"],
            output_artifacts=["model_plan.json"],
            context_budget=budget_report.as_dict(),
            timeout_s=config.llm.request_timeout_s,
        ):
            with managed_server(config, "planner", job.logs_dir / "server-planner.log") as mode:
                plan, usage = client.chat_json(messages, "planner", ModelPlan, max_tokens=3000)
    except Exception:
        if client.last_raw:
            (job.logs_dir / "plan-last-response.txt").write_text(
                client.last_raw, encoding="utf-8"
            )
        raise
    plan = ground_plan(normalize_plan(plan))
    write_json(job.model_plan, plan)
    update_metadata(
        job,
        stage="plan",
        status="pass",
        model=config.model("planner").alias,
        server=mode,
        usage=usage,
        parts=len(plan.parts),
    )
    return plan
