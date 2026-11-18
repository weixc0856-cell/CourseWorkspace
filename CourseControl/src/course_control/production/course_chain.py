"""One versioned course-plan chain shared by audit and production.

The chain answers one question: does the lesson being built belong to the
episode the plan declares, with the same card, evidence and durations?

It is deliberately structural. Topic fit is a human decision made on the
static storyboard page; this module only guarantees that the thing a human
signed is the thing production builds. The plan is the only list of episode
slots. The card is the only place an episode's title, home section and
evidence live. A lesson is bound by declaring ``course_id`` and
``episode_id``; nothing is inferred from the directory name.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


EPISODE_ID = re.compile(r"\bT(?:[1-9]|1[0-4])-(?:\d{2}|H\d{2})\b")
CURRICULUM_BLOCK = re.compile(r"```yaml\s+curriculum\s*\n(.*?)```", re.S)
DETAIL_ROW = re.compile(
    r"^\|\s*(T\d+-\d{2})\s*\|\s*([^|]+?)\s*\|\s*(\d+(?:\.\d+)*)[^|]*"
    r"\|\s*[^|]*?\|\s*(\d+)\s*\|$",
    re.M,
)


class CourseChainError(RuntimeError):
    """A course-bound lesson cannot prove one plan/card/content identity."""


@dataclass
class ChainResult:
    course_id: str | None = None
    plan: Path | None = None
    expected_episode_count: int | None = None
    discovered_episode_count: int | None = None
    lesson_slug: str | None = None
    episode_id: str | None = None
    errors: list[str] = field(default_factory=list)
    fingerprint: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _normalized(value: object) -> str:
    return " ".join(str(value).lower().split())


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _require_same_number(
    label: str,
    values: list[tuple[str, object]],
    errors: list[str],
) -> None:
    numbers = [(name, _number(value)) for name, value in values]
    missing = [name for name, value in numbers if value is None]
    if missing:
        errors.append(f"{label} missing from: {missing}")
        return
    baseline_name, baseline = numbers[0]
    for name, value in numbers[1:]:
        if abs(float(value) - float(baseline)) > 0.01:
            errors.append(
                f"{label} drift: {name}={value:g} != "
                f"{baseline_name}={float(baseline):g}"
            )


def _require_duration_contract(card: dict, lesson: dict, claims: dict, errors: list[str]) -> None:
    duration = lesson.get("duration") or {}
    if not isinstance(duration, dict):
        errors.append("lesson.yaml duration must be a mapping")
        return
    _require_same_number(
        "target duration",
        [
            ("card.target_seconds", card.get("target_seconds")),
            ("lesson.duration.target_seconds", duration.get("target_seconds")),
            ("episode.spec.target_seconds", claims.get("target_seconds")),
        ],
        errors,
    )
    _require_same_number(
        "minimum duration",
        [
            ("lesson.duration.min_seconds", duration.get("min_seconds")),
            ("episode.spec.min_seconds", claims.get("min_seconds")),
        ],
        errors,
    )
    _require_same_number(
        "maximum duration",
        [
            ("lesson.duration.max_seconds", duration.get("max_seconds")),
            ("episode.spec.max_seconds", claims.get("max_seconds")),
        ],
        errors,
    )


def _read_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def default_chain_config() -> Path:
    """Return the repository chain config, with a fail-closed test override."""
    override = os.environ.get("COURSEWORKSPACE_CHAIN_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return (Path(__file__).resolve().parents[4] / "config" / "course-chain.yaml").resolve()


def project_course_config(root: Path, course_id: str) -> dict | None:
    """Read the course contract from ``projects/<course_id>/project.yaml``.

    The program repository serves many subjects; the plan, card directory,
    claim index, voice profile and forbidden terms belong to the course
    project in the content root, not to a per-course block in the repo config.
    """
    path = Path(root) / "projects" / course_id / "project.yaml"
    if not path.is_file():
        return None
    from course_control.delivery.project import load_project

    spec = load_project(path)
    if spec.project.mode != "course" or spec.production.course is None:
        return None
    course = spec.production.course
    if not course.plan:
        raise ValueError(f"{path}: production.course.plan is required")
    return {
        "expected_episode_count": course.expected_episode_count
        or course.lesson_count.target,
        "plan": course.plan,
        "cards_dir": course.cards_dir
        or f"runtime/course-content/{course_id}/episodes",
        "lessons_root": "lessons",
        "forbidden_lesson_slugs": dict(course.forbidden_lesson_slugs or {}),
        "forbidden_slide_terms": list(course.forbidden_slide_terms or []),
        "claim_index": course.claim_index,
        "voice_profile": course.voice_profile,
    }


def resolve_chain_root(workspace: Path, lesson_dir: Path) -> Path:
    """The content root that owns the lesson and its course plan.

    The build workspace is the program repository; lessons and plans live in
    the content root. Resolving the plan against the workspace made every
    bound lesson fail even when the content root was correct.
    """
    workspace = Path(workspace).resolve()
    lesson_dir = Path(lesson_dir).resolve()
    try:
        from course_control.platform.workspace_layout import content_root

        configured: Path | None = Path(content_root(workspace)).resolve()
    except Exception:  # pragma: no cover - defensive, layout is optional
        configured = None
    candidates: list[Path] = []
    if configured is not None:
        candidates.append(configured)
    if len(lesson_dir.parents) > 1:
        candidates.append(lesson_dir.parents[1])
    for candidate in candidates:
        if candidate == lesson_dir or candidate in lesson_dir.parents:
            return candidate
    return lesson_dir.parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finish(
    result: ChainResult, content_root: Path, artifacts: dict[str, Path]
) -> ChainResult:
    hashes: dict[str, str] = {}
    for label, path in sorted(artifacts.items()):
        candidate = Path(path)
        if not candidate.is_file():
            continue
        try:
            key = candidate.resolve().relative_to(content_root).as_posix()
        except ValueError:
            # The chain config lives in the program repository, not the
            # content root. Hashing its content is enough; putting the absolute
            # path in the fingerprint would make every signature machine-bound.
            key = label
        hashes[key] = _sha256(candidate)
    payload = json.dumps(hashes, sort_keys=True, ensure_ascii=False).encode("utf-8")
    result.artifacts = hashes
    result.fingerprint = hashlib.sha256(payload).hexdigest() if hashes else None
    return result


def expand_episode_ids(plan_text: str, errors: list[str]) -> tuple[list[str], dict[str, int]]:
    """Expand the machine-readable curriculum block into unique episode slots.

    The block is the only list of slots. Module counts, numbering ranges and
    the T11 helmet sub-range are data, not special cases in code.
    """
    match = CURRICULUM_BLOCK.search(plan_text)
    if match is None:
        errors.append("course plan has no ```yaml curriculum``` block")
        return [], {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        errors.append(f"curriculum block is not valid YAML: {exc}")
        return [], {}
    modules = data.get("modules") if isinstance(data, dict) else None
    if not isinstance(modules, list) or not modules:
        errors.append("curriculum block needs a non-empty modules list")
        return [], {}

    ids: list[str] = []
    counts: dict[str, int] = {}
    for module in modules:
        if not isinstance(module, dict):
            errors.append("curriculum module must be a mapping")
            continue
        module_id = str(module.get("id") or "").strip()
        count = int(module.get("count") or 0)
        if not module_id or count <= 0:
            errors.append(f"curriculum module {module!r} needs id and positive count")
            continue
        ranges = module.get("ranges")
        module_ids: list[str] = []
        if isinstance(ranges, list) and ranges:
            for item in ranges:
                if not isinstance(item, dict):
                    errors.append(f"{module_id}: range must be a mapping")
                    continue
                prefix = str(item.get("prefix") or "")
                first = int(item.get("from") or 1)
                last = int(item.get("to") or 0)
                if not prefix or last < first:
                    errors.append(f"{module_id}: range needs prefix and from <= to")
                    continue
                module_ids.extend(f"{prefix}{number:02d}" for number in range(first, last + 1))
        else:
            module_ids = [f"{module_id}-{number:02d}" for number in range(1, count + 1)]
        if len(module_ids) != count:
            errors.append(
                f"{module_id}: block expands to {len(module_ids)} ids, declared count {count}"
            )
        ids.extend(module_ids)
        counts[module_id] = count

    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        errors.append(f"curriculum block repeats episode ids: {duplicates}")
    return ids, counts


def _table_module_counts(plan_text: str) -> dict[str, int]:
    """Read the human module table, used only to detect prose drift."""
    counts: dict[str, int] = {}
    for line in plan_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip().strip("*").strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.fullmatch(r"T(?:[1-9]|1[0-4])", cells[0]):
            continue
        try:
            count = int(cells[-1])
        except ValueError:
            continue
        module = cells[0]
        if module in counts and counts[module] != count:
            counts[module] = -1
        else:
            counts[module] = count
    return counts


def _detail_row(plan_text: str, episode_id: str) -> dict | None:
    for match in DETAIL_ROW.finditer(plan_text):
        if match.group(1) != episode_id:
            continue
        return {
            "episode": match.group(1),
            "title": match.group(2).strip(),
            "section": match.group(3),
            "minutes": int(match.group(4)),
        }
    return None


def _find_lesson(root: Path, lessons_root: str, episode_id: str) -> Path | None:
    base = root / lessons_root
    if not base.is_dir():
        return None
    for lesson_file in sorted(base.glob("*/lesson.yaml")):
        data = _read_yaml(lesson_file)
        if str(data.get("episode_id") or "") == episode_id:
            return lesson_file.parent
    return None


def _check_forbidden_slugs(
    root: Path,
    lessons_root: str,
    forbidden: dict[str, str],
    errors: list[str],
) -> None:
    for slug, episode_id in forbidden.items():
        duplicate = root / lessons_root / str(slug)
        if duplicate.exists():
            errors.append(
                f"forbidden duplicate lesson directory exists: {duplicate} "
                f"(use the lesson bound to {episode_id})"
            )


def check_course_chain(
    content_root: Path,
    *,
    config_path: Path,
    course_id: str = "automotive-aerodynamics",
    episode_id: str | None = None,
    lesson_dir: Path | None = None,
) -> ChainResult:
    root = Path(content_root).resolve()
    config_path = Path(config_path).resolve()
    result = ChainResult(course_id=course_id, episode_id=episode_id)
    artifacts: dict[str, Path] = {"course_chain_config": config_path}
    if not config_path.is_file():
        result.errors.append(f"course chain config missing: {config_path}")
        return _finish(result, root, artifacts)
    data = _read_yaml(config_path)
    try:
        course = project_course_config(root, course_id)
    except Exception as exc:  # noqa: BLE001 - a broken project must block
        result.errors.append(f"invalid course project for {course_id!r}: {exc}")
        return _finish(result, root, artifacts)
    if course is None:
        course = (data.get("courses") or {}).get(course_id)
    if not isinstance(course, dict):
        result.errors.append(
            f"course {course_id!r} has no projects/{course_id}/project.yaml "
            f"and no entry in {config_path}"
        )
        return _finish(result, root, artifacts)

    expected = int(course.get("expected_episode_count") or 0)
    result.expected_episode_count = expected
    lessons_root = str(course.get("lessons_root") or "lessons")
    forbidden = {
        str(slug): str(episode)
        for slug, episode in (course.get("forbidden_lesson_slugs") or {}).items()
    }
    _check_forbidden_slugs(root, lessons_root, forbidden, result.errors)

    plan_rel = str(course.get("plan") or "").strip()
    if not plan_rel:
        result.errors.append(f"course {course_id!r} declares no plan file")
        return _finish(result, root, artifacts)
    plan = (root / plan_rel).resolve()
    if not plan.is_file():
        result.errors.append(
            f"no {expected}-episode plan found under {root} "
            f"(expected {plan_rel}); the chain is blocked instead of guessing a plan"
        )
        return _finish(result, root, artifacts)

    result.plan = plan
    artifacts["course_plan"] = plan
    plan_text = plan.read_text(encoding="utf-8")
    ids, block_counts = expand_episode_ids(plan_text, result.errors)
    result.discovered_episode_count = len(ids)
    if ids and len(ids) != expected:
        result.errors.append(
            f"plan expands to {len(ids)} episode slots from curriculum modules "
            f"{block_counts}, expected {expected}"
        )
    table_counts = _table_module_counts(plan_text)
    for module, count in sorted(block_counts.items()):
        if module in table_counts and table_counts[module] != count:
            result.errors.append(
                f"module table says {module}={table_counts[module]}, "
                f"curriculum block says {count}"
            )
    explicit = set(EPISODE_ID.findall(plan_text))
    unknown = sorted(explicit - set(ids))
    if unknown:
        result.errors.append(f"plan names episode ids outside the curriculum block: {unknown}")
    if result.errors:
        return _finish(result, root, artifacts)

    if episode_id is None:
        return _finish(result, root, artifacts)
    if episode_id not in set(ids):
        result.errors.append(f"episode {episode_id!r} is not in the {expected}-episode plan")
        return _finish(result, root, artifacts)

    if lesson_dir is None:
        lesson_dir = _find_lesson(root, lessons_root, episode_id)
    if lesson_dir is None:
        result.errors.append(f"no lesson declares episode_id {episode_id!r}")
        return _finish(result, root, artifacts)
    lesson_dir = Path(lesson_dir).resolve()
    result.lesson_slug = lesson_dir.name

    cards_dir = str(course.get("cards_dir") or "")
    card_path = (root / cards_dir / episode_id / "card.yaml").resolve() if cards_dir else None
    lesson_file = lesson_dir / "lesson.yaml"
    slides_file = lesson_dir / "slides.md"
    notes_file = lesson_dir / "lecture_notes.md"
    claim_file = lesson_dir / "authoring" / "episode.spec.yaml"
    named = [("lesson.yaml", lesson_file), ("slides.md", slides_file),
             ("lecture_notes.md", notes_file), ("episode.spec.yaml", claim_file)]
    if card_path is not None:
        named.insert(0, ("card", card_path))
    for label, path in named:
        artifacts[label] = path
        if not path.is_file():
            result.errors.append(f"{label} missing: {path}")
    if result.errors:
        return _finish(result, root, artifacts)

    card = _read_yaml(card_path)
    lesson = _read_yaml(lesson_file)
    claims = _read_yaml(claim_file)

    if str(card.get("episode")) != episode_id:
        result.errors.append(f"card episode drift: {card.get('episode')!r}")
    if str(lesson.get("lesson_id")) != lesson_dir.name:
        result.errors.append(
            f"lesson slug drift: {lesson.get('lesson_id')!r}, expected {lesson_dir.name!r}"
        )
    if str(lesson.get("course_id")) != course_id:
        result.errors.append(f"lesson course_id drift: {lesson.get('course_id')!r}")
    if str(lesson.get("episode_id")) != episode_id:
        result.errors.append(f"lesson episode_id drift: {lesson.get('episode_id')!r}")

    row = _detail_row(plan_text, episode_id)
    if row is not None:
        if _normalized(row["title"]) != _normalized(card.get("title")):
            result.errors.append(
                f"card title {card.get('title')!r} != plan row {row['title']!r}"
            )
        if str(card.get("section") or "") != row["section"]:
            result.errors.append(
                f"card section {card.get('section')!r} != plan row {row['section']!r}"
            )
        target = _number(card.get("target_seconds"))
        if target is None or abs(target - row["minutes"] * 60) > 0.01:
            result.errors.append(
                f"card target_seconds {card.get('target_seconds')!r} != "
                f"plan row {row['minutes']} minutes"
            )

    _require_duration_contract(card, lesson, claims, result.errors)

    slides = slides_file.read_text(encoding="utf-8")
    haystack = _normalized(slides)
    for term in course.get("forbidden_slide_terms") or []:
        if _normalized(term) in haystack:
            result.errors.append(f"slides.md contains forbidden stale label: {term!r}")

    episode_claims = claims.get("claims") or []
    if not episode_claims:
        result.errors.append("episode.spec.yaml declares no claims; an episode needs evidence")
    concepts = {str(item) for item in (card.get("concepts") or [])}
    for claim in episode_claims:
        source = claim.get("source") or {}
        section = str(source.get("section") or "")
        if section and section not in concepts:
            result.errors.append(
                f"claim {claim.get('id')!r} cites section {section}, "
                "which card.concepts does not declare"
            )

    return _finish(result, root, artifacts)


def check_lesson_course_chain(
    workspace: Path,
    lesson_dir: Path,
    *,
    config_path: Path | None = None,
) -> ChainResult | None:
    """Validate the course chain for one lesson.

    A lesson without ``course_id``/``episode_id`` keeps the legacy standalone
    behaviour, unless its directory name is explicitly forbidden. Nothing is
    inferred from the slug: the old inference silently bound test fixtures and
    renamed lessons to an episode.
    """
    lesson_dir = Path(lesson_dir).resolve()
    config = Path(config_path or default_chain_config()).resolve()
    root = resolve_chain_root(workspace, lesson_dir)
    result = ChainResult(lesson_slug=lesson_dir.name)
    artifacts = {"course_chain_config": config, "lesson.yaml": lesson_dir / "lesson.yaml"}
    if not (lesson_dir / "lesson.yaml").is_file():
        return None
    lesson = _read_yaml(lesson_dir / "lesson.yaml")
    course_id = str(lesson.get("course_id") or "").strip()
    episode_id = str(lesson.get("episode_id") or "").strip()

    if not course_id and not episode_id:
        if config.is_file():
            data = _read_yaml(config)
            for course in (data.get("courses") or {}).values():
                if not isinstance(course, dict):
                    continue
                forbidden = course.get("forbidden_lesson_slugs") or {}
                if lesson_dir.name in {str(item) for item in forbidden}:
                    result.errors.append(
                        f"lesson slug {lesson_dir.name!r} is forbidden; "
                        "use the lesson bound to its episode"
                    )
                    return _finish(result, root, artifacts)
        return None

    if not course_id or not episode_id:
        result.errors.append("course-bound lesson must declare both course_id and episode_id")
        return _finish(result, root, artifacts)
    result.course_id = course_id
    result.episode_id = episode_id
    return check_course_chain(
        root,
        config_path=config,
        course_id=course_id,
        episode_id=episode_id,
        lesson_dir=lesson_dir,
    )


def assert_lesson_course_chain(
    workspace: Path,
    lesson_dir: Path,
    *,
    config_path: Path | None = None,
) -> ChainResult | None:
    result = check_lesson_course_chain(
        workspace, lesson_dir, config_path=config_path
    )
    if result is not None and not result.ok:
        raise CourseChainError(
            "course chain failed:\n  - " + "\n  - ".join(result.errors)
        )
    return result


__all__ = [
    "ChainResult",
    "CourseChainError",
    "assert_lesson_course_chain",
    "check_course_chain",
    "check_lesson_course_chain",
    "default_chain_config",
    "expand_episode_ids",
    "resolve_chain_root",
]
