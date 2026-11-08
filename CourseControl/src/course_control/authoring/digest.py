"""Deterministic source digest with stable citation refs (R1-5A)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from .ingest import sha256_text
from .models import DigestSection, SourceDigest, SourceEntry, SourcesFile

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sections_for(source: SourceEntry, text: str) -> list[DigestSection]:
    lines = text.splitlines()
    counters = [0] * 7
    sections: list[DigestSection] = []
    current: dict | None = None

    def flush(end_line: int) -> None:
        nonlocal current
        if current is None:
            return
        body = "\n".join(lines[current["start"] - 1 : end_line - 1]).strip()
        if not body:
            current = None
            return
        sections.append(
            DigestSection(
                ref=current["ref"],
                source_id=source.id,
                heading=current["heading"],
                level=current["level"],
                ordinal=current["ordinal"],
                line_start=current["start"],
                line_end=end_line - 1,
                text_sha256=sha256_text(body),
                excerpt=re.sub(r"\s+", " ", body)[:240],
            )
        )
        current = None

    ordinal = 0
    for number, line in enumerate(lines, start=1):
        match = HEADING.match(line)
        if not match:
            continue
        flush(number)
        level = len(match.group(1))
        counters[level] += 1
        for deeper in range(level + 1, 7):
            counters[deeper] = 0
        ordinal += 1
        ref = f"{source.id}-" + ".".join(str(counters[i]) for i in range(1, level + 1))
        current = {
            "ref": ref,
            "heading": match.group(2).strip(),
            "level": level,
            "ordinal": ordinal,
            "start": number,
        }
    flush(len(lines) + 1)

    if not sections:
        body = text.strip()
        if body:
            sections.append(
                DigestSection(
                    ref=f"{source.id}-1",
                    source_id=source.id,
                    heading=source.title or source.id,
                    level=1,
                    ordinal=1,
                    line_start=1,
                    line_end=max(1, len(lines)),
                    text_sha256=sha256_text(body),
                    excerpt=re.sub(r"\s+", " ", body)[:240],
                )
            )
    return sections


def _digest_markdown(digest: SourceDigest) -> str:
    lines = [f"# Source digest: {digest.lesson}", "", f"- generated_at: {digest.generated_at}", ""]
    lines.append("| id | kind | title | origin | sha256 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for source in digest.sources:
        lines.append(
            f"| {source.id} | {source.kind} | {source.title} | {source.origin} | `{source.sha256[:12]}` |"
        )
    lines.append("")
    for section in digest.sections:
        lines.append("## " + section.ref + " · " + section.heading)
        lines.append("")
        lines.append(
            f"- source: {section.source_id}; level: {section.level}; "
            f"lines: {section.line_start}-{section.line_end}"
        )
        lines.append("")
        lines.append(section.excerpt)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_digest(lesson_dir: Path) -> SourceDigest:
    lesson_dir = lesson_dir.resolve()
    authoring = lesson_dir / "authoring"
    manifest_path = authoring / "sources.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"sources.yaml not found: {manifest_path}")
    import yaml

    manifest = SourcesFile.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    )
    sections: list[DigestSection] = []
    for source in manifest.sources:
        path = lesson_dir / source.local_path
        if not path.is_file():
            raise FileNotFoundError(f"source body not found: {path}")
        text = path.read_text(encoding="utf-8")
        actual = sha256_text(text)
        if actual != source.sha256:
            raise ValueError(f"{source.id}: sha256 mismatch; re-ingest or update sources.yaml")
        sections.extend(_sections_for(source, text))

    digest = SourceDigest(
        lesson=lesson_dir.name,
        generated_at=_now(),
        sources=manifest.sources,
        sections=sections,
    )
    target_json = authoring / "source-digest.json"
    target_md = authoring / "source-digest.md"
    target_json.write_text(
        json.dumps(digest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    target_md.write_text(_digest_markdown(digest), encoding="utf-8")
    return digest


def load_digest(path: Path) -> SourceDigest:
    return SourceDigest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def digest_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
