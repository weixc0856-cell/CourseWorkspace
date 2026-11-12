"""Picture and Dialogue locks: snapshots that make drift visible.

A lock never forbids a change.  It records the hashes an approval was given
against, and the next ``lock-status`` says which downstream artefacts the
difference invalidates.  See ``docs/锁定与失效.md``.
"""

from . import dialogue, picture
from .dependencies import RULES, LockError, affected, diff, downstream_for

__all__ = [
    "RULES",
    "LockError",
    "affected",
    "dialogue",
    "diff",
    "downstream_for",
    "picture",
]
