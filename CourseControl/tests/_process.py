"""Helpers shared by tests that run external tools."""

from __future__ import annotations

import os
import subprocess

# The hosted Windows runner runs each step in a console shared with its child
# processes. A console control event (Ctrl+C / Ctrl+Break) terminates every
# attached child with STATUS_CONTROL_C_EXIT (0xC000013A). ffmpeg here only
# reads lavfi sources and writes a file, so it has no reason to stay on that
# console: detach it on Windows and keep the default behaviour elsewhere.
NO_CONSOLE = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

__all__ = ["NO_CONSOLE"]
