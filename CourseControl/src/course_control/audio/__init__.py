"""Voice assets: Voice Bible and Lexicon, resolved per lesson.

``<content_root>/audio/`` holds them:

    audio/
    ├── voice-bibles/<voice-id>.yaml
    └── lexicons/<series-id>.yaml

A lesson opts in from ``lesson.yaml``:

    narration:
      voice_bible: wayne-en-v1
      lexicon: automotive-aerodynamics

Both are optional.  A lesson that declares neither behaves exactly as before:
the config voice reference is used and the cache key is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..workspace_layout import audio_root
from . import lexicon as lexicon_module
from . import voice_bible as voice_bible_module
from .lexicon import Application, Lexicon, LexiconEntry
from .voice_bible import AudioAssetError, VoiceBible

__all__ = [
    "Application",
    "AudioAssetError",
    "Lexicon",
    "LexiconEntry",
    "ResolvedAssets",
    "VoiceBible",
    "resolve_assets",
]


@dataclass
class ResolvedAssets:
    voice_bible: VoiceBible | None = None
    voice_bible_path: Path | None = None
    voice_bible_sha256: str | None = None
    lexicon: Lexicon | None = None
    lexicon_path: Path | None = None
    lexicon_sha256: str | None = None
    problems: list[str] = field(default_factory=list)

    def apply(self, text: str) -> Application:
        if self.lexicon is None:
            return Application(text)
        return lexicon_module.apply(self.lexicon, text)

    def ref_audio(self) -> Path | None:
        if self.voice_bible is None or self.voice_bible_path is None:
            return None
        return voice_bible_module.ref_audio_path(self.voice_bible, self.voice_bible_path)

    def as_dict(self) -> dict:
        return {
            "voice_bible": (
                None
                if self.voice_bible is None
                else {
                    "id": self.voice_bible.id,
                    "sha256": self.voice_bible_sha256,
                    "path": str(self.voice_bible_path),
                    "ref_audio": str(self.ref_audio()),
                    "model": self.voice_bible.model,
                    "backend": self.voice_bible.backend,
                    "language": self.voice_bible.language,
                }
            ),
            "lexicon": (
                None
                if self.lexicon is None
                else {
                    "id": self.lexicon.id,
                    "sha256": self.lexicon_sha256,
                    "path": str(self.lexicon_path),
                    "entries": len(self.lexicon.entries),
                }
            ),
            "problems": list(self.problems),
        }


def resolve_assets(workspace: Path, lesson) -> ResolvedAssets:
    """Load the assets a lesson declares; raise when a declared file is missing."""
    narration = getattr(lesson, "narration", None)
    if narration is None:
        return ResolvedAssets()
    root = audio_root(workspace)
    assets = ResolvedAssets()

    bible_id = getattr(narration, "voice_bible", None)
    if bible_id:
        path = voice_bible_module.resolve(root, bible_id)
        if not path.is_file():
            raise AudioAssetError(f"voice bible '{bible_id}' not found: {path}")
        assets.voice_bible = voice_bible_module.load(path)
        assets.voice_bible_path = path
        assets.voice_bible_sha256 = voice_bible_module.digest(assets.voice_bible)
        assets.problems.extend(voice_bible_module.check(assets.voice_bible, path))

    lexicon_id = getattr(narration, "lexicon", None)
    if lexicon_id:
        path = lexicon_module.resolve(root, lexicon_id)
        if not path.is_file():
            raise AudioAssetError(f"lexicon '{lexicon_id}' not found: {path}")
        assets.lexicon = lexicon_module.load(path)
        assets.lexicon_path = path
        assets.lexicon_sha256 = lexicon_module.digest(assets.lexicon)
        assets.problems.extend(lexicon_module.check(assets.lexicon, path))

    return assets
