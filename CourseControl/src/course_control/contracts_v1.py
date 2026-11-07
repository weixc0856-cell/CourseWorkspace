"""Normalized course-production contracts V1.

This module is additive.  It does not replace ``lesson.yaml`` or
``storyboard.yaml``; adapters will translate author files into these objects.
All timeline values are integer frames.  Milliseconds are used only for
external audio/subtitle boundaries, where ``timecode`` converts them exactly.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, ValidationError, field_validator, model_validator

from .contracts import SLUG_RE, StrictModel
from .paths import path_problem
from .timecode import frame_to_ms, frame_to_srt, ms_to_frame

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
RENDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

class V1Model(StrictModel):
    """Strict V1 base: reject extra fields and implicit type coercion."""

    model_config = ConfigDict(extra="forbid", strict=True)


def _require_id(value: str, field: str) -> str:
    if not ID_RE.match(value):
        raise ValueError(f"{field} must match {ID_RE.pattern}")
    return value


def _require_sha256(value: str, field: str = "sha256") -> str:
    if not SHA256_RE.match(value):
        raise ValueError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


class AssetRef(V1Model):
    """A file reference with content identity and provenance."""

    path: str = Field(min_length=1)
    sha256: str
    bytes: int = Field(ge=0)
    kind: Literal[
        "video", "audio", "image", "subtitle", "font", "data", "log", "json"
    ]
    origin: Literal[
        "author", "rendered", "captured", "generated", "external"
    ]
    version: str | None = None

    @field_validator("sha256")
    @classmethod
    def _sha256(cls, value: str) -> str:
        return _require_sha256(value)

    @model_validator(mode="after")
    def _path(self):
        if self.origin == "external":
            normalized = self.path.replace("\\", "/")
            if any(part == ".." for part in normalized.split("/")):
                raise ValueError("external path must not contain '..'")
            return self
        problem = path_problem(self.path)
        if problem:
            raise ValueError(f"path: {problem}")
        return self


class RationalFPS(V1Model):
    """Exact frame rate as a rational number, e.g. 30000/1001."""

    fps_num: int = Field(gt=0, le=1_000_000)
    fps_den: int = Field(gt=0, le=1_000_000)

    def frame_to_ms(self, frame: int) -> int:
        return frame_to_ms(frame, self.fps_num, self.fps_den)

    def ms_to_frame(self, ms: int) -> int:
        return ms_to_frame(ms, self.fps_num, self.fps_den)


class FrameTiming(V1Model):
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)

    @property
    def end_frame(self) -> int:
        return self.start_frame + self.duration_frames


class LessonSource(V1Model):
    lesson_yaml: AssetRef
    storyboard: AssetRef


class LessonAudio(V1Model):
    sample_rate: int = Field(48000, gt=0, le=384000)
    channels: int = Field(1, ge=1, le=8)


class LessonOutput(V1Model):
    fps: RationalFPS
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    audio: LessonAudio = LessonAudio()


class LessonNarration(V1Model):
    enabled: bool = False
    spec: AssetRef | None = None

    @model_validator(mode="after")
    def _spec_when_enabled(self):
        if self.enabled and self.spec is None:
            raise ValueError("narration.spec is required when narration is enabled")
        return self


class LessonSubtitles(V1Model):
    enabled: bool = False
    format: Literal["srt"] = "srt"
    spec: AssetRef | None = None

    @model_validator(mode="after")
    def _spec_when_enabled(self):
        if self.enabled and self.spec is None:
            raise ValueError("subtitles.spec is required when subtitles are enabled")
        return self


class LessonAcceptance(V1Model):
    min_duration_frames: int | None = Field(default=None, ge=0)
    max_duration_frames: int | None = Field(default=None, ge=0)
    required_checks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _range(self):
        if (
            self.min_duration_frames is not None
            and self.max_duration_frames is not None
            and self.max_duration_frames < self.min_duration_frames
        ):
            raise ValueError("max_duration_frames must be >= min_duration_frames")
        return self


class LessonSpec(V1Model):
    schema_version: Literal[1] = 1
    kind: Literal["lesson_spec"] = "lesson_spec"
    lesson_id: str
    title: str = Field(min_length=1)
    status: Literal["draft", "ready", "in_progress", "done", "blocked"]
    source: LessonSource
    output: LessonOutput
    tracks: list[
        Literal[
            "slide",
            "motion_canvas",
            "manim",
            "blender",
            "session",
            "simulation",
            "graphics",
        ]
    ] = Field(min_length=1)
    assets: list[AssetRef] = Field(default_factory=list)
    narration: LessonNarration = LessonNarration()
    subtitles: LessonSubtitles = LessonSubtitles()
    acceptance: LessonAcceptance = LessonAcceptance()
    metadata: dict[str, Any] | None = None

    @field_validator("lesson_id")
    @classmethod
    def _lesson_id(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase hyphenated slug")
        return value

    @model_validator(mode="after")
    def _unique_tracks(self):
        if len(set(self.tracks)) != len(self.tracks):
            raise ValueError("tracks must be unique")
        return self


class SlideSource(V1Model):
    kind: Literal["slide"]
    slide: int = Field(ge=1)


class MotionCanvasSource(V1Model):
    kind: Literal["motion_canvas"]
    project: str = Field(min_length=1)
    scene: str = Field(min_length=1)


class ManimSource(V1Model):
    kind: Literal["manim"]
    file: str = Field(min_length=1)
    scene_class: str = Field(alias="class", min_length=1)

    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=True)


class BlenderSource(V1Model):
    kind: Literal["blender"]
    task: str = Field(min_length=1)


class SessionSource(V1Model):
    kind: Literal["session"]
    session_spec: str = Field(min_length=1)
    session_id: str

    @field_validator("session_id")
    @classmethod
    def _session_id(cls, value: str) -> str:
        return _require_id(value, "session_id")


class SimulationSource(V1Model):
    kind: Literal["simulation"]
    project: str = Field(min_length=1)
    entry: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class GraphicsSource(V1Model):
    kind: Literal["graphics"]
    project: str = Field(min_length=1)
    entry: str = Field(min_length=1)


ShotSource = Annotated[
    SlideSource
    | MotionCanvasSource
    | ManimSource
    | BlenderSource
    | SessionSource
    | SimulationSource
    | GraphicsSource,
    Field(discriminator="kind"),
]


class ExpectedTiming(V1Model):
    duration_frames: int | None = Field(default=None, gt=0)
    min_frames: int | None = Field(default=None, ge=0)
    max_frames: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _range(self):
        if self.min_frames is not None and self.max_frames is not None:
            if self.max_frames < self.min_frames:
                raise ValueError("max_frames must be >= min_frames")
        return self


class Presentation(V1Model):
    role: Literal["base", "overlay"] = "base"
    z: int = Field(0, ge=-100, le=100)


class ShotSpecV1(V1Model):
    schema_version: Literal[1] = 1
    kind: Literal["shot_spec"] = "shot_spec"
    lesson_id: str
    shot_id: str
    track: Literal[
        "slide",
        "motion_canvas",
        "manim",
        "blender",
        "session",
        "simulation",
        "graphics",
    ]
    source: ShotSource
    timing: FrameTiming
    narration_id: str | None = None
    asset: AssetRef | None = None
    expected: ExpectedTiming = ExpectedTiming()
    presentation: Presentation = Presentation()
    metadata: dict[str, Any] | None = None

    @field_validator("lesson_id")
    @classmethod
    def _lesson_id(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase hyphenated slug")
        return value

    @field_validator("shot_id")
    @classmethod
    def _shot_id(cls, value: str) -> str:
        return _require_id(value, "shot_id")

    @field_validator("narration_id")
    @classmethod
    def _narration_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_id(value, "narration_id")

    @model_validator(mode="after")
    def _track_matches_source(self):
        if self.track != self.source.kind:
            raise ValueError("track must match source.kind")
        if self.asset is not None and self.asset.kind not in ("video", "image"):
            raise ValueError("shot asset must be video or image")
        return self


class NarrationVoice(V1Model):
    provider: Literal["voxcpm2"]
    ref_audio: AssetRef
    language: str = Field("zh", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    speed: float = Field(1.0, ge=0.5, le=2.0)


class NarrationSegment(V1Model):
    narration_id: str
    shot_id: str
    text: str = Field(min_length=1)
    text_sha256: str
    audio: AssetRef
    duration_ms: int = Field(gt=0)
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    fit: Literal["ok", "underflow", "overflow", "mismatch"]

    @field_validator("narration_id")
    @classmethod
    def _narration_id(cls, value: str) -> str:
        return _require_id(value, "narration_id")

    @field_validator("shot_id")
    @classmethod
    def _shot_id(cls, value: str) -> str:
        return _require_id(value, "shot_id")

    @field_validator("text_sha256")
    @classmethod
    def _text_hash(cls, value: str) -> str:
        return _require_sha256(value, "text_sha256")

    @model_validator(mode="after")
    def _audio_kind(self):
        if self.audio.kind != "audio":
            raise ValueError("narration segment audio must be kind=audio")
        return self


class NarrationTotal(V1Model):
    duration_ms: int = Field(ge=0)
    total_frames: int = Field(gt=0)


class NarrationGenerator(V1Model):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)


class NarrationSpec(V1Model):
    schema_version: Literal[1] = 1
    kind: Literal["narration_spec"] = "narration_spec"
    lesson_id: str
    fps: RationalFPS
    voice: NarrationVoice
    segments: list[NarrationSegment] = Field(min_length=1)
    total: NarrationTotal
    generator: NarrationGenerator

    @field_validator("lesson_id")
    @classmethod
    def _lesson_id(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase hyphenated slug")
        return value

    @model_validator(mode="after")
    def _segments(self):
        ids = [segment.narration_id for segment in self.segments]
        shot_ids = [segment.shot_id for segment in self.segments]
        if len(set(ids)) != len(ids):
            raise ValueError("narration_id values must be unique")
        if len(set(shot_ids)) != len(shot_ids):
            raise ValueError("each shot can have only one narration segment")
        ordered = sorted(self.segments, key=lambda segment: segment.start_frame)
        if [segment.start_frame for segment in self.segments] != [
            segment.start_frame for segment in ordered
        ]:
            raise ValueError("narration segments must be ordered by start_frame")
        previous_end = -1
        for segment in ordered:
            expected = ms_to_frame(
                segment.duration_ms, self.fps.fps_num, self.fps.fps_den
            )
            if segment.duration_frames != expected:
                raise ValueError(
                    f"{segment.narration_id}: duration_frames {segment.duration_frames} "
                    f"does not match duration_ms {segment.duration_ms} at "
                    f"{self.fps.fps_num}/{self.fps.fps_den}"
                )
            if segment.start_frame < previous_end:
                raise ValueError(
                    f"narration segment {segment.narration_id} overlaps the previous segment"
                )
            previous_end = segment.start_frame + segment.duration_frames
        if self.total.total_frames < previous_end:
            raise ValueError("total.total_frames is shorter than the last segment")
        expected_total_ms = frame_to_ms(
            self.total.total_frames, self.fps.fps_num, self.fps.fps_den
        )
        if self.total.duration_ms != expected_total_ms:
            raise ValueError(
                f"total.duration_ms {self.total.duration_ms} does not match "
                f"{self.total.total_frames} frames at "
                f"{self.fps.fps_num}/{self.fps.fps_den}"
            )
        return self


class TimelineVideo(V1Model):
    shot_id: str
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    role: Literal["base", "overlay"] = "base"
    z: int = Field(0, ge=-100, le=100)
    asset: AssetRef

    @field_validator("shot_id")
    @classmethod
    def _shot_id(cls, value: str) -> str:
        return _require_id(value, "shot_id")

    @model_validator(mode="after")
    def _asset_kind(self):
        if self.asset.kind not in ("video", "image"):
            raise ValueError("timeline video asset must be video or image")
        return self


class TimelineAudio(V1Model):
    narration_id: str
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    asset: AssetRef
    gain_db: float = Field(0.0, ge=-60.0, le=12.0)

    @field_validator("narration_id")
    @classmethod
    def _narration_id(cls, value: str) -> str:
        return _require_id(value, "narration_id")

    @model_validator(mode="after")
    def _asset_kind(self):
        if self.asset.kind != "audio":
            raise ValueError("timeline audio asset must be kind=audio")
        return self


class SubtitleCue(V1Model):
    index: int = Field(ge=1)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.end_frame <= self.start_frame:
            raise ValueError("subtitle end_frame must be after start_frame")
        return self


class SyncRules(V1Model):
    audio_tolerance_frames: int = Field(1, ge=0, le=10)
    subtitle_tolerance_ms: int = Field(40, ge=0, le=1000)
    allow_gap_frames: int = Field(1, ge=0, le=10)


class TimelineSpec(V1Model):
    schema_version: Literal[1] = 1
    kind: Literal["timeline_spec"] = "timeline_spec"
    lesson_id: str
    fps: RationalFPS
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    total_frames: int = Field(gt=0)
    video: list[TimelineVideo] = Field(min_length=1)
    audio: list[TimelineAudio] = Field(default_factory=list)
    subtitles: list[SubtitleCue] = Field(default_factory=list)
    sync: SyncRules = SyncRules()

    @field_validator("lesson_id")
    @classmethod
    def _lesson_id(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase hyphenated slug")
        return value

    @property
    def duration_ms(self) -> int:
        return frame_to_ms(self.total_frames, self.fps.fps_num, self.fps.fps_den)

    def srt_text(self) -> str:
        blocks: list[str] = []
        for cue in sorted(self.subtitles, key=lambda item: item.start_frame):
            blocks.append(
                f"{cue.index}\n"
                f"{frame_to_srt(cue.start_frame, self.fps.fps_num, self.fps.fps_den)} --> "
                f"{frame_to_srt(cue.end_frame, self.fps.fps_num, self.fps.fps_den)}\n"
                f"{cue.text}"
            )
        return "\n\n".join(blocks) + ("\n" if blocks else "")

    @model_validator(mode="after")
    def _timeline(self):
        if len({item.shot_id for item in self.video}) != len(self.video):
            raise ValueError("timeline video shot_id values must be unique")
        base = sorted(
            (item for item in self.video if item.role == "base"),
            key=lambda item: item.start_frame,
        )
        if not base:
            raise ValueError("timeline requires at least one base video shot")
        if base[0].start_frame != 0:
            raise ValueError("the first base shot must start at frame 0")
        for previous, current in zip(base, base[1:]):
            previous_end = previous.start_frame + previous.duration_frames
            if current.start_frame < previous_end:
                raise ValueError(
                    f"base shots {previous.shot_id} and {current.shot_id} overlap"
                )
            gap = current.start_frame - previous_end
            if gap > self.sync.allow_gap_frames:
                raise ValueError(
                    f"base shots {previous.shot_id} and {current.shot_id} "
                    f"have a {gap}-frame gap"
                )
        base_end = base[-1].start_frame + base[-1].duration_frames
        if base_end != self.total_frames:
            raise ValueError(
                f"base shots end at frame {base_end}, expected {self.total_frames}"
            )
        for item in self.video:
            if item.role != "overlay":
                continue
            end = item.start_frame + item.duration_frames
            if not any(
                item.start_frame >= shot.start_frame
                and end <= shot.start_frame + shot.duration_frames
                for shot in base
            ):
                raise ValueError(f"overlay shot {item.shot_id} is outside every base shot")

        if len({item.narration_id for item in self.audio}) != len(self.audio):
            raise ValueError("timeline audio narration_id values must be unique")
        previous_audio_end = -1
        for item in sorted(self.audio, key=lambda audio: audio.start_frame):
            if item.start_frame < previous_audio_end:
                raise ValueError(f"audio {item.narration_id} overlaps the previous audio")
            previous_audio_end = item.start_frame + item.duration_frames
            if previous_audio_end > self.total_frames:
                raise ValueError(f"audio {item.narration_id} exceeds total_frames")

        if len({cue.index for cue in self.subtitles}) != len(self.subtitles):
            raise ValueError("subtitle cue indices must be unique")
        previous_cue_end = -1
        for cue in sorted(self.subtitles, key=lambda item: item.start_frame):
            if cue.start_frame < previous_cue_end:
                raise ValueError(f"subtitle cue {cue.index} overlaps the previous cue")
            previous_cue_end = cue.end_frame
            if cue.end_frame > self.total_frames:
                raise ValueError(f"subtitle cue {cue.index} exceeds total_frames")
        return self


class EvidenceEnvironment(V1Model):
    kind: Literal["docker", "wsl", "host"]
    image: str | None = None
    image_digest: str | None = None
    os: str | None = None
    tool_versions: dict[str, str] = Field(default_factory=dict)


class EvidenceManifestV1(V1Model):
    schema_version: Literal[1] = 1
    kind: Literal["evidence_manifest"] = "evidence_manifest"
    lesson_id: str
    shot_id: str
    session_id: str
    run_id: str
    spec: AssetRef
    environment: EvidenceEnvironment | None = None
    execution_result: AssetRef
    recording_result: AssetRef
    validation_report: AssetRef
    transcript: AssetRef | None = None
    artifacts: list[AssetRef] = Field(default_factory=list)
    cache_key: str = Field(min_length=1)
    legacy: dict[str, Any] | None = None

    @field_validator("lesson_id")
    @classmethod
    def _lesson_id(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase hyphenated slug")
        return value

    @field_validator("shot_id", "session_id")
    @classmethod
    def _ids(cls, value: str) -> str:
        return _require_id(value, "id")

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        if not RUN_ID_RE.match(value):
            raise ValueError("run_id must look like 20261107T090000Z-1a2b3c4d")
        return value

    @model_validator(mode="after")
    def _artifacts(self):
        paths = [item.path for item in self.artifacts]
        if len(set(paths)) != len(paths):
            raise ValueError("artifact paths must be unique")
        if self.execution_result.kind != "json":
            raise ValueError("execution_result must be a JSON asset")
        if self.recording_result.kind != "json":
            raise ValueError("recording_result must be a JSON asset")
        if self.validation_report.kind != "json":
            raise ValueError("validation_report must be a JSON asset")
        return self


class RenderSource(V1Model):
    # Standalone tracks (such as E6.5) may not have an author lesson.yaml.
    lesson_spec: AssetRef | None = None
    timeline: AssetRef
    narration: AssetRef | None = None


class RenderOutput(V1Model):
    fps: RationalFPS
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    total_frames: int = Field(gt=0)
    duration_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _duration(self):
        expected = frame_to_ms(
            self.total_frames, self.fps.fps_num, self.fps.fps_den
        )
        if self.duration_ms != expected:
            raise ValueError(
                f"duration_ms {self.duration_ms} does not match "
                f"{self.total_frames} frames at {self.fps.fps_num}/{self.fps.fps_den}"
            )
        return self


class RenderShot(V1Model):
    shot_id: str
    track: Literal[
        "slide",
        "motion_canvas",
        "manim",
        "blender",
        "session",
        "simulation",
        "graphics",
    ]
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    asset: AssetRef
    evidence: AssetRef | None = None

    @field_validator("shot_id")
    @classmethod
    def _shot_id(cls, value: str) -> str:
        return _require_id(value, "shot_id")

    @model_validator(mode="after")
    def _asset_kind(self):
        if self.asset.kind not in ("video", "image"):
            raise ValueError("render shot asset must be video or image")
        return self


class RenderNarrationSegment(V1Model):
    narration_id: str
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    duration_ms: int = Field(gt=0)

    @field_validator("narration_id")
    @classmethod
    def _narration_id(cls, value: str) -> str:
        return _require_id(value, "narration_id")


class RenderNarration(V1Model):
    asset: AssetRef
    duration_ms: int = Field(gt=0)
    segments: list[RenderNarrationSegment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _asset_kind(self):
        if self.asset.kind != "audio":
            raise ValueError("render narration asset must be kind=audio")
        return self


class RenderSubtitles(V1Model):
    asset: AssetRef
    format: Literal["srt"] = "srt"
    cues: int = Field(ge=0)

    @model_validator(mode="after")
    def _asset_kind(self):
        if self.asset.kind != "subtitle":
            raise ValueError("render subtitles asset must be kind=subtitle")
        return self


class RenderCheck(V1Model):
    id: str = Field(min_length=1)
    status: Literal["pass", "fail", "skipped", "not_run", "not_applicable"]
    detail: str = ""
    evidence: AssetRef | None = None


class RenderManifest(V1Model):
    schema_version: Literal[1] = 1
    kind: Literal["render_manifest"] = "render_manifest"
    lesson_id: str
    render_id: str
    run_id: str
    created_at: str = Field(min_length=1)
    source: RenderSource | None = None
    output: RenderOutput
    shots: list[RenderShot] = Field(min_length=1)
    narration: RenderNarration | None = None
    subtitles: RenderSubtitles | None = None
    video: AssetRef
    checks: list[RenderCheck] = Field(default_factory=list)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    legacy: dict[str, Any] | None = None

    @field_validator("lesson_id")
    @classmethod
    def _lesson_id(cls, value: str) -> str:
        if not SLUG_RE.match(value):
            raise ValueError("lesson_id must be a lowercase hyphenated slug")
        return value

    @field_validator("render_id")
    @classmethod
    def _render_id(cls, value: str) -> str:
        if not RENDER_ID_RE.match(value):
            raise ValueError(f"render_id must match {RENDER_ID_RE.pattern}")
        return value

    @field_validator("run_id")
    @classmethod
    def _run_id(cls, value: str) -> str:
        if not RUN_ID_RE.match(value):
            raise ValueError("run_id must look like 20261107T090000Z-1a2b3c4d")
        return value

    @model_validator(mode="after")
    def _manifest(self):
        if self.source is None:
            legacy_manifest = (self.legacy or {}).get("v0_manifest")
            if legacy_manifest is None:
                raise ValueError(
                    "source is required unless legacy.v0_manifest is provided"
                )
            try:
                AssetRef.model_validate(legacy_manifest)
            except ValidationError as exc:
                raise ValueError(
                    "legacy.v0_manifest must be a valid AssetRef"
                ) from exc
        if self.video.kind != "video":
            raise ValueError("video must be kind=video")
        if len({shot.shot_id for shot in self.shots}) != len(self.shots):
            raise ValueError("render shot ids must be unique")
        for shot in self.shots:
            end = shot.start_frame + shot.duration_frames
            if end > self.output.total_frames:
                raise ValueError(f"shot {shot.shot_id} exceeds output.total_frames")
        if len({check.id for check in self.checks}) != len(self.checks):
            raise ValueError("render check ids must be unique")
        return self


V1_MODELS = {
    "asset-ref-v1": AssetRef,
    "lesson-v1": LessonSpec,
    "shot-v1": ShotSpecV1,
    "narration-v1": NarrationSpec,
    "timeline-v1": TimelineSpec,
    "evidence-v1": EvidenceManifestV1,
    "render-v1": RenderManifest,
}
