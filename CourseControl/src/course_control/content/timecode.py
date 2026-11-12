"""Integer-only time conversion for course contracts V1.

Video time is represented as integer frames.  A frame rate is a rational
``fps_num / fps_den`` so rates such as 30000/1001 and 60000/1001 are exact
inputs rather than rounded decimals.  Milliseconds are an exchange unit at
the audio/subtitle boundary only; no conversion in this module uses floats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SRT_RE = re.compile(r"^(?P<h>\d{2,}):(?P<m>[0-5]\d):(?P<s>[0-5]\d),(?P<ms>\d{3})$")


class TimecodeError(ValueError):
    """Raised when a time value or frame rate is not representable."""


def _positive_int(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise TimecodeError(f"{name} must be a positive integer, got {value!r}")
    return value


def _non_negative_int(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TimecodeError(f"{name} must be a non-negative integer, got {value!r}")
    return value


def _round_half_up(numerator: int, denominator: int) -> int:
    """Round a non-negative rational to the nearest integer, ties upward.

    ``numerator`` and ``denominator`` are integers.  The calculation uses
    ``(2*n + d) // (2*d)`` so no float ever enters the conversion.
    """

    if denominator <= 0:
        raise TimecodeError(f"denominator must be positive, got {denominator!r}")
    if numerator < 0:
        raise TimecodeError(f"numerator must be non-negative, got {numerator!r}")
    return (2 * numerator + denominator) // (2 * denominator)


def validate_fps(fps_num: int, fps_den: int = 1) -> None:
    _positive_int("fps_num", fps_num)
    _positive_int("fps_den", fps_den)


def ms_to_frame(ms: int, fps_num: int, fps_den: int = 1) -> int:
    """Nearest video frame for a millisecond timestamp.

    ``ms * fps_num / (1000 * fps_den)``, rounded half up.  Use this for
    external timestamps (WAV duration, SRT input).  For a sequence of
    segments, convert cumulative milliseconds once and subtract frame
    boundaries; do not convert and add each segment independently.
    """

    _non_negative_int("ms", ms)
    validate_fps(fps_num, fps_den)
    return _round_half_up(ms * fps_num, 1000 * fps_den)


def frame_to_ms(frame: int, fps_num: int, fps_den: int = 1) -> int:
    """Nearest millisecond for a video frame, rounded half up."""

    _non_negative_int("frame", frame)
    validate_fps(fps_num, fps_den)
    return _round_half_up(frame * 1000 * fps_den, fps_num)


def frame_to_sample(frame: int, sample_rate: int, fps_num: int, fps_den: int = 1) -> int:
    """Nearest audio sample index for a video frame.

    The exact time is ``frame * fps_den / fps_num`` seconds.  At 48 kHz and
    30000/1001 fps a frame is 1601.6 samples, so the returned sample is an
    integer approximation; ``AudioAlignment`` records the drift.
    """

    _non_negative_int("frame", frame)
    _positive_int("sample_rate", sample_rate)
    validate_fps(fps_num, fps_den)
    return _round_half_up(frame * sample_rate * fps_den, fps_num)


def sample_to_frame(sample: int, sample_rate: int, fps_num: int, fps_den: int = 1) -> int:
    """Nearest video frame for an audio sample index, rounded half up."""

    _non_negative_int("sample", sample)
    _positive_int("sample_rate", sample_rate)
    validate_fps(fps_num, fps_den)
    return _round_half_up(sample * fps_num, sample_rate * fps_den)


def format_srt_timestamp(ms: int) -> str:
    """Format non-negative milliseconds as ``HH:MM:SS,mmm``."""

    _non_negative_int("ms", ms)
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_srt_timestamp(value: str) -> int:
    """Parse ``HH:MM:SS,mmm`` into integer milliseconds."""

    match = _SRT_RE.match(value)
    if not match:
        raise TimecodeError(f"invalid SRT timestamp: {value!r}")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    millis = int(match.group("ms"))
    return ((hours * 60 + minutes) * 60 + seconds) * 1_000 + millis


def frame_to_srt(frame: int, fps_num: int, fps_den: int = 1) -> str:
    return format_srt_timestamp(frame_to_ms(frame, fps_num, fps_den))


def srt_to_frames(start: str, end: str, fps_num: int, fps_den: int = 1) -> tuple[int, int]:
    """Convert an SRT cue to frame boundaries and reject empty cues."""

    start_ms = parse_srt_timestamp(start)
    end_ms = parse_srt_timestamp(end)
    if end_ms <= start_ms:
        raise TimecodeError(f"SRT cue end must be after start: {start!r} -> {end!r}")
    start_frame = ms_to_frame(start_ms, fps_num, fps_den)
    end_frame = ms_to_frame(end_ms, fps_num, fps_den)
    if end_frame <= start_frame:
        raise TimecodeError(
            f"SRT cue is shorter than one frame at {fps_num}/{fps_den}: {start!r} -> {end!r}"
        )
    return start_frame, end_frame


@dataclass(frozen=True)
class AudioAlignment:
    """Frame/sample alignment for one contiguous audio segment."""

    start_frame: int
    end_frame: int
    start_sample: int
    end_sample: int
    aligned_start_sample: int
    aligned_end_sample: int
    sample_rate: int
    fps_num: int
    fps_den: int

    @property
    def start_drift_samples(self) -> int:
        return self.aligned_start_sample - self.start_sample

    @property
    def end_drift_samples(self) -> int:
        return self.aligned_end_sample - self.end_sample

    @property
    def max_drift_samples(self) -> int:
        """One video frame expressed in audio samples (rounded up)."""

        return (self.sample_rate * self.fps_den + self.fps_num - 1) // self.fps_num

    def within_one_frame(self) -> bool:
        return (
            abs(self.start_drift_samples) <= self.max_drift_samples
            and abs(self.end_drift_samples) <= self.max_drift_samples
        )


def align_audio_segment(
    start_sample: int,
    end_sample: int,
    sample_rate: int,
    fps_num: int,
    fps_den: int = 1,
) -> AudioAlignment:
    """Align a sample range to video frames.

    Both boundaries are quantized independently to the nearest frame, then
    the chosen frame boundaries are mapped back to sample indices.  The
    differences are reported as drift instead of being silently corrected.
    """

    _non_negative_int("start_sample", start_sample)
    _non_negative_int("end_sample", end_sample)
    _positive_int("sample_rate", sample_rate)
    validate_fps(fps_num, fps_den)
    if end_sample <= start_sample:
        raise TimecodeError(
            f"audio segment end must be after start: {start_sample} -> {end_sample}"
        )
    start_frame = sample_to_frame(start_sample, sample_rate, fps_num, fps_den)
    end_frame = sample_to_frame(end_sample, sample_rate, fps_num, fps_den)
    if end_frame <= start_frame:
        raise TimecodeError(
            "audio segment is shorter than one video frame at "
            f"{fps_num}/{fps_den} fps"
        )
    return AudioAlignment(
        start_frame=start_frame,
        end_frame=end_frame,
        start_sample=start_sample,
        end_sample=end_sample,
        aligned_start_sample=frame_to_sample(start_frame, sample_rate, fps_num, fps_den),
        aligned_end_sample=frame_to_sample(end_frame, sample_rate, fps_num, fps_den),
        sample_rate=sample_rate,
        fps_num=fps_num,
        fps_den=fps_den,
    )
