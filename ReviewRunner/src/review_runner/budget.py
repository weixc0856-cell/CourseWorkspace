"""Context budget guard for one review run.

The project hard limit is 64K including reserved output (PRD FR-11).  A codex
``1M`` catalog never overrides it.  Reserves come from measurements on this
machine (2026-11-08, codex-cli 0.167.0):

* isolated invocation: 14,243 input tokens for a trivial request;
* user-config invocation: 19,238 input tokens for the same request.

The isolated form is the default, so its reserve is 18,000 (measured plus a
margin); the user-config form keeps the original 24,000 reserve.  The estimate
is an approximation, never a guarantee: actual usage is read from
``turn.completed`` and recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_runtime.budget import HARD_LIMIT as RUNTIME_HARD_LIMIT

from .schema import BudgetInfo

HARD_LIMIT = min(65536, RUNTIME_HARD_LIMIT)
SAFETY_MARGIN = 1000

SYSTEM_RESERVE_ISOLATED = 18000
SYSTEM_RESERVE_USER_CONFIG = 24000
INSTRUCTION_RESERVE = 3000
OUTPUT_RESERVE = 8000

BUDGET_CEILING = HARD_LIMIT - SAFETY_MARGIN
WARN_RATIO = 0.8

MEASURED_ISOLATED_INPUT = 14243
MEASURED_USER_CONFIG_INPUT = 19238
MEASURED_DATE = "2026-11-08"


@dataclass(frozen=True)
class BudgetPolicy:
    system_reserve: int = SYSTEM_RESERVE_ISOLATED
    hard_limit: int = HARD_LIMIT
    safety_margin: int = SAFETY_MARGIN
    instruction_reserve: int = INSTRUCTION_RESERVE
    output_reserve: int = OUTPUT_RESERVE
    warn_ratio: float = WARN_RATIO

    @property
    def ceiling(self) -> int:
        return self.hard_limit - self.safety_margin

    @property
    def file_budget(self) -> int:
        return (
            self.ceiling
            - self.system_reserve
            - self.instruction_reserve
            - self.output_reserve
        )

    def evaluate(
        self,
        *,
        diff_tokens: int,
        file_tokens: int,
        task_prompt_tokens: int,
    ) -> BudgetInfo:
        content = diff_tokens + file_tokens
        # The prompt carries the diff and file full texts inline, so the
        # instruction portion is the prompt minus the content it embeds.
        instruction = max(
            self.instruction_reserve,
            max(0, task_prompt_tokens - content),
        )
        estimate = self.system_reserve + instruction + content
        total = estimate + self.output_reserve
        reasons: list[str] = []
        if content > self.file_budget:
            reasons.append(
                f"file content {content} > file budget {self.file_budget}; "
                "split the commit or narrow the review scope"
            )
        if total > self.ceiling:
            reasons.append(f"estimated total {total} > ceiling {self.ceiling}")
        return BudgetInfo(
            hard_limit=self.hard_limit,
            safety_margin=self.safety_margin,
            system_reserve=self.system_reserve,
            instruction_reserve=self.instruction_reserve,
            output_reserve=self.output_reserve,
            file_budget=self.file_budget,
            diff_tokens=diff_tokens,
            file_tokens=file_tokens,
            task_prompt_tokens=task_prompt_tokens,
            estimated_input_tokens=estimate,
            estimated_total_tokens=total,
            warning=content > int(self.file_budget * self.warn_ratio),
            blocked=bool(reasons),
            blocked_reason="; ".join(reasons) if reasons else None,
        )

    def check_actual(self, info: BudgetInfo, usage: dict | None) -> BudgetInfo:
        usage = usage or {}
        input_tokens = _int_or_none(usage.get("input_tokens"))
        output_tokens = _int_or_none(usage.get("output_tokens"))
        updated = info.model_copy(
            update={
                "actual_input_tokens": input_tokens,
                "actual_output_tokens": output_tokens,
            }
        )
        # The hard ceiling is about the request context (input).  Output is a
        # generation budget: exceeding the 8K reserve is recorded as a cost
        # signal, not as a context violation.  Measured on 2026-11-08, a real
        # review used input 49,976 (< 64K) and output 61,814, which would
        # otherwise wrongly mark a usable review incomplete.
        violation = input_tokens is not None and input_tokens > self.hard_limit
        output_over_reserve = (
            output_tokens is not None and output_tokens > self.output_reserve
        )
        return updated.model_copy(
            update={
                "violation": violation,
                "output_over_reserve": output_over_reserve,
            }
        )


def policy_for(*, isolated: bool) -> BudgetPolicy:
    return BudgetPolicy(
        system_reserve=(
            SYSTEM_RESERVE_ISOLATED if isolated else SYSTEM_RESERVE_USER_CONFIG
        )
    )


def _int_or_none(value) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


DEFAULT_POLICY = BudgetPolicy()


__all__ = [
    "BUDGET_CEILING",
    "BudgetPolicy",
    "DEFAULT_POLICY",
    "HARD_LIMIT",
    "INSTRUCTION_RESERVE",
    "MEASURED_DATE",
    "MEASURED_ISOLATED_INPUT",
    "MEASURED_USER_CONFIG_INPUT",
    "OUTPUT_RESERVE",
    "SAFETY_MARGIN",
    "SYSTEM_RESERVE_ISOLATED",
    "SYSTEM_RESERVE_USER_CONFIG",
    "WARN_RATIO",
    "policy_for",
]
