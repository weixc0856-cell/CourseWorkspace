from __future__ import annotations

import json

from .config import PROJECT_ROOT, WorkflowConfig
from .contracts import ModelPlan
from .job import Job, read_json, save_task, stage_task, update_metadata
from .llm import LLMClient
from .script_fallback import fallback_script
from .script_guard import ScriptRejected, extract_code, guard_script, write_script
from .server import managed_model

PROMPT = PROJECT_ROOT / "prompts" / "script_generation.md"


def generate_script(config: WorkflowConfig, job: Job, *, attempts: int = 3) -> str:
    plan = ModelPlan.model_validate(read_json(job.model_plan))
    system = PROMPT.read_text(encoding="utf-8").replace(
        "{plan}", json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "Write the Blender module for this plan. Return only one Python code block.",
        },
    ]
    budget = config.budget_for("generate")
    budget_report = budget.check(messages)

    client = LLMClient(config, budget=budget)
    rejection = ""
    code = ""
    route = None
    with stage_task(
        job,
        config,
        stage="generate",
        task_type="modeling.generate",
        model_key="coder",
        input_artifacts=["model_plan.json"],
        output_artifacts=["build_model.py"],
        context_budget=budget_report.as_dict(),
        timeout_s=config.llm.request_timeout_s,
    ) as record:
        with managed_model(config, "coder", job.logs_dir / "server-coder.log") as route:
            record.assigned_model = route.model
            record.provider = route.provider
            save_task(config, job, record)
            for attempt in range(attempts):
                content, usage = client.chat(
                    messages, "coder", max_tokens=6000, temperature=0.05, route=route
                )
                code = extract_code(content)
                try:
                    guard_script(code)
                    write_script(job.script, code, model=config.model("coder").alias)
                    update_metadata(
                        job,
                        stage="generate",
                        status="pass",
                        model=route.model,
                        provider=route.provider,
                        server=route.mode,
                        usage=usage,
                        attempts=attempt + 1,
                        lines=code.count("\n") + 1,
                    )
                    return code
                except ScriptRejected as exc:
                    rejection = str(exc)
                    messages = [
                        *messages,
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "The script was rejected by the static guard: "
                                f"{rejection}. Rewrite the complete module and keep the "
                                "same hard requirements. Return only one Python code block."
                            ),
                        },
                    ]
    code = fallback_script(plan)
    guard_script(code)
    write_script(job.script, code, model="fallback")
    update_metadata(
        job,
        stage="generate",
        status="fallback",
        model="fallback",
        provider=route.provider if route else "local",
        server=route.mode if route else "fallback",
        error=rejection,
    )
    return code
