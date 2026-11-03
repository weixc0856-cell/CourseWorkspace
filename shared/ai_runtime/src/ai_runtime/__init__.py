"""Shared local-model runtime.

Cross-process lock, service lifecycle, task records and context budgets for all
projects that call the single local llama.cpp service on port 8080.
"""

from .budget import (
    COMPLEX_LIMIT,
    DEFAULT_LIMIT,
    HARD_LIMIT,
    BudgetReport,
    ContextBudget,
    ContextOverflow,
    estimate_image_tokens,
    estimate_messages_tokens,
    estimate_text_tokens,
    plan_budget,
)
from .locks import FileLock, LockInfo, LockTimeout, pid_alive
from .service import (
    ModelSpec,
    ServerBusy,
    ServerConfig,
    ServerStartError,
    is_healthy,
    model_ids,
    model_service,
    port_in_use,
    probe,
)
from .tasks import STATUSES, TaskRecord, TaskStore, schema

__all__ = [
    "COMPLEX_LIMIT",
    "DEFAULT_LIMIT",
    "HARD_LIMIT",
    "BudgetReport",
    "ContextBudget",
    "ContextOverflow",
    "estimate_image_tokens",
    "estimate_messages_tokens",
    "estimate_text_tokens",
    "plan_budget",
    "FileLock",
    "LockInfo",
    "LockTimeout",
    "pid_alive",
    "ModelSpec",
    "ServerBusy",
    "ServerConfig",
    "ServerStartError",
    "is_healthy",
    "model_ids",
    "model_service",
    "port_in_use",
    "probe",
    "STATUSES",
    "TaskRecord",
    "TaskStore",
    "schema",
]
