"""Negative tests for the write guard in scripts/fetch_book_figures.py.

The guard exists because the script used to default ``--workspace`` to the
current directory: running it from the program workspace wrote figures into the
production content root.  These tests pin the fail-closed behaviour so the same
mistake cannot come back silently.

The link tests keep the link target *inside* the allowed content root on
purpose.  A target outside the root would be rejected by the containment rule
first, which would prove nothing about the link rule.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "fetch_book_figures.py"


def _load():
    spec = importlib.util.spec_from_file_location("fetch_book_figures_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workspace(root: Path) -> Path:
    """A minimal workspace whose content root is ``root/content``."""
    workspace = root / "ws"
    (workspace / "config").mkdir(parents=True, exist_ok=True)
    (root / "content").mkdir(parents=True, exist_ok=True)
    (workspace / "config" / "local-paths.yaml").write_text(
        f"content_root: {root / 'content'}\n", encoding="utf-8"
    )
    return workspace


def _make_link(link: Path, real: Path) -> None:
    """Create a directory junction or symlink; fail loudly if neither works."""
    try:
        os.symlink(real, link, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    done = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)], capture_output=True
    ).returncode == 0
    if not done:
        raise AssertionError(
            "could not create a junction or symlink; the guard must be proven, not skipped"
        )


class WriteGuardTest(unittest.TestCase):
    def test_write_requires_explicit_workspace(self):
        """No --workspace and no --dry-run: refuse, and write nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            env = dict(os.environ)
            for key in ("COURSEWORKSPACE_MODE", "COURSEWORKSPACE_DEV_ROOT", "COURSEWORKSPACE_CONTENT_ROOT"):
                env.pop(key, None)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--lesson", "x", "--source-id", "y", "--figure", "1.1"],
                cwd=cwd,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("--workspace", result.stderr)
            self.assertEqual(list(cwd.iterdir()), [], "the guard must not create anything")

    def test_out_outside_allowed_root_is_refused(self):
        module = _load()
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            workspace = _workspace(root)
            outside = Path(other) / "ref_figs"
            with self.assertRaises(module.PathGuardError):
                module.guard_destination(workspace, outside)

    def test_dev_mode_refuses_a_target_outside_the_dev_root(self):
        module = _load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = _workspace(root)
            dev_root = root / "dev-root"
            target = root / "content" / "lessons" / "x" / "staging" / "ref_figs"
            env = {
                "COURSEWORKSPACE_MODE": "dev",
                "COURSEWORKSPACE_DEV_ROOT": str(dev_root),
                "COURSEWORKSPACE_DEV_WORKSPACE": str(workspace),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                with self.assertRaises(module.PathGuardError):
                    module.guard_destination(workspace, target)

    def test_link_on_the_path_is_refused_even_when_it_points_inside(self):
        """A junction inside the content root is refused for being a link."""
        module = _load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = _workspace(root)
            real = root / "content" / "lessons" / "real"
            real.mkdir(parents=True)
            link = root / "content" / "lessons" / "jlink"
            _make_link(link, real)

            # Resolves to a path inside the content root, so containment passes;
            # only the link rule can reject this.
            with self.assertRaises(module.PathGuardError) as caught:
                module.guard_destination(workspace, link / "ref_figs")
            self.assertIn("link", str(caught.exception))

    def test_base_out_itself_being_a_link_is_refused(self):
        """The target directory itself is a link; its parents are all real."""
        module = _load()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = _workspace(root)
            real = root / "content" / "targetdir"
            real.mkdir(parents=True)
            holder = root / "content" / "links"
            holder.mkdir()
            link = holder / "ref_figs"
            _make_link(link, real)

            with self.assertRaises(module.PathGuardError) as caught:
                module.guard_destination(workspace, link)
            self.assertIn("link", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
