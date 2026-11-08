"""Scope resolution: turn a commit/base range into an immutable input snapshot.

Everything the reviewer sees is read from Git objects, never from the working
tree.  That keeps the diff, the file full texts and the recorded commit in one
consistent snapshot even when the working tree is dirty.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from .schema import ExclusionRecord, ScopeMode

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
MAX_TEXT_FILE_BYTES = 512 * 1024
MAX_CHANGED_FILES = 200
BINARY_PROBE_BYTES = 8000

# Directories whose content is never part of a code review.  ``config`` holds
# local credentials and machine paths; ``lessons`` is course content owned by
# the user and only enters a review through an explicit course review grant.
DENY_DIR_NAMES = frozenset(
    {
        "lessons",
        "build",
        "runtime",
        "node_modules",
        ".venv",
        ".git",
        ".codex",
        ".sandbox",
        ".sandbox-bin",
        "config",
    }
)

DENY_PREFIXES = ("docs/archive/",)

DENY_BASENAME_GLOBS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "*credential*",
    "*secret*",
    "auth.json",
    "*.gguf",
    "*.safetensors",
    "*.onnx",
    "*.pt",
    "*.pth",
    "*.ckpt",
    "*.mp4",
    "*.mov",
    "*.webm",
    "*.wav",
    "*.mp3",
    "*.flac",
    "*.m4a",
)

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class ScopeError(RuntimeError):
    """The requested scope is invalid, unsafe or cannot be snapshotted."""


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------


def _decode(data: bytes) -> str:
    return (data or b"").decode("utf-8", "replace")


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    command = [
        "git",
        "-c",
        "core.quotepath=false",
        "-c",
        "color.ui=false",
        "-c",
        "core.autocrlf=false",
        "-c",
        "diff.external=",
        *args,
    ]
    proc = subprocess.run(command, cwd=str(repo), capture_output=True, env=env)
    if check and proc.returncode != 0:
        detail = _decode(proc.stderr).strip() or _decode(proc.stdout).strip()
        raise ScopeError(f"git {' '.join(args)} failed: {detail[-800:]}")
    return proc


def resolve_repo_root(start: Path | str) -> Path:
    candidate = Path(start).resolve()
    if not candidate.exists():
        raise ScopeError(f"workspace does not exist: {candidate}")
    proc = _git(candidate, "rev-parse", "--show-toplevel", check=False)
    if proc.returncode != 0:
        raise ScopeError(f"not a git repository: {candidate}")
    return Path(_decode(proc.stdout).strip()).resolve()


def resolve_commit(repo: Path, ref: str) -> str:
    if not ref or not ref.strip():
        raise ScopeError("empty commit reference")
    proc = _git(repo, "rev-parse", "--verify", f"{ref.strip()}^{{commit}}", check=False)
    if proc.returncode != 0:
        raise ScopeError(f"unknown commit: {ref}")
    return _decode(proc.stdout).strip()


def normalize_relpath(raw: str) -> str:
    value = (raw or "").strip().replace("\\", "/")
    if not value:
        raise ScopeError("empty path")
    if value.startswith("/") or _DRIVE_PREFIX.match(value) or os.path.isabs(value):
        raise ScopeError(f"absolute paths are not allowed: {raw}")
    path = PurePosixPath(value)
    if any(part in ("..", "") for part in path.parts):
        raise ScopeError(f"path traversal is not allowed: {raw}")
    if str(path) in (".", ""):
        raise ScopeError(f"invalid path: {raw}")
    return str(path)


def deny_reason(relpath: str) -> str | None:
    value = relpath.lower()
    path = PurePosixPath(value)
    if any(part in DENY_DIR_NAMES for part in path.parts):
        return "denied directory (course content, local config, build or dependency)"
    if value.startswith(DENY_PREFIXES):
        return "denied path prefix (local archive)"
    name = path.name
    for pattern in DENY_BASENAME_GLOBS:
        if fnmatchcase(name, pattern):
            return f"denied file pattern: {pattern}"
    return None


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeResolution:
    repo: Path
    mode: ScopeMode
    commit: str | None
    base: str | None
    head_sha: str
    review_rev: str
    diff_left: str
    diff_right: str
    diff_range: str
    base_resolved: str | None
    worktree_dirty: bool
    dirty_paths: int


def resolve_scope(
    repo: Path,
    *,
    mode: ScopeMode,
    commit: str | None = None,
    base: str | None = None,
) -> ScopeResolution:
    head_sha = resolve_commit(repo, "HEAD")
    status = _git(repo, "status", "--porcelain", "-z", check=False)
    dirty_paths = len([part for part in status.stdout.split(b"\0") if part])

    if mode is ScopeMode.commit:
        if not commit:
            raise ScopeError("--commit is required for commit review")
        if base:
            raise ScopeError("--commit and --base are mutually exclusive")
        sha = resolve_commit(repo, commit)
        parent = _git(repo, "rev-parse", "--verify", f"{sha}^^{{commit}}", check=False)
        left = _decode(parent.stdout).strip() if parent.returncode == 0 else EMPTY_TREE
        return ScopeResolution(
            repo=repo,
            mode=mode,
            commit=sha,
            base=None,
            head_sha=head_sha,
            review_rev=sha,
            diff_left=left,
            diff_right=sha,
            diff_range=f"{left[:12]}..{sha[:12]}",
            base_resolved=None,
            worktree_dirty=bool(dirty_paths),
            dirty_paths=dirty_paths,
        )

    if mode is ScopeMode.base:
        if not base:
            raise ScopeError("--base is required for base review")
        if commit:
            raise ScopeError("--base and --commit are mutually exclusive")
        base_sha = resolve_commit(repo, base)
        merge = _git(repo, "merge-base", base_sha, head_sha, check=False)
        if merge.returncode != 0:
            raise ScopeError(f"no merge base between {base} and HEAD")
        merge_base = _decode(merge.stdout).strip()
        return ScopeResolution(
            repo=repo,
            mode=mode,
            commit=None,
            base=base,
            head_sha=head_sha,
            review_rev=head_sha,
            diff_left=merge_base,
            diff_right=head_sha,
            diff_range=f"{merge_base[:12]}...{head_sha[:12]}",
            base_resolved=merge_base,
            worktree_dirty=bool(dirty_paths),
            dirty_paths=dirty_paths,
        )

    raise ScopeError(f"unsupported scope mode: {mode}")


def changed_entries(resolution: ScopeResolution) -> list[tuple[str, str]]:
    raw = _git(
        resolution.repo,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        resolution.diff_left,
        resolution.diff_right,
    ).stdout
    parts = [part for part in raw.split(b"\0") if part]
    entries: list[tuple[str, str]] = []
    index = 0
    while index + 1 < len(parts):
        status = _decode(parts[index]).strip()
        path = normalize_relpath(_decode(parts[index + 1]))
        entries.append((status[:1] or "M", path))
        index += 2
    return entries


def read_blob(repo: Path, rev: str, relpath: str) -> bytes | None:
    size_proc = _git(repo, "cat-file", "-s", f"{rev}:{relpath}", check=False)
    if size_proc.returncode != 0:
        return None
    try:
        size = int(_decode(size_proc.stdout).strip())
    except ValueError:
        return None
    if size > MAX_TEXT_FILE_BYTES:
        raise ScopeError(
            f"{relpath} is {size} bytes (> {MAX_TEXT_FILE_BYTES}); "
            "split the commit or narrow the scope instead of trimming silently"
        )
    return _git(repo, "cat-file", "blob", f"{rev}:{relpath}").stdout


def file_diff(resolution: ScopeResolution, relpath: str) -> str:
    proc = _git(
        resolution.repo,
        "diff",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        "--unified=3",
        "--no-renames",
        resolution.diff_left,
        resolution.diff_right,
        "--",
        relpath,
    )
    return _decode(proc.stdout)


@dataclass
class BlobFile:
    path: str
    status: str
    data: bytes
    sha256: str
    size: int
    role: str = "changed_file"


@dataclass
class Snapshot:
    resolution: ScopeResolution
    diff_text: str
    files: list[BlobFile] = field(default_factory=list)
    exclusions: list[ExclusionRecord] = field(default_factory=list)
    changed: list[tuple[str, str]] = field(default_factory=list)
    reviewed_paths: list[str] = field(default_factory=list)


def build_snapshot(
    resolution: ScopeResolution,
    *,
    context_files: tuple[str, ...] = (),
) -> Snapshot:
    entries = changed_entries(resolution)
    if len(entries) > MAX_CHANGED_FILES:
        raise ScopeError(
            f"{len(entries)} changed files (> {MAX_CHANGED_FILES}); "
            "split the commit or narrow the scope"
        )

    snapshot = Snapshot(resolution=resolution, diff_text="")
    seen: set[str] = set()
    diffs: list[str] = []

    for status, path in entries:
        if path in seen:
            continue
        seen.add(path)
        snapshot.changed.append((status, path))
        reason = deny_reason(path)
        if reason:
            snapshot.exclusions.append(
                ExclusionRecord(path=path, reason=reason, kind="policy")
            )
            continue
        diffs.append(file_diff(resolution, path))
        snapshot.reviewed_paths.append(path)
        if status == "D":
            continue
        data = read_blob(resolution.repo, resolution.diff_right, path)
        if data is None:
            snapshot.exclusions.append(
                ExclusionRecord(
                    path=path,
                    reason="blob not found at review revision",
                    kind="unreadable",
                )
            )
            continue
        if b"\0" in data[:BINARY_PROBE_BYTES]:
            snapshot.exclusions.append(
                ExclusionRecord(
                    path=path,
                    reason="binary content is not included; the diff records the fact",
                    kind="binary",
                )
            )
            continue
        snapshot.files.append(
            BlobFile(
                path=path,
                status=status,
                data=data,
                sha256=hashlib.sha256(data).hexdigest(),
                size=len(data),
            )
        )

    for raw_path in context_files:
        path = normalize_relpath(raw_path)
        reason = deny_reason(path)
        if reason:
            raise ScopeError(f"context file refused: {path}: {reason}")
        if path in seen:
            continue
        data = read_blob(resolution.repo, resolution.review_rev, path)
        if data is None:
            raise ScopeError(
                f"context file is not tracked at {resolution.review_rev}: {path}"
            )
        if b"\0" in data[:BINARY_PROBE_BYTES]:
            raise ScopeError(f"context file is binary: {path}")
        seen.add(path)
        snapshot.files.append(
            BlobFile(
                path=path,
                status="C",
                data=data,
                sha256=hashlib.sha256(data).hexdigest(),
                size=len(data),
                role="context",
            )
        )
        snapshot.reviewed_paths.append(path)

    snapshot.diff_text = "".join(diffs)
    if not snapshot.reviewed_paths:
        raise ScopeError("no reviewable files after policy filters")
    return snapshot


__all__ = [
    "BINARY_PROBE_BYTES",
    "BlobFile",
    "EMPTY_TREE",
    "MAX_CHANGED_FILES",
    "MAX_TEXT_FILE_BYTES",
    "ScopeError",
    "ScopeResolution",
    "Snapshot",
    "build_snapshot",
    "changed_entries",
    "deny_reason",
    "file_diff",
    "normalize_relpath",
    "read_blob",
    "resolve_commit",
    "resolve_repo_root",
    "resolve_scope",
]
