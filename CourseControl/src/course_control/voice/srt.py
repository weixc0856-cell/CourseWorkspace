"""The one SRT parser used by every subtitle consumer.

QC, counting and rewriting all read the same file, so they share one parser.
Parsing is lenient: a block without a readable timestamp is skipped rather than
raised, because every caller here measures what it can read and reports the
rest.  Consumers that must fail hard validate the cue list afterwards.

Each cue carries both ``text`` (the body joined by newlines) and ``lines`` (the
body as a list) so callers do not need a second parser for the other shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from course_control.platform.media import MediaError
from course_control.content.timecode import TimecodeError, parse_srt_timestamp

TS_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def _ms(hours: str, minutes: str, seconds: str, millis: str) -> int:
    # SRT millis are commonly 3 digits but 1-2 digit variants exist in the wild.
    return (
        (int(hours) * 60 + int(minutes)) * 60 + int(seconds)
    ) * 1000 + int(millis.ljust(3, "0"))


def parse_srt(text: str) -> list[dict]:
    """Return cues as ``{index, start_ms, end_ms, text, lines}``; skip bad blocks."""
    cues: list[dict] = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        index: int | None = None
        if lines[0].isdigit():
            index = int(lines[0])
            lines = lines[1:]
        if not lines:
            continue
        match = TS_RE.search(lines[0])
        if match is None:
            continue
        body = lines[1:]
        cues.append(
            {
                "index": index if index is not None else len(cues) + 1,
                "start_ms": _ms(*match.groups()[:4]),
                "end_ms": _ms(*match.groups()[4:]),
                "text": "\n".join(body),
                "lines": body,
            }
        )
    return cues


@dataclass(frozen=True)
class SrtCue:
    index: int
    start_ms: int
    end_ms: int
    text: str


def parse_srt_strict(text: str) -> list[SrtCue]:
    """Parse the small SRT subset used by E6, with explicit failures."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise MediaError("SRT file is empty")
    cues: list[SrtCue] = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            raise MediaError(f"invalid SRT block: {block!r}")
        try:
            index = int(lines[0])
        except ValueError as exc:
            raise MediaError(f"invalid SRT cue index: {lines[0]!r}") from exc
        match = re.match(r"^(\S+)\s*-->\s*(\S+)$", lines[1])
        if not match:
            raise MediaError(f"invalid SRT time line: {lines[1]!r}")
        try:
            start_ms = parse_srt_timestamp(match.group(1))
            end_ms = parse_srt_timestamp(match.group(2))
        except TimecodeError as exc:
            raise MediaError(f"invalid SRT cue {index}: {exc}") from exc
        if end_ms <= start_ms:
            raise MediaError(f"SRT cue {index} ends before it starts")
        cues.append(SrtCue(index=index, start_ms=start_ms, end_ms=end_ms, text="\n".join(lines[2:])))
    return cues
