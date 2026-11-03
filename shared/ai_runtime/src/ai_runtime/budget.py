"""Context budgeting for local and online model requests.

Rules (PRD FR-11):
- hard ceiling 65536 tokens; never a default
- default band 16384; complex tasks 32768
- budget counts system prompt, history, inputs, images and reserved output
- overflow raises instead of silently truncating
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field

DEFAULT_LIMIT = 16384
COMPLEX_LIMIT = 32768
HARD_LIMIT = 65536

# Qwen-family approximation: CJK characters are roughly one token each,
# Latin text is roughly four characters per token.
_TOKEN_PER_CJK = 1.0
_CHARS_PER_TOKEN = 4.0
_IMAGE_PATCH_PIXELS = 750


class ContextOverflow(RuntimeError):
    def __init__(self, estimated: int, limit: int, hint: str = ""):
        self.estimated = estimated
        self.limit = limit
        self.hint = hint
        message = f"context budget exceeded: estimated {estimated} > limit {limit} tokens"
        if hint:
            message += f"; {hint}"
        super().__init__(message)


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x3040 <= code <= 0x30FF
        or 0xAC00 <= code <= 0xD7AF
        or 0x3000 <= code <= 0x303F
        or 0xFF00 <= code <= 0xFFEF
    )


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = 0
    other = 0
    for char in text:
        if _is_cjk(char):
            cjk += 1
        elif unicodedata.category(char).startswith("C"):
            other += 1
        else:
            other += 1
    return int(math.ceil(cjk * _TOKEN_PER_CJK + other / _CHARS_PER_TOKEN))


def estimate_image_tokens(
    width: int, height: int, *, min_tokens: int = 0
) -> int:
    pixels = max(int(width), 0) * max(int(height), 0)
    base = int(math.ceil(pixels / _IMAGE_PATCH_PIXELS))
    return max(base, int(min_tokens))


def estimate_content_tokens(content) -> int:
    """Estimate a chat message content (string or multimodal part list)."""
    if content is None:
        return 0
    if isinstance(content, str):
        return estimate_text_tokens(content)
    total = 0
    for part in content:
        if not isinstance(part, dict):
            total += estimate_text_tokens(str(part))
            continue
        kind = part.get("type")
        if kind == "text":
            total += estimate_text_tokens(str(part.get("text", "")))
        elif kind == "image_url":
            image = part.get("image_url") or {}
            width = int(image.get("width") or 1280)
            height = int(image.get("height") or 720)
            total += estimate_image_tokens(width, height)
        else:
            total += estimate_text_tokens(str(part))
    return total


def estimate_messages_tokens(messages: list[dict]) -> int:
    total = 0
    for message in messages:
        total += 4  # role and framing overhead
        total += estimate_content_tokens(message.get("content"))
    return total


@dataclass
class BudgetReport:
    estimated: int
    limit: int
    reserved_output: int
    parts: dict[str, int] = field(default_factory=dict)

    @property
    def available(self) -> int:
        return max(self.limit - self.estimated, 0)

    @property
    def ok(self) -> bool:
        return self.estimated + self.reserved_output <= self.limit

    def as_dict(self) -> dict:
        return {
            "limit_tokens": self.limit,
            "estimated_input_tokens": self.estimated,
            "reserved_output_tokens": self.reserved_output,
            "parts": dict(self.parts),
        }


@dataclass
class ContextBudget:
    limit: int = DEFAULT_LIMIT
    reserved_output: int = 2048

    def __post_init__(self) -> None:
        if self.limit > HARD_LIMIT:
            raise ValueError(f"limit {self.limit} exceeds the hard ceiling {HARD_LIMIT}")
        if self.limit <= 0 or self.reserved_output < 0:
            raise ValueError("limit must be positive and reserved_output non-negative")

    def measure(
        self,
        messages: list[dict],
        *,
        images: list[tuple[int, int]] | None = None,
        extra: dict[str, str] | None = None,
    ) -> BudgetReport:
        parts = {"messages": estimate_messages_tokens(messages)}
        if images:
            parts["images"] = sum(estimate_image_tokens(w, h) for w, h in images)
        for name, text in (extra or {}).items():
            parts[name] = estimate_text_tokens(text)
        estimated = sum(parts.values())
        return BudgetReport(
            estimated=estimated,
            limit=self.limit,
            reserved_output=self.reserved_output,
            parts=parts,
        )

    def check(
        self,
        messages: list[dict],
        *,
        images: list[tuple[int, int]] | None = None,
        extra: dict[str, str] | None = None,
    ) -> BudgetReport:
        report = self.measure(messages, images=images, extra=extra)
        if not report.ok:
            hint = (
                "split the task into smaller units and pass intermediate artifacts "
                "instead of the full source"
            )
            raise ContextOverflow(report.estimated + report.reserved_output, report.limit, hint)
        return report


def plan_budget(purpose: str) -> ContextBudget:
    """Return the budget band for a task purpose."""
    purpose = purpose.lower()
    if purpose in {"complex", "review", "analysis", "course"}:
        return ContextBudget(limit=COMPLEX_LIMIT, reserved_output=3000)
    return ContextBudget(limit=DEFAULT_LIMIT, reserved_output=2048)
