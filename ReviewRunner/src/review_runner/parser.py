"""Parse codex ``--json`` JSONL events and the findings contract.

The parser is deliberately narrow: it reads the last ``agent_message`` and the
single fenced ``json:findings`` block.  Anything else (missing final message,
unparseable JSONL, invalid finding) makes the review ``REVIEW_INCOMPLETE``; the
raw output is still archived so nothing is lost.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .schema import Finding, FindingsEnvelope, Verification

FINDINGS_FENCE = re.compile(
    r"```[ \t]*json:findings[ \t]*\r?\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# Known CLI noise.  These are configuration/installation messages, never
# review findings.  They are counted and recorded, and the raw stderr is kept.
NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"unrecognized configuration setting", re.IGNORECASE),
    re.compile(r"failed to load skill", re.IGNORECASE),
    re.compile(r"missing yaml frontmatter", re.IGNORECASE),
    re.compile(r"reading additional input from stdin", re.IGNORECASE),
    re.compile(r"model metadata for .* not found", re.IGNORECASE),
    re.compile(r"defaulting to fallback metadata", re.IGNORECASE),
    re.compile(r"under-development features enabled", re.IGNORECASE),
    re.compile(r"rollout.*(corrupt|failed|legacy)", re.IGNORECASE),
    re.compile(r"mcp server .*(failed|error|ignored)", re.IGNORECASE),
    re.compile(r"failed to load (mcp|plugin)", re.IGNORECASE),
)


class FindingsParseError(RuntimeError):
    """The final message does not contain a usable findings block."""


def is_noise(message: str) -> bool:
    return any(pattern.search(message) for pattern in NOISE_PATTERNS)


@dataclass
class ParseOutcome:
    events: list[dict] = field(default_factory=list)
    thread_id: str | None = None
    usage: dict = field(default_factory=dict)
    last_agent_message: str | None = None
    noise: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    invalid_lines: list[str] = field(default_factory=list)
    has_turn_completed: bool = False

    @property
    def jsonl_complete(self) -> bool:
        return (
            not self.invalid_lines
            and self.has_turn_completed
            and self.last_agent_message is not None
            and not self.errors
        )


def parse_events(text: str) -> ParseOutcome:
    outcome = ParseOutcome()
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            outcome.invalid_lines.append(line[:300])
            continue
        if not isinstance(event, dict):
            outcome.invalid_lines.append(line[:300])
            continue
        outcome.events.append(event)
        kind = event.get("type")
        if kind == "thread.started":
            thread_id = event.get("thread_id")
            if isinstance(thread_id, str):
                outcome.thread_id = thread_id
        elif kind == "turn.completed":
            outcome.has_turn_completed = True
            usage = event.get("usage")
            if isinstance(usage, dict):
                outcome.usage = usage
        elif kind == "item.completed":
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "agent_message":
                message = item.get("text")
                if isinstance(message, str) and message.strip():
                    outcome.last_agent_message = message
            elif item_type == "error":
                message = str(item.get("message") or "").strip()
                if not message:
                    continue
                if is_noise(message):
                    outcome.noise.append(message)
                else:
                    outcome.errors.append(message)
        elif kind == "error":
            message = str(event.get("message") or "").strip()
            if message:
                if is_noise(message):
                    outcome.noise.append(message)
                else:
                    outcome.errors.append(message)
    return outcome


def extract_findings(message: str) -> FindingsEnvelope:
    if not message or not message.strip():
        raise FindingsParseError("empty final message")
    matches = list(FINDINGS_FENCE.finditer(message))
    if not matches:
        raise FindingsParseError(
            "final message has no ```json:findings fenced block"
        )
    payload = matches[-1].group(1).strip()
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FindingsParseError(f"findings block is not valid JSON: {exc}") from exc
    if isinstance(data, dict):
        items = data.get("findings")
    elif isinstance(data, list):
        items = data
    else:
        items = None
    if not isinstance(items, list):
        raise FindingsParseError("findings block has no 'findings' array")
    findings: list[Finding] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise FindingsParseError(f"finding #{index} is not an object")
        try:
            finding = Finding.model_validate(item)
        except Exception as exc:  # pydantic ValidationError
            raise FindingsParseError(f"finding #{index} is invalid: {exc}") from exc
        # A model may claim its own finding is verified; it never is until a
        # human confirms it.  Force the review state, keep the rest.
        findings.append(
            finding.model_copy(update={"verification": Verification.unverified})
        )
    return FindingsEnvelope(findings=findings)


__all__ = [
    "FINDINGS_FENCE",
    "FindingsParseError",
    "NOISE_PATTERNS",
    "ParseOutcome",
    "extract_findings",
    "is_noise",
    "parse_events",
]
