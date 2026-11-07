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
from .claude_code import (
    ClaudeCodeConfig,
    ClaudeCodeError,
    ClaudeCodeResult,
    ClaudeCodeUnavailable,
    complete as claude_code_complete,
)
from .env import load_env_file
from .locks import FileLock, LockInfo, LockTimeout, pid_alive
from .remote import (
    RemoteAuthError,
    RemoteConfig,
    RemoteError,
    RemoteResponseError,
    RemoteResult,
    RemoteUnavailable,
    chat_completion,
    health as remote_health,
)
from .routing import ModelRoute, route_model
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
    "load_env_file",
    "ClaudeCodeConfig",
    "ClaudeCodeError",
    "ClaudeCodeResult",
    "ClaudeCodeUnavailable",
    "claude_code_complete",
    "RemoteAuthError",
    "RemoteConfig",
    "RemoteError",
    "RemoteResponseError",
    "RemoteResult",
    "RemoteUnavailable",
    "chat_completion",
    "remote_health",
    "ModelRoute",
    "route_model",
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
