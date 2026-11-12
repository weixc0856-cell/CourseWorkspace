"""Which upstream change forces which downstream re-check.

The table is the WP-4 contract: a lock records hashes, a later run compares the
current hashes with the locked ones, and every difference names the artefacts
that must be re-checked.  Nothing here decides *how* to rebuild -- it decides
what is stale.

Keys are namespaced: ``picture:page-003`` and ``asset:assets/body.png`` share
their base key with the rule table, so one changed frame names only the
downstream a frame change can touch.
"""

from __future__ import annotations


class LockError(RuntimeError):
    """A lock cannot be taken or cannot be compared."""


RULES: dict[str, tuple[str, ...]] = {
    "script": ("narration", "subtitles", "timeline", "audio_mix"),
    "voice_bible": ("narration", "subtitles", "audio_mix"),
    "lexicon": ("narration", "subtitles", "audio_mix"),
    "narration": ("subtitles", "timeline", "audio_mix"),
    "shot_sheet": ("shot_sheet_plan", "director_plan", "animatic", "affected_shots"),
    "sheet": ("animatic", "affected_shots"),
    "scene": ("affected_shots",),
    "asset": ("affected_shots",),
    "picture": ("timeline", "final_compose"),
    "bgm": ("audio_mix", "audio_qc"),
    "compose_config": ("final_compose", "full_qc"),
    "subtitles": (),
}


def base_key(key: str) -> str:
    return key.split(":", 1)[0]


def downstream_for(key: str) -> list[str]:
    return list(RULES.get(base_key(key), ()))


def diff(previous: dict, current: dict) -> list[dict]:
    """Every hash that differs, with the downstream it invalidates."""
    changes: list[dict] = []
    for key in sorted(set(previous) | set(current)):
        before = previous.get(key)
        after = current.get(key)
        if before == after:
            continue
        if key not in previous:
            change = "added"
        elif key not in current:
            change = "removed"
        else:
            change = "changed"
        changes.append(
            {
                "key": key,
                "change": change,
                "was": before,
                "now": after,
                "downstream": downstream_for(key),
            }
        )
    return changes


def affected(changes: list[dict]) -> list[str]:
    names: list[str] = []
    for change in changes:
        for name in change.get("downstream", ()):
            if name not in names:
                names.append(name)
    return names
