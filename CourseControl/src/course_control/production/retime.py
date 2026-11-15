"""Retime the beat sheet from a measured narration track.

One command, one source of truth: every narration segment belongs to exactly one
beat, and the beat durations are the measured span of its segments. A missing or
unknown segment fails instead of being guessed; the table is generated, never
hand-edited, so the next voice track cannot leave stale numbers behind.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


class RetimeError(ValueError):
    pass


@dataclass
class BeatTiming:
    id: str
    type: str
    claims: list[str]
    segment_ids: list[str]
    start_s: float
    end_s: float

    @property
    def seconds(self) -> float:
        return round(self.end_s - self.start_s, 3)


def load_narration(meta_path: Path) -> dict[str, dict]:
    if not meta_path.is_file():
        raise RetimeError(f"narration metadata not found: {meta_path}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RetimeError(f"invalid narration metadata {meta_path}: {exc}") from exc
    segments = meta.get("segments") or []
    if not segments:
        raise RetimeError(f"{meta_path}: no narration segments")
    by_id = {}
    for segment in segments:
        segment_id = segment.get("segment_id")
        if not segment_id:
            raise RetimeError(f"{meta_path}: a segment has no segment_id")
        by_id[str(segment_id)] = segment
    return by_id


def load_mapping(path: Path) -> dict:
    if not path.is_file():
        raise RetimeError(f"beat mapping not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RetimeError(f"invalid YAML in {path}: {exc}") from exc
    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        raise RetimeError(f"{path}: beats must be a non-empty list")
    return data


def compute(segments: dict[str, dict], mapping: dict) -> list[BeatTiming]:
    assigned: dict[str, str] = {}
    timings: list[BeatTiming] = []
    for beat in mapping["beats"]:
        beat_id = str(beat.get("id") or "")
        segment_ids = [str(item) for item in beat.get("segments") or []]
        if not beat_id:
            raise RetimeError("a beat has no id")
        if not segment_ids:
            raise RetimeError(f"beat {beat_id} has no segments; mapping is incomplete")
        unknown = [item for item in segment_ids if item not in segments]
        if unknown:
            raise RetimeError(f"beat {beat_id}: unknown segments {', '.join(unknown)}")
        for segment_id in segment_ids:
            if segment_id in assigned:
                raise RetimeError(
                    f"segment {segment_id} is assigned to both {assigned[segment_id]} and {beat_id}"
                )
            assigned[segment_id] = beat_id
        start = min(float(segments[item].get("start_s") or 0) for item in segment_ids)
        end = max(float(segments[item].get("end_s") or 0) for item in segment_ids)
        timings.append(
            BeatTiming(
                id=beat_id,
                type=str(beat.get("type") or ""),
                claims=[str(item) for item in beat.get("claims") or []],
                segment_ids=segment_ids,
                start_s=round(start, 3),
                end_s=round(end, 3),
            )
        )
    unassigned = sorted(set(segments) - set(assigned))
    if unassigned:
        raise RetimeError(f"segments not assigned to any beat: {', '.join(unassigned)}")
    return timings


def render_markdown(timings: list[BeatTiming], source: str) -> str:
    total = round(sum(item.seconds for item in timings), 3)
    lines = [
        "# T1-01 beat timing",
        "",
        f"- 由 `course-control retime` 生成；来源：`{source}`。不要手改。",
        f"- 合计 {total} s；每段标注 `measured({source})`。",
        "",
        "| beat | type | seconds | time_source | claims | segments |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in timings:
        lines.append(
            f"| {item.id} | {item.type} | {item.seconds} | measured({source}) | "
            f"{', '.join(item.claims) or '—'} | {', '.join(item.segment_ids)} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_retime(lesson_dir: Path, build_root: Path, mapping_path: Path, meta_path: Path) -> list[BeatTiming]:
    segments = load_narration(meta_path)
    mapping = load_mapping(mapping_path)
    timings = compute(segments, mapping)
    source = str(mapping.get("source") or meta_path.parent.parent.name)
    (lesson_dir / "authoring" / "beat-timing.md").write_text(
        render_markdown(timings, source), encoding="utf-8"
    )
    out = build_root / "retime"
    out.mkdir(parents=True, exist_ok=True)
    (out / "beat-timing.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": source,
                "beats": [
                    {
                        "id": item.id,
                        "type": item.type,
                        "claims": item.claims,
                        "segments": item.segment_ids,
                        "start_s": item.start_s,
                        "end_s": item.end_s,
                        "seconds": item.seconds,
                    }
                    for item in timings
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return timings
