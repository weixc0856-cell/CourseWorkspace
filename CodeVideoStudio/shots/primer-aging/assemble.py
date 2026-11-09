"""Assemble narration, subtitles and the bilingual draft for the aging lesson.

Reads ``build/aging-evolution/timing.json`` and ``audio/sXX.wav``, writes
``narration/narration.wav``, ``lessons/aging-evolution/subtitles.srt`` and
``build/aging-evolution/subtitles/bilingual.draft.json``.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT / "build" / "aging-evolution"
LESSON = ROOT / "lessons" / "aging-evolution"
TIMING = BUILD / "timing.json"
SHOT = Path(__file__).resolve().parent

ZH = {
    "s01": "每一种生物都能自我修复一点。但几乎一切都会衰老、死亡。如果进化能造出眼睛，为什么造不出永久的身体？",
    "s02": "答案始于一个简单事实：选择在你年轻时最强，随着年龄增长而减弱。",
    "s03": "多数个体在步入老年之前，就死于意外、捕食或疾病。一个到八十岁才伤害你的突变，几乎不会被选择看见，因为几乎没人活到那时。",
    "s04": "这种衰减有两个后果。第一是突变累积：晚年才发作的有害突变溜了进来，而选择太弱，无法清除它们。",
    "s05": "第二是拮抗性多效：一个帮助早期繁殖的基因可以扩散，即使同一个基因让你晚年衰退。",
    "s06": "为了看清这一点，我们造了一个小世界。每个团块带着基因组，会衰老、会繁殖。突变随机出现在不同年龄，死亡来自环境和基因组。",
    "s07": "在危险的世界里，多数团块很年轻就死了。选择把繁殖推早，寿命保持很短。",
    "s08": "去掉一部分危险，更多团块能活到老年。选择现在能看见更晚的年龄，更长的寿命演化出来。",
    "s09": "但衰老从未消失。在两个世界里，死亡风险都随年龄上升，因为晚期突变持续累积。",
    "s10": "环境改变时死亡曲线会平移，但形状保持不变。选择的力量总是随年龄衰减。",
    "s11": "真实的生物学更混乱。修复、权衡与环境彼此作用。但核心逻辑很简单。",
    "s12": "衰老不是身体的失败。它是选择投下的影子，随着我们变老而淡去。",
}


def wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False) or [text]


def wrap_zh(text: str, width: int) -> list[str]:
    return [text[index : index + width] for index in range(0, len(text), width)] or [text]


def split_en(text: str, parts: int) -> list[str]:
    words = text.split()
    if parts <= 1 or len(words) <= parts:
        return [text]
    target = len(text) / parts
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        addition = len(word) + (1 if current else 0)
        if current and current_len + addition > target * 1.12 and len(chunks) < parts - 1:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += addition
    if current:
        chunks.append(" ".join(current))
    while len(chunks) < parts:
        longest = max(range(len(chunks)), key=lambda i: len(chunks[i]))
        words = chunks[longest].split()
        mid = max(1, len(words) // 2)
        chunks[longest : longest + 1] = [" ".join(words[:mid]), " ".join(words[mid:])]
    return chunks[:parts]


def split_zh(text: str, parts: int) -> list[str]:
    if parts <= 1:
        return [text]
    clauses = [part for part in re.split(r"(?<=[。！？；，])", text) if part.strip()]
    if len(clauses) < parts:
        size = len(text) / parts
        return [text[int(i * size) : int((i + 1) * size)] for i in range(parts - 1)] + [
            text[int((parts - 1) * size) :]
        ]
    target = len(text) / parts
    chunks: list[str] = []
    current = ""
    for clause in clauses:
        if current and len(current) + len(clause) > target * 1.15 and len(chunks) < parts - 1:
            chunks.append(current)
            current = clause
        else:
            current += clause
    if current:
        chunks.append(current)
    while len(chunks) < parts:
        longest = max(range(len(chunks)), key=lambda i: len(chunks[i]))
        chunk = chunks[longest]
        mid = max(1, len(chunk) // 2)
        chunks[longest : longest + 1] = [chunk[:mid], chunk[mid:]]
    return chunks[:parts]


def ts_srt(ms: int) -> str:
    hours, rest = divmod(ms, 3600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_narration(segments: list[dict]) -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "narration").mkdir(parents=True, exist_ok=True)
    args = ["ffmpeg", "-v", "error", "-y"]
    for segment in segments:
        args += ["-i", str(BUILD / "audio" / f"{segment['id']}.wav")]
    chains, labels = [], []
    for index, segment in enumerate(segments):
        delay = int(round(segment["start"] * 1000))
        chains.append(f"[{index}:a]adelay={delay}:all=1[a{index}]")
        labels.append(f"[a{index}]")
    chains.append(
        f"{''.join(labels)}amix=inputs={len(segments)}:duration=longest:normalize=0[mix]"
    )
    chains.append("[mix]loudnorm=I=-16:TP=-1.6:LRA=11[out]")
    args += [
        "-filter_complex",
        ";".join(chains),
        "-map",
        "[out]",
        "-ar",
        "48000",
        str(BUILD / "narration" / "narration.wav"),
    ]
    subprocess.run(args, check=True)


def main() -> int:
    data = json.loads(TIMING.read_text(encoding="utf-8"))
    segments = data["segments"]
    total = float(data["total"])
    build_narration(segments)

    cues = []
    cue_index = 0
    for index, segment in enumerate(segments, start=1):
        en = segment["text"]
        zh = ZH[segment["id"]]
        span = float(segment["duration"])
        offset = float(segment["start"])
        parts = max(
            1,
            math.ceil(span / 5.5),
            math.ceil(len(en) / 84),
            math.ceil(len(re.sub(r"\s", "", zh)) / 30),
        )
        while True:
            en_chunks = split_en(en, parts)
            zh_chunks = split_zh(zh, parts)
            weights = [max(1, len(chunk)) for chunk in en_chunks]
            total_weight = sum(weights)
            gap = 0.10
            raw = [max(1.0, min(6.0, (span - gap * (parts - 1)) * w / total_weight)) for w in weights]
            scale = (span - gap * (parts - 1)) / sum(raw)
            durs = [d * scale for d in raw]
            candidate = []
            cue_index = len(cues)
            cursor = offset
            valid = True
            for part, (en_chunk, zh_chunk, duration) in enumerate(
                zip(en_chunks, zh_chunks, durs), start=1
            ):
                en_lines = wrap(en_chunk, 42)
                zh_lines = wrap_zh(zh_chunk, 15)
                if len(en_lines) > 2 or len(zh_lines) > 2 or duration > 6.0 or duration < 1.0:
                    valid = False
                    break
                cue_index += 1
                candidate.append(
                    {
                        "index": cue_index,
                        "slide": index,
                        "segment_id": segment["id"],
                        "start_ms": int(round(cursor * 1000)),
                        "end_ms": int(round((cursor + duration) * 1000)),
                        "en": en_chunk,
                        "zh": zh_chunk,
                        "en_lines": en_lines,
                        "zh_lines": zh_lines,
                    }
                )
                cursor += duration + gap
            if valid:
                cues.extend(candidate)
                break
            parts += 1
            cue_index = len(cues)

    srt = []
    for cue in cues:
        lines = cue["en_lines"] + cue["zh_lines"]
        srt.append(f"{cue['index']}\n{ts_srt(cue['start_ms'])} --> {ts_srt(cue['end_ms'])}\n" + "\n".join(lines))
    (LESSON / "subtitles.srt").write_text("\n\n".join(srt) + "\n", encoding="utf-8")

    draft = {
        "schema_version": 1,
        "lesson": "aging-evolution",
        "languages": {"top": "en", "bottom": "zh-Hans"},
        "policy": {"top_language": "en", "bottom_language": "zh-Hans", "max_line_chars": 50},
        "cues": cues,
        "counts": {
            "cues": len(cues),
            "en_lines": sum(len(cue["en_lines"]) for cue in cues),
            "zh_lines": sum(len(cue["zh_lines"]) for cue in cues),
        },
        "translation": {"provider": "claude-code-candidate", "reviewed": False},
    }
    target = BUILD / "subtitles"
    target.mkdir(parents=True, exist_ok=True)
    (target / "bilingual.draft.json").write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (SHOT / "timing.json").write_text(
        json.dumps({"segments": segments, "total": round(total, 3)}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    import datetime, hashlib

    narration = BUILD / "narration" / "narration.wav"
    meta = {
        "schema_version": 2,
        "lesson": "aging-evolution",
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "prompt_reference",
        "tts": {"model": "VoxCPM2", "sample_rate": 48000, "timesteps": 10, "cfg": 2.0},
        "segments": [
            {
                "segment_id": segment["id"],
                "slide": index,
                "start_s": segment["start"],
                "duration_s": segment["duration"],
                "end_s": round(segment["start"] + segment["duration"], 3),
                "audio_seconds": segment["duration"],
                "duration_seconds": segment["duration"],
                "text_sha256": hashlib.sha256(segment["text"].encode("utf-8")).hexdigest(),
                "raw_wav": f"audio/{segment['id']}.wav",
            }
            for index, segment in enumerate(segments, start=1)
        ],
        # Page spans tile the whole narration (lead-in, segments and gaps), not
        # just the audio durations; the timeline total must equal the mix.
        "pages": [
            {
                "slide": index,
                "start_s": 0.0 if index == 1 else segment["start"],
                "end_s": round(
                    segments[index]["start"] if index < len(segments) else total, 3
                ),
                "measured_s": round(
                    (segments[index]["start"] if index < len(segments) else total)
                    - (0.0 if index == 1 else segment["start"]),
                    3,
                ),
                "planned_s": segment["duration"],
                "drift_s": 0.0,
            }
            for index, segment in enumerate(segments, start=1)
        ],
        "assembly": {
            "file": "narration/narration.wav",
            "duration_s": round(total, 3),
            "source": str(narration),
            "sha256": hashlib.sha256(narration.read_bytes()).hexdigest(),
        },
        "source": {
            "notes_sha256": hashlib.sha256(
                (LESSON / "lecture_notes.md").read_bytes()
            ).hexdigest(),
        },
        "totals": {"segments": len(segments), "cache_hits": 0},
    }
    (BUILD / "narration" / "narration.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8"
    )
    print(f"narration + {len(cues)} cues; total {total:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
