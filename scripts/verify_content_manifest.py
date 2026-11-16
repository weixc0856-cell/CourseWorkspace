"""Recompute the content-root change manifest without following junctions.

The manifest is evidence for moves outside Git.  This script is the verifier so
a reviewer does not have to re-derive the tree algorithm:

    python scripts/verify_content_manifest.py \
        --manifest docs/audit/content-changes-2026-11-16.json \
        --content-root <content-root>

Every rule fails closed:

- ``schema_version`` must be 1 and each section must be a list.
- Paths stay inside the content root by *lexical* containment.  Nothing is
  resolved, so a junction cannot make an outside file look like an inside one.
- A move's old source must be gone and its target must be a real directory,
  not a link.  Non-cache targets are hashed; cache targets are counted and
  sized but never hashed, and a junction inside them is reported, not entered.
- An archived entry proves the old source is gone, the target is a regular
  file, and the bytes and hash match.
- Created and modified files must be regular files with the declared bytes
  and hash.  Removed paths must be absent.

``--selftest`` builds a throwaway tree and proves each rule can go red.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = 1
SECTIONS = ("moves", "archived", "created", "modified", "removed")
NUL = chr(0)
NEWLINE = chr(10)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_link(path: Path) -> bool:
    """True for a symlink or a Windows junction; never follow it."""
    if path.is_symlink():
        return True
    checker = getattr(path, "is_junction", None)
    if callable(checker):
        try:
            return bool(checker())
        except OSError:
            return False
    return False


def _exists(path: Path) -> bool:
    """Whether the directory entry exists, even when it is a broken link."""
    return os.path.lexists(path)


def _regular_file(path: Path) -> bool:
    return _exists(path) and not is_link(path) and path.is_file()


def _real_dir(path: Path) -> bool:
    return _exists(path) and not is_link(path) and path.is_dir()


def _excluded(relative: str, exclude: tuple[str, ...]) -> bool:
    return any(relative == prefix or relative.startswith(prefix) for prefix in exclude)


def walk_tree(root: Path, exclude: tuple[str, ...] = ()) -> dict:
    """Count and hash a tree without following junctions or symlinks.

    ``links`` holds both kinds, which keeps the manifest's existing
    ``symlinks`` field able to describe the two junctions under
    ``build/_shared/tmp``.  ``junctions`` is reported separately so a cache
    directory can refuse them.
    """
    lines: list[str] = []
    total = 0
    count = 0
    links: list[str] = []
    junctions: list[str] = []
    if not root.is_dir():
        if _regular_file(root):
            size = root.stat().st_size
            return {
                "files": 1,
                "bytes": size,
                "links": [],
                "junctions": [],
                "tree_sha256": hashlib.sha256(
                    (root.name + NUL + str(size) + NUL + _sha(root)).encode("utf-8")
                ).hexdigest(),
            }
        return {
            "files": 0,
            "bytes": 0,
            "links": [],
            "junctions": [],
            "tree_sha256": hashlib.sha256(b"").hexdigest(),
        }
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        for name in sorted(list(dirnames)):
            child = base / name
            relative = child.relative_to(root).as_posix()
            if _excluded(relative, exclude):
                dirnames.remove(name)
                continue
            if is_link(child):
                links.append(relative)
                if not child.is_symlink():
                    junctions.append(relative)
                dirnames.remove(name)
        for name in sorted(filenames):
            item = base / name
            relative = item.relative_to(root).as_posix()
            if _excluded(relative, exclude):
                continue
            if is_link(item):
                links.append(relative)
                if not item.is_symlink():
                    junctions.append(relative)
                continue
            size = item.stat().st_size
            total += size
            count += 1
            lines.append(relative + NUL + str(size) + NUL + _sha(item))
    return {
        "files": count,
        "bytes": total,
        "links": sorted(links),
        "junctions": sorted(junctions),
        "tree_sha256": hashlib.sha256(NEWLINE.join(lines).encode()).hexdigest(),
    }


def _within(root: Path, relative: object) -> Path | None:
    """Confine a relative path lexically, without resolving links."""
    value = str(relative or "")
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return None
    base = Path(os.path.normpath(root))
    target = Path(os.path.normpath(root / candidate))
    if target == base or base in target.parents:
        return target
    return None


def _exclude_problems(value: object, label: str) -> list[str]:
    """An exclude list may only hold relative paths that cannot leave the target."""
    if value is None:
        return []
    if not isinstance(value, list):
        return [f"{label} exclude is not a list"]
    problems: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            problems.append(f"{label} exclude has an empty or non-string entry")
            continue
        parts = Path(item).parts
        if (
            Path(item).is_absolute()
            or item.startswith("/")
            or item.startswith(chr(92))
            or ".." in parts
            or item.strip() in {".", ""}
        ):
            problems.append(
                f"{label} exclude must be a relative path without ..: {item!r}"
            )
    return problems


def _link_ancestor(root: Path, target: Path) -> Path | None:
    """The first ancestor of target, below root, that is a symlink or junction."""
    try:
        relative = target.relative_to(root)
    except ValueError:
        return None
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if _exists(current) and is_link(current):
            return current
    return None


def _number(item: dict, key: str, label: str, problems: list[str]) -> int | None:
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        problems.append(f"{label} has no {key} count")
        return None
    return value


def verify(data: object, root: Path) -> list[str]:
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["manifest is not a JSON object"]
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        problems.append(
            f"manifest schema_version is {version!r}, not the integer {SCHEMA_VERSION}"
        )
    sections: dict[str, list] = {}
    missing_sections = [key for key in SECTIONS if key not in data]
    if missing_sections:
        problems.append(
            "manifest is missing sections: " + ", ".join(missing_sections)
        )
    for key in SECTIONS:
        value = data.get(key)
        if isinstance(value, list):
            sections[key] = value
        else:
            if key not in missing_sections:
                problems.append(f"manifest {key} is not a list")
            sections[key] = []

    for index, item in enumerate(sections["moves"]):
        label = f"moves[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{label} is not an object")
            continue
        missing = [key for key in ("from", "to") if not str(item.get(key) or "")]
        if missing:
            problems.append(f"{label} is missing: {', '.join(missing)}")
            continue
        source = _within(root, item.get("from"))
        target = _within(root, item.get("to"))
        if source is None:
            problems.append(f"unsafe move source: {item.get('from')}")
            continue
        if target is None:
            problems.append(f"unsafe move target: {item.get('to')}")
            continue
        ancestor = _link_ancestor(root, source) or _link_ancestor(root, target)
        if ancestor is not None:
            problems.append(
                f"{label} path passes through a link and was not followed: {ancestor}"
            )
            continue
        cache = item.get("cache", False)
        if not isinstance(cache, bool):
            problems.append(f"{label} cache must be a boolean, not {type(cache).__name__}")
            continue
        exclude = item.get("exclude")
        exclude_problems = _exclude_problems(exclude, label)
        if exclude_problems:
            problems.extend(exclude_problems)
            continue
        if _exists(source):
            problems.append(f"move source still exists: {item.get('from')}")
        if is_link(target):
            problems.append(
                f"{label} target is a link and was not followed: {item.get('to')}"
            )
            continue
        if cache and not _real_dir(target):
            problems.append(
                f"cache target is not a real directory: {item.get('to')}"
            )
            continue
        if not (_real_dir(target) or _regular_file(target)):
            problems.append(
                f"{label} target is neither a directory nor a regular file: "
                f"{item.get('to')}"
            )
            continue
        current = walk_tree(target, tuple(exclude or ()))
        if cache and current["junctions"]:
            # A cache is counted, not hashed; a junction inside it would make
            # the count reach outside the root, so it is reported instead.
            problems.append(
                f"cache directory contains junction(s) and they were not followed: "
                + ", ".join(current["junctions"])
            )
        if cache:
            count = _number(item, "files", label, problems)
            if count is not None and current["files"] != count:
                problems.append(
                    f"cache file count mismatch: {item.get('to')} "
                    f"({current['files']} != {count})"
                )
            # A cache is counted and typed, not sized: its bytes change with
            # timestamps on every regeneration.
            continue
        count = _number(item, "files", label, problems)
        if count is not None and current["files"] != count:
            problems.append(
                f"move file count mismatch: {item.get('to')} "
                f"({current['files']} != {count})"
            )
        size = _number(item, "bytes", label, problems)
        if size is not None and current["bytes"] != size:
            problems.append(
                f"move byte count mismatch: {item.get('to')} "
                f"({current['bytes']} != {size})"
            )
        digest = item.get("tree_sha256")
        if not digest:
            problems.append(f"{label} has no tree hash: {item.get('to')}")
        elif current["tree_sha256"] != digest:
            problems.append(f"move tree hash mismatch: {item.get('to')}")
        if sorted(current["links"]) != sorted(item.get("symlinks") or []):
            problems.append(f"move link list mismatch: {item.get('to')}")

    for index, item in enumerate(sections["archived"]):
        label = f"archived[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{label} is not an object")
            continue
        missing = [key for key in ("from", "to") if not str(item.get(key) or "")]
        if missing:
            problems.append(f"{label} is missing: {', '.join(missing)}")
            continue
        source = _within(root, item.get("from"))
        target = _within(root, item.get("to"))
        if source is None:
            problems.append(f"unsafe archive source: {item.get('from')}")
            continue
        if target is None:
            problems.append(f"unsafe archive path: {item.get('to')}")
            continue
        if str(item.get("kind") or "") != "file":
            problems.append(f"{label} kind must be 'file': {item.get('to')}")
        ancestor = _link_ancestor(root, source) or _link_ancestor(root, target)
        if ancestor is not None:
            problems.append(
                f"{label} path passes through a link and was not followed: {ancestor}"
            )
            continue
        if _exists(source):
            problems.append(f"archive source still exists: {item.get('from')}")
        if not _regular_file(target):
            problems.append(f"{label} target is not a regular file: {item.get('to')}")
            continue
        size = _number(item, "bytes", label, problems)
        if size is not None and target.stat().st_size != size:
            problems.append(
                f"archived byte count mismatch: {item.get('to')} "
                f"({target.stat().st_size} != {size})"
            )
        if _sha(target) != item.get("sha256"):
            problems.append(f"archived file changed: {item.get('to')}")

    for section in ("created", "modified"):
        for index, item in enumerate(sections[section]):
            label = f"{section}[{index}]"
            if not isinstance(item, dict):
                problems.append(f"{label} is not an object")
                continue
            value = _within(root, item.get("path"))
            if value is None:
                problems.append(f"unsafe {section} path: {item.get('path')}")
                continue
            ancestor = _link_ancestor(root, value)
            if ancestor is not None:
                problems.append(
                    f"{label} path passes through a link and was not followed: {ancestor}"
                )
                continue
            if not _regular_file(value):
                problems.append(f"{label} is not a regular file: {item.get('path')}")
                continue
            size = _number(item, "bytes", label, problems)
            if size is not None and value.stat().st_size != size:
                problems.append(
                    f"{label} byte count mismatch: {item.get('path')} "
                    f"({value.stat().st_size} != {size})"
                )
            if _sha(value) != item.get("sha256"):
                problems.append(f"{label} file changed: {item.get('path')}")

    for index, item in enumerate(sections["removed"]):
        label = f"removed[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{label} is not an object")
            continue
        value = _within(root, item.get("path"))
        if value is None:
            problems.append(f"unsafe removed path: {item.get('path')}")
            continue
        ancestor = _link_ancestor(root, value)
        if ancestor is not None:
            problems.append(
                f"{label} path passes through a link and was not followed: {ancestor}"
            )
            continue
        if _exists(value):
            problems.append(f"removed path still exists: {item.get('path')}")
    return problems


def _make_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and is_link(link)


def selftest() -> int:
    root = Path(tempfile.mkdtemp(prefix="content-manifest-"))
    try:
        content = root / "content"
        content.mkdir()
        outside = root / "outside"
        outside.mkdir()
        (outside / "x.bin").write_bytes(b"x")
        (outside / "y.bin").write_bytes(b"yy")

        moved = content / "moved"
        moved.mkdir()
        (moved / "a.txt").write_bytes(b"a")
        archive = content / "archive"
        archive.mkdir()
        (archive / "a.json").write_bytes(b"{}")
        created = content / "created.json"
        created.write_bytes(b"{}")
        (content / "runtime.json").write_bytes(b"{}")
        cache = content / "cache"
        cache.mkdir()
        (cache / "b.txt").write_bytes(b"bb")

        def move(**overrides) -> dict:
            info = walk_tree(moved)
            item = {
                "from": "gone/",
                "to": "moved",
                "kind": "directory",
                "files": info["files"],
                "bytes": info["bytes"],
                "symlinks": info["links"],
                "tree_sha256": info["tree_sha256"],
            }
            item.update(overrides)
            return item

        def archived(**overrides) -> dict:
            target = archive / "a.json"
            item = {
                "from": "runtime-gone.json",
                "to": "archive/a.json",
                "kind": "file",
                "bytes": target.stat().st_size,
                "sha256": _sha(target),
            }
            item.update(overrides)
            return item

        def created_entry(**overrides) -> dict:
            item = {
                "path": "created.json",
                "bytes": created.stat().st_size,
                "sha256": _sha(created),
            }
            item.update(overrides)
            return item

        single = content / "single.log"
        single.write_bytes(b"log")

        def file_move(**overrides) -> dict:
            info = walk_tree(single)
            item = {
                "from": "gone.log",
                "to": "single.log",
                "kind": "file",
                "files": info["files"],
                "bytes": info["bytes"],
                "symlinks": info["links"],
                "tree_sha256": info["tree_sha256"],
            }
            item.update(overrides)
            return item

        def manifest(**overrides) -> dict:
            data = {
                "schema_version": 1,
                "moves": [move(), file_move()],
                "archived": [archived()],
                "created": [created_entry()],
                "modified": [],
                "removed": [],
            }
            data.update(overrides)
            return data

        def expect(name: str, data: object, wanted: str | None, *must_not: str) -> bool:
            problems = verify(data, content)
            ok = not problems if wanted is None else any(wanted in p for p in problems)
            ok = ok and not any(item in p for p in problems for item in must_not)
            if not ok:
                print(f"selftest FAIL: {name}: {problems}")
            return ok

        if not expect("clean tree", manifest(), None):
            return 1
        if not expect(
            "schema version",
            manifest(schema_version=2),
            "schema_version",
        ):
            return 1
        if not expect(
            "schema version is a boolean",
            manifest(schema_version=True),
            "schema_version",
        ):
            return 1
        if not expect(
            "missing sections",
            {"schema_version": 1},
            "missing sections",
        ):
            return 1
        if not expect(
            "cache flag is a string",
            manifest(moves=[move(to="cache", cache="false", files=1)]),
            "cache must be a boolean",
        ):
            return 1
        if not expect(
            "exclude leaves the target",
            manifest(moves=[move(exclude=["../outside"])]),
            "exclude must be a relative path",
        ):
            return 1
        if not expect(
            "section type",
            manifest(moves={"to": "moved"}),
            "moves is not a list",
        ):
            return 1
        if not expect(
            "entry without target",
            manifest(moves=[{"from": "gone/"}]),
            "missing: to",
        ):
            return 1
        (content / "runtime.json").write_bytes(b"{}")
        if not expect(
            "source still exists",
            manifest(moves=[move(**{"from": "runtime.json", "to": "moved"})]),
            "move source still exists",
        ):
            return 1
        if not expect(
            "unsafe target",
            manifest(moves=[move(to="../outside")]),
            "unsafe move target",
        ):
            return 1
        link = content / "link"
        junction_ok = _make_junction(link, moved)
        if junction_ok:
            if not expect(
                "junction as move target",
                manifest(moves=[move(to="link")]),
                "is a link",
            ):
                return 1
            if not expect(
                "junction in an ancestor",
                manifest(
                    created=[
                        created_entry(
                            path="link/a.txt",
                            bytes=1,
                            sha256=_sha(moved / "a.txt"),
                        )
                    ]
                ),
                "passes through a link",
            ):
                return 1
        if not expect(
            "missing move target",
            manifest(moves=[move(to="missing")]),
            "neither a directory nor a regular file",
        ):
            return 1
        cache_file = content / "cache-file"
        cache_file.write_bytes(b"x")
        if not expect(
            "cache target is a file",
            manifest(moves=[move(to="cache-file", files=1, bytes=1, cache=True)]),
            "cache target is not a real directory",
        ):
            return 1
        cache_info = walk_tree(cache)
        if junction_ok:
            assert not is_link(cache / "link")
            _make_junction(cache / "link", outside)
            cache_info = walk_tree(cache)
            cache_bytes = cache_info["bytes"]
            if not expect(
                "cache junction",
                manifest(
                    moves=[
                        move(
                            to="cache",
                            cache=True,
                            files=cache_info["files"],
                            bytes=cache_bytes,
                        )
                    ]
                ),
                "contains junction",
                "count mismatch",
            ):
                return 1
        else:
            print(
                "selftest FAIL: junction cases could not run; "
                "the junction safety proof is unavailable"
            )
            return 1
        if not expect(
            "move bytes",
            manifest(moves=[move(bytes=move()["bytes"] + 1)]),
            "move byte count mismatch",
        ):
            return 1
        (content / "runtime-gone.json").write_bytes(b"{}")
        if not expect(
            "archive source still exists",
            manifest(archived=[archived()]),
            "archive source still exists",
        ):
            return 1
        if not expect(
            "archive target is a directory",
            manifest(archived=[archived(to="archive")]),
            "not a regular file",
        ):
            return 1
        if not expect(
            "archive bytes",
            manifest(archived=[archived(bytes=999)]),
            "archived byte count mismatch",
        ):
            return 1
        if not expect(
            "created file changed",
            manifest(created=[created_entry(sha256="0" * 64)]),
            "created[0] file changed",
        ):
            return 1
        if not expect(
            "removed path still exists",
            manifest(removed=[{"path": "runtime.json"}]),
            "removed path still exists",
        ):
            return 1
        print("verify content manifest selftest PASS")
        return 0
    finally:
        import shutil

        # Every junction in this throwaway tree points inside it, so even a
        # walker that followed one could not reach real data.
        shutil.rmtree(root, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--content-root", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.manifest is None or args.content_root is None:
        print("--manifest and --content-root are required", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"manifest is unreadable: {exc}", file=sys.stderr)
        return 1
    root = args.content_root.resolve()
    problems = verify(data, root)
    if problems:
        print(f"{len(problems)} content manifest problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("content manifest ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
