"""Tests for bump-assets.py (run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

Every test copies the script into a throwaway git repository and runs it
there, so no test can touch the real checkout even if the script under test
ignores --root.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "bump-assets.py"
OLD = "202601010000"
PAGE = (
    '<link rel="stylesheet" href="/assets/site.css?v={v}">\n'
    '<script src="/assets/site.js?v={v}"></script>\n'
)
SW = "const CACHE_VERSION = '{cv}';\nconst PRECACHE = ['/'];\n"


def git(root: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class BumpAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name) / "site"
        self.root.mkdir()
        git(self.root, "init", "-q")
        (self.root / ".gitignore").write_text(".claude/\n")
        (self.root / "index.html").write_text(PAGE.format(v=OLD))
        (self.root / "sub").mkdir()
        (self.root / "sub" / "page.html").write_text(PAGE.format(v=OLD))
        (self.root / "sw.js").write_text(SW.format(cv="gilly-" + OLD))
        nested = self.root / ".claude" / "worktrees" / "x"
        nested.mkdir(parents=True)
        self.nested = nested / "page.html"
        self.nested_text = PAGE.format(v="199901010000")
        self.nested.write_text(self.nested_text)
        self.script = self.root / "bump-assets.py"
        shutil.copy(SCRIPT, self.script)
        git(self.root, "add", "-A")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_script(self, *args: str, script: pathlib.Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(script or self.script), *args],
                              capture_output=True, text=True, cwd=self.root)

    def snapshot(self) -> dict[str, str]:
        return {str(p.relative_to(self.root)): p.read_text()
                for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}

    def test_write_skips_untracked_worktree_page(self) -> None:
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.nested.read_text(), self.nested_text)

    def test_write_stamps_tracked_pages_and_sw(self) -> None:
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        m = re.search(r"v=(\d{12}): 4 links updated", r.stdout)
        self.assertIsNotNone(m, r.stdout)
        stamp = m.group(1)
        self.assertIn(f"?v={stamp}", (self.root / "sub" / "page.html").read_text())
        self.assertIn(f"const CACHE_VERSION = 'gilly-{stamp}';", (self.root / "sw.js").read_text())

    def test_root_flag_from_outside(self) -> None:
        outside = pathlib.Path(self._tmp.name) / "tool"
        outside.mkdir()
        shutil.copy(SCRIPT, outside / "bump-assets.py")
        r = self.run_script("--root", str(self.root), script=outside / "bump-assets.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(f"?v={OLD}", (self.root / "index.html").read_text())

    def test_sw_without_cache_version_fails_and_writes_nothing(self) -> None:
        (self.root / "sw.js").write_text("const PRECACHE = ['/'];\n")
        before = self.snapshot()
        r = self.run_script()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("CACHE_VERSION", r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_writes_nothing(self) -> None:
        before = self.snapshot()
        r = self.run_script("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would update index.html (2)", r.stdout)
        self.assertIn("would update sub/page.html (2)", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_check_clean_tree_exits_0(self) -> None:
        before = self.snapshot()
        r = self.run_script("--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("STAMP ", r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_check_mixed_stamps_exits_1(self) -> None:
        (self.root / "sub" / "page.html").write_text(
            f'<link href="/assets/site.css?v=202602020000">\n<script src="/assets/site.js?v={OLD}"></script>\n')
        before = self.snapshot()
        r = self.run_script("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("STAMP sub/page.html: v=202602020000 differs from v=" + OLD, r.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_check_unstamped_link_exits_1(self) -> None:
        (self.root / "sub" / "page.html").write_text('<link href="/assets/site.css">\n')
        r = self.run_script("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("STAMP sub/page.html: unstamped link to /assets/site.css", r.stdout)

    def test_check_stale_sw_exits_1(self) -> None:
        (self.root / "sw.js").write_text(SW.format(cv="gilly-v3"))
        r = self.run_script("--check")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"STAMP sw.js: CACHE_VERSION gilly-v3 is not gilly-{OLD}", r.stdout)

    def test_check_heliograph_page_warns_only(self) -> None:
        (self.root / "heliograph").mkdir()
        (self.root / "heliograph" / "index.html").write_text('<link href="/assets/site.css">\n')
        git(self.root, "add", "-A")
        r = self.run_script("--check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARN heliograph/index.html: unstamped link to /assets/site.css", r.stdout)


if __name__ == "__main__":
    unittest.main()
