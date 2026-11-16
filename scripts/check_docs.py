"""Keep the documentation map truthful.

One file owns the map (``docs/文档地图.yaml``); ``docs/README.md`` is generated
from it.  The check fails when a document is missing from the map, when a link
points nowhere, when a documented ``course-control`` subcommand does not exist,
or when a documented script path does not exist.  ``--write`` regenerates the
README; ``--selftest`` proves each rule can go red.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

MAP_NAME = "文档地图.yaml"
README_NAME = "README.md"
STATUS_LABEL = {
    "current": "现行",
    "superseded": "已取代",
    "record": "记录",
    "draft": "草案",
}
LAYER_ORDER = ("entry", "contract", "guide", "record")
LAYER_TITLE = {
    "entry": "入口",
    "contract": "现行契约",
    "guide": "现行指南",
    "record": "记录（不是指令）",
}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CMD_RE = re.compile(r"course-control\s+([a-z][a-z0-9-]*)(?:\s+([a-z][a-z0-9-]*))?")
# Executable paths are the command chain: they must exist.  Source-file
# references are checked separately as advisories, because records legitimately
# describe code that has since moved.
SCRIPT_RE = re.compile(
    r"(?<![\w/])((?:[A-Za-z0-9_.\-]+/)*scripts/[A-Za-z0-9_.\-/]+\.(?:py|ps1|mjs))(?![A-Za-z0-9])"
)
SOURCE_RE = re.compile(
    r"(?<![\w/])((?:RemotionStudio|MotionStudio|BlenderStudio|CodeVideoStudio|"
    r"CourseSlides|ReviewRunner|ContentQA|KnowledgeStudio|CourseControl|BrandIntro|"
    r"ScientificFigures|shared)/[A-Za-z0-9_.\-/]+\.(?:py|mjs|ts|tsx))(?![A-Za-z0-9])"
)
SKIP_LINK_PREFIX = ("http://", "https://", "mailto:", "#")
# A superseded document must say so in its own first screen.  "已并入" is the
# wording the merged reading-order note already uses.
SUPERSEDED_MARKERS = ("已取代", "已并入", "superseded")
PIPELINE_DOC = "生产流水线-阶段与中间交付物.md"


def load_map(docs: Path) -> dict:
    path = docs / MAP_NAME
    if not path.is_file():
        raise SystemExit(f"missing documentation map: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def markdown_files(docs: Path) -> list[str]:
    return sorted(str(p.relative_to(docs)).replace("\\", "/") for p in docs.rglob("*.md"))


def command_names() -> tuple[set[str], dict[str, set[str]]]:
    from course_control.cli import app

    names = set()
    for command in app.registered_commands:
        names.add(command.name or (command.callback.__name__.replace("_", "-") if command.callback else ""))
    groups: dict[str, set[str]] = {}
    for group in app.registered_groups:
        if not group.name:
            continue
        names.add(group.name)
        subs = set()
        if group.typer_instance is not None:
            for command in group.typer_instance.registered_commands:
                subs.add(
                    command.name
                    or (command.callback.__name__.replace("_", "-") if command.callback else "")
                )
        groups[group.name] = {sub for sub in subs if sub}
    return {name for name in names if name}, groups


def _doc_text(docs: Path) -> dict[str, str]:
    return {
        path: (docs / path).read_text(encoding="utf-8", errors="replace")
        for path in markdown_files(docs)
    }


def map_errors(docs: Path, data: dict) -> list[str]:
    errors: list[str] = []
    files = set(markdown_files(docs))
    listed: list[str] = []
    for entry in data.get("documents") or []:
        path = entry.get("path")
        if not path:
            errors.append("document entry without a path")
            continue
        listed.append(path)
        if path not in files:
            errors.append(f"map lists a missing document: {path}")
        if entry.get("layer") not in LAYER_ORDER:
            errors.append(f"{path}: layer must be one of {', '.join(LAYER_ORDER)}")
        if entry.get("status") not in STATUS_LABEL:
            errors.append(f"{path}: status must be one of {', '.join(STATUS_LABEL)}")
        if not str(entry.get("answers") or "").strip():
            errors.append(f"{path}: answers is empty; it must state the one question it answers")
        if entry.get("status") == "superseded" and not entry.get("superseded_by"):
            errors.append(f"{path}: superseded without superseded_by")
    duplicates = sorted({path for path in listed if listed.count(path) > 1})
    for path in duplicates:
        errors.append(f"map lists the document more than once: {path}")
    for path in sorted(files - set(listed)):
        errors.append(f"document is not in the map: {path}")
    return errors


def structure_errors(docs: Path, data: dict) -> list[str]:
    """The map's own shape: layers, questions and superseded records.

    A map that lists a document but routes a question elsewhere is two truths
    again, so a question must point at a registered current document.  A
    superseded file must carry its status banner, otherwise a reader who opens
    it directly has no way to know it is not an instruction.
    """
    errors: list[str] = []
    layers = data.get("layers") or {}
    missing = [name for name in LAYER_ORDER if not str(layers.get(name) or "").strip()]
    extra = sorted(str(name) for name in layers if name not in LAYER_ORDER)
    if missing:
        errors.append(
            "layers must describe " + ", ".join(LAYER_ORDER)
            + "; missing or empty: " + ", ".join(missing)
        )
    if extra:
        errors.append("layers names an unknown layer: " + ", ".join(extra))
    registered = {
        str(entry.get("path")): entry for entry in data.get("documents") or []
    }
    for item in data.get("questions") or []:
        if not isinstance(item, dict):
            errors.append("question entry is not an object")
            continue
        question = str(item.get("question") or "?")
        path = str(item.get("path") or "")
        if not path:
            errors.append(f"question '{question}' names no document")
            continue
        entry = registered.get(path)
        if entry is None:
            errors.append(f"question '{question}' points at an unlisted document: {path}")
        elif entry.get("status") != "current":
            errors.append(f"question '{question}' points at a non-current document: {path}")
    for entry in data.get("documents") or []:
        path = str(entry.get("path") or "")
        for successor in entry.get("superseded_by") or []:
            if str(successor) not in registered:
                errors.append(f"{path}: superseded_by target is not in the map: {successor}")
        if entry.get("status") != "superseded":
            continue
        target = docs / path
        if not target.is_file():
            continue  # map_errors reports the missing document
        head = target.read_text(encoding="utf-8", errors="replace")[:600].lower()
        if not any(marker in head for marker in SUPERSEDED_MARKERS):
            errors.append(
                f"{path}: superseded document has no status banner in its first 600 characters"
            )
    return errors


def _command_exists(command: str, commands: set[str], groups: dict[str, set[str]]) -> bool:
    parts = command.split()
    if not parts:
        return False
    if parts[0] in groups:
        return len(parts) > 1 and parts[1] in groups[parts[0]]
    return len(parts) == 1 and parts[0] in commands


def pipeline_data(docs: Path) -> tuple[dict | None, str | None]:
    path = docs / PIPELINE_DOC
    if not path.is_file():
        return None, f"pipeline document is missing: {PIPELINE_DOC}"
    text = path.read_text(encoding="utf-8", errors="replace")
    block_lines: list[str] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if not inside and stripped == "```yaml":
            inside = True
            block_lines = []
            continue
        if inside and stripped == "```":
            inside = False
            try:
                block = yaml.safe_load(chr(10).join(block_lines))
            except yaml.YAMLError:
                continue
            if isinstance(block, dict) and isinstance(block.get("pipeline"), dict):
                return block["pipeline"], None
            continue
        if inside:
            block_lines.append(line)
    return None, f"{PIPELINE_DOC} has no machine-readable `pipeline:` yaml block"


def pipeline_errors(
    docs: Path,
    commands: set[str],
    groups: dict[str, set[str]] | None = None,
) -> list[str]:
    """The stage table is a command chain, not prose.

    Every stage names at least one command the CLI really registers and one
    intermediate artifact; the G0-G7 production gates must all be reachable
    from some stage.  S1 (research) carries no G gate by design, so the rule
    is coverage of every gate, not one gate per stage.
    """
    data, problem = pipeline_data(docs)
    if problem:
        return [problem]
    groups = groups or {}
    errors: list[str] = []
    stages = [item for item in data.get("stages") or [] if isinstance(item, dict)]
    ids = [str(item.get("id") or "") for item in stages]
    expected = [f"S{index}" for index in range(10)]
    if ids != expected:
        errors.append(
            "pipeline stages must be S0..S9 exactly once, in order; got "
            + (", ".join(ids) or "none")
        )
    declared_gates = [str(item) for item in data.get("contract_gates") or []]
    expected_gates = [f"G{index}" for index in range(8)]
    if declared_gates != expected_gates:
        errors.append(
            "pipeline contract_gates must be G0..G7; got "
            + (", ".join(declared_gates) or "none")
        )
    used_gates: set[str] = set()
    for stage in stages:
        sid = str(stage.get("id") or "?")
        for key in ("name", "gate"):
            if not str(stage.get(key) or "").strip():
                errors.append(f"{sid}: {key} is empty")
        stage_commands = [str(item) for item in stage.get("commands") or []]
        if not stage_commands:
            errors.append(f"{sid}: names no command")
        for command in stage_commands:
            if not _command_exists(command, commands, groups):
                errors.append(f"{sid}: unknown command 'course-control {command}'")
        if not stage.get("artifacts"):
            errors.append(f"{sid}: names no intermediate artifact")
        for gate in stage.get("contract_gates") or []:
            gate = str(gate)
            if gate not in expected_gates:
                errors.append(f"{sid}: unknown contract gate {gate}")
            used_gates.add(gate)
    missing_gates = [gate for gate in expected_gates if gate not in used_gates]
    if missing_gates:
        errors.append(
            "no stage maps to contract gate(s): " + ", ".join(missing_gates)
        )
    return errors


def link_errors(docs: Path) -> list[str]:
    errors: list[str] = []
    for path, text in _doc_text(docs).items():
        for match in LINK_RE.finditer(text):
            target = match.group(1).split("#")[0].strip()
            if not target or target.startswith(SKIP_LINK_PREFIX) or target.startswith("<"):
                continue
            if not (docs / path).parent.joinpath(target).exists():
                errors.append(f"{path}: broken link -> {target}")
    return errors


def command_errors(
    docs: Path,
    commands: set[str],
    groups: dict[str, set[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    groups = groups or {}
    for path, text in _doc_text(docs).items():
        for match in CMD_RE.finditer(text):
            name, sub = match.group(1), match.group(2)
            if name not in commands:
                errors.append(f"{path}: unknown subcommand 'course-control {name}'")
            elif name in groups and sub and sub not in groups[name]:
                errors.append(
                    f"{path}: unknown subcommand 'course-control {name} {sub}'"
                )
    return errors


def current_paths(data: dict) -> set[str]:
    return {
        entry["path"]
        for entry in data.get("documents") or []
        if entry.get("status") == "current" and entry.get("layer") in {"entry", "contract", "guide"}
    }


REPO_ROOTS = (
    "scripts/", "RemotionStudio/", "MotionStudio/", "BlenderStudio/", "CodeVideoStudio/",
    "CourseSlides/", "ReviewRunner/", "ContentQA/", "KnowledgeStudio/", "CourseControl/",
    "shared/", "BrandIntro/", "ScientificFigures/",
)


def script_errors(docs: Path, repo_root: Path, data: dict) -> list[str]:
    errors: list[str] = []
    wanted = current_paths(data)
    for path, text in _doc_text(docs).items():
        if path not in wanted:
            continue
        for match in SCRIPT_RE.finditer(text):
            target = match.group(1).rstrip(".")
            if not target.startswith(REPO_ROOTS):
                continue  # e.g. a generic "blender/scripts" layout inside a temp project
            if not (repo_root / target).exists():
                errors.append(f"{path}: documented command path does not exist: {target}")
    return errors


def path_advisories(docs: Path, repo_root: Path, data: dict) -> list[str]:
    advisories: list[str] = []
    wanted = current_paths(data)
    for path, text in _doc_text(docs).items():
        if path not in wanted:
            continue
        for match in SOURCE_RE.finditer(text):
            target = match.group(1).rstrip(".")
            if not (repo_root / target).exists():
                advisories.append(f"{path}: stale source reference -> {target}")
    return advisories


def render_readme(data: dict) -> str:
    docs = {entry["path"]: entry for entry in data.get("documents") or []}
    lines = [
        "# 文档地图",
        "",
        "> 本文件由 `scripts/check_docs.py --write` 从 `文档地图.yaml` 生成，不要手改。",
        f"> 最后更新：{data.get('updated', '')}",
        "",
        "先读四份，其余按问题查表。**记录层不是指令**：审计、评估、交付记录与草案只说明当时看到了什么。",
        "",
        "## 0. 先读四份",
        "",
    ]
    first = ["PRD.md", "ARCHITECTURE.md", "课程生产统一契约V1.md", "生产流水线-阶段与中间交付物.md"]
    for index, path in enumerate(first, start=1):
        entry = docs.get(path)
        if entry:
            lines.append(f"{index}. [{path}]({path}) —— {entry['answers']}")
    lines += ["", "## 1. 按问题找文档", "", "| 问题 | 文档 | 只回答 |", "| --- | --- | --- |"]
    for item in data.get("questions") or []:
        path = item["path"]
        entry = docs.get(path, {})
        lines.append(f"| {item['question']} | [{path}]({path}) | {entry.get('answers', '')} |")
    for layer in LAYER_ORDER:
        entries = [e for e in data.get("documents") or [] if e.get("layer") == layer]
        if not entries:
            continue
        lines += ["", f"## {LAYER_ORDER.index(layer) + 2}. {LAYER_TITLE[layer]}", ""]
        current = [e for e in entries if e.get("status") == "current"]
        archived = [e for e in entries if e.get("status") != "current"]
        if layer == "entry":
            current = [e for e in current if e["path"] != README_NAME]
        for entry in sorted(current, key=lambda e: e["path"]):
            lines.append(f"- [{entry['path']}]({entry['path']})：{entry['answers']}")
        if archived:
            lines += ["", "**以下不是现行规范，不要照做：**", ""]
            for entry in sorted(archived, key=lambda e: e["path"]):
                status = STATUS_LABEL.get(entry.get("status"), entry.get("status"))
                suffix = f"（{status}"
                if entry.get("superseded_by"):
                    suffix += " → " + "、".join(entry["superseded_by"])
                suffix += "）"
                lines.append(f"- [{entry['path']}]({entry['path']})：{entry['answers']}{suffix}")
    lines += [
        "",
        "## 6. 写新文档的规则",
        "",
        "1. 先在本文件对应的 `文档地图.yaml` 登记它的唯一职责；写不出“只回答一个问题”，就不要新建。",
        "2. 与现有文档重叠时，在开头写明“补充/取代了哪一份”，把旧文件标为 `superseded`，并指向新文件。",
        "3. 一次性记录（审计、评估、复盘、交付记录）放记录层，不进入现行契约或指南。",
        "4. 改动后跑 `uv run --project CourseControl python scripts/check_docs.py --write`，再跑检查。",
        "",
    ]
    return "\n".join(lines)


def check(
    docs: Path,
    repo_root: Path,
    commands: set[str],
    groups: dict[str, set[str]] | None = None,
) -> list[str]:
    data = load_map(docs)
    errors = map_errors(docs, data)
    errors += structure_errors(docs, data)
    errors += pipeline_errors(docs, commands, groups)
    errors += link_errors(docs)
    errors += command_errors(docs, commands, groups)
    errors += script_errors(docs, repo_root, data)
    readme = docs / README_NAME
    expected = render_readme(data)
    if not readme.is_file() or readme.read_text(encoding="utf-8") != expected:
        errors.append("docs/README.md is out of date; run check_docs.py --write")
    return errors


def _selftest_stages() -> list[dict]:
    return [
        {
            "id": f"S{index}",
            "name": f"stage {index}",
            "commands": ["validate"],
            "artifacts": ["artifact.md"],
            "gate": "auto",
            "contract_gates": [f"G{index % 8}"],
        }
        for index in range(10)
    ]


def _selftest_pipeline_doc(stages: list[dict] | None = None) -> str:
    payload = {
        "pipeline": {
            "contract_gates": [f"G{index}" for index in range(8)],
            "stages": _selftest_stages() if stages is None else stages,
        }
    }
    lines = ["# pipeline selftest", "", "```yaml"]
    lines += yaml.safe_dump(payload, allow_unicode=True).splitlines()
    lines += ["```", ""]
    return chr(10).join(lines)


def selftest() -> int:
    root = Path(tempfile.mkdtemp(prefix="docs-check-"))
    try:
        docs = root / "docs"
        docs.mkdir()
        (root / "scripts").mkdir()
        (root / "scripts" / "check_docs.py").write_text("", encoding="utf-8")
        base = {
            "version": 1,
            "updated": "2026-11-16",
            "layers": {name: name for name in LAYER_ORDER},
            "questions": [],
            "documents": [
                {"path": "README.md", "layer": "entry", "status": "current", "answers": "map"},
                {"path": "ok.md", "layer": "guide", "status": "current", "answers": "a question"},
                {
                    "path": PIPELINE_DOC,
                    "layer": "contract",
                    "status": "current",
                    "answers": "the command chain",
                },
            ],
        }

        def write_map(data: dict) -> None:
            (docs / MAP_NAME).write_text(
                yaml.safe_dump(data, allow_unicode=True), encoding="utf-8"
            )
            (docs / README_NAME).write_text(render_readme(data), encoding="utf-8")

        (docs / "ok.md").write_text("see [ok](ok.md)" + chr(10), encoding="utf-8")
        (docs / PIPELINE_DOC).write_text(_selftest_pipeline_doc(), encoding="utf-8")
        write_map(base)
        if check(docs, root, {"validate"}, {}):
            print("selftest FAIL: a clean documentation tree was rejected")
            return 1

        (docs / "new.md").write_text("new" + chr(10), encoding="utf-8")
        if not any("not in the map" in e for e in check(docs, root, {"validate"})):
            print("selftest FAIL: an unlisted document was accepted")
            return 1
        (docs / "new.md").unlink()

        (docs / "ok.md").write_text("see [gone](gone.md)" + chr(10), encoding="utf-8")
        if not any("broken link" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a broken link was accepted")
            return 1
        (docs / "ok.md").write_text("run `course-control nope`" + chr(10), encoding="utf-8")
        if not any("unknown subcommand" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: an unknown subcommand was accepted")
            return 1
        (docs / "ok.md").write_text("run `scripts/missing.py`" + chr(10), encoding="utf-8")
        if not any("does not exist" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a missing script path was accepted")
            return 1
        (docs / "ok.md").write_text("ok" + chr(10), encoding="utf-8")
        (docs / README_NAME).write_text("stale" + chr(10), encoding="utf-8")
        if not any("out of date" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a stale README was accepted")
            return 1
        write_map(base)

        unlisted = dict(base, questions=[{"question": "q", "path": "missing.md"}])
        write_map(unlisted)
        if not any("unlisted document" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a question pointing at an unlisted document was accepted")
            return 1
        write_map(base)

        bad_layers = dict(base, layers={"entry": "only one layer"})
        write_map(bad_layers)
        if not any("layers must describe" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a shortened layer list was accepted")
            return 1
        write_map(base)

        old = dict(
            base,
            documents=base["documents"]
            + [
                {
                    "path": "old.md",
                    "layer": "guide",
                    "status": "superseded",
                    "answers": "old",
                    "superseded_by": ["ok.md"],
                }
            ],
        )
        (docs / "old.md").write_text("old text" + chr(10), encoding="utf-8")
        write_map(old)
        if not any("no status banner" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a superseded document without a banner was accepted")
            return 1
        (docs / "old.md").write_text("> 状态：已取代" + chr(10), encoding="utf-8")
        if any("no status banner" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a superseded status banner was not accepted")
            return 1
        (docs / "old.md").unlink()
        write_map(base)

        stages = _selftest_stages()
        (docs / PIPELINE_DOC).write_text(
            _selftest_pipeline_doc(stages[:-1]), encoding="utf-8"
        )
        if not any("S0..S9" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a pipeline missing a stage was accepted")
            return 1
        stages = _selftest_stages()
        stages[4]["commands"] = ["storyboard-pages"]
        (docs / PIPELINE_DOC).write_text(
            _selftest_pipeline_doc(stages), encoding="utf-8"
        )
        if not any("unknown command" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a pipeline naming an unknown command was accepted")
            return 1
        stages = _selftest_stages()
        stages[4]["contract_gates"] = []
        stages[5]["contract_gates"] = []
        (docs / PIPELINE_DOC).write_text(
            _selftest_pipeline_doc(stages), encoding="utf-8"
        )
        if not any("no stage maps to contract gate" in e for e in check(docs, root, {"validate"}, {})):
            print("selftest FAIL: a pipeline with an unreachable gate was accepted")
            return 1
        (docs / PIPELINE_DOC).write_text(_selftest_pipeline_doc(), encoding="utf-8")

        print("docs map selftest PASS")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", type=Path, default=Path("docs"))
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    docs = args.docs.resolve()
    repo_root = args.workspace.resolve()
    data = load_map(docs)
    if args.write:
        (docs / README_NAME).write_text(render_readme(data), encoding="utf-8")
        print(f"wrote {docs / README_NAME}")
        return 0
    commands, groups = command_names()
    errors = check(docs, repo_root, commands, groups)
    if errors:
        print(f"{len(errors)} documentation problem(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    pipeline, problem = pipeline_data(docs)
    if problem is None:
        stages = [
            item for item in pipeline.get("stages") or [] if isinstance(item, dict)
        ]
        print(f"pipeline ok ({len(stages)} stages)")
    print(f"docs map ok ({len(data.get('documents') or [])} documents)")
    advisories = path_advisories(docs, repo_root, data)
    if advisories:
        print(f"advisory: {len(advisories)} stale source reference(s) in current documents")
        for line in advisories[:12]:
            print(f"  - {line}")
        if len(advisories) > 12:
            print(f"  ... and {len(advisories) - 12} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
