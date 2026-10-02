"""Tests for heliosoftware/spec/tools/no_em_dash.py (suite SU-10).

The dash is built with chr(0x2014) so this file never contains the character.
Run: python3 -m unittest discover -s tools/tests -p 'test_no_em_dash.py' -v
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "heliosoftware" / "spec" / "tools" / "no_em_dash.py"
_spec = importlib.util.spec_from_file_location("no_em_dash", TOOL)
nd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nd)

D = chr(0x2014)

DIFF = "\n".join([
    "diff --git a/a.txt b/a.txt",
    "--- a/a.txt",
    "+++ b/a.txt",
    "@@ -1,0 +2,2 @@",
    "+clean line",
    f"+dash {D} here",
    "@@ -10 +12 @@",
    f"-old {D}",
    "+new clean",
    "diff --git a/new.md b/new.md",
    "new file mode 100644",
    "--- /dev/null",
    "+++ b/new.md",
    "@@ -0,0 +1,3 @@",
    "+one",
    "+two",
    f"+{D}three",
    "",
])


def run_tool(*args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=cwd, input=stdin,
                          capture_output=True, text=True)


class AddedHits(unittest.TestCase):
    def test_only_added_lines_with_new_line_numbers(self):
        self.assertEqual(nd.added_hits(DIFF), [("a.txt", 3), ("new.md", 3)])

    def test_removed_and_context_lines_are_not_flagged(self):
        diff = "\n".join(["--- a/x", "+++ b/x", "@@ -1,2 +1,2 @@", f" context {D}", f"-gone {D}", "+fine", ""])
        self.assertEqual(nd.added_hits(diff), [])

    def test_content_that_looks_like_a_file_header_is_still_content(self):
        diff = "\n".join(["--- a/b.txt", "+++ b/b.txt", "@@ -1 +1 @@", "--- old", f"+++ new {D}", ""])
        self.assertEqual(nd.added_hits(diff), [("b.txt", 1)])

    def test_no_newline_marker_does_not_shift_lines(self):
        diff = "\n".join(["--- a/c", "+++ b/c", "@@ -1 +1,2 @@", "-a", "\\ No newline at end of file",
                          "+b", "\\ No newline at end of file", f"+{D}", ""])
        self.assertEqual(nd.added_hits(diff), [("c", 2)])


class Cli(unittest.TestCase):
    def test_stdin_mode(self):
        r = run_tool("--stdin", stdin=DIFF)
        self.assertEqual((r.returncode, r.stdout), (1, "a.txt:3\nnew.md:3\n"))

    def test_clean_stdin_passes(self):
        r = run_tool("--stdin", stdin="--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+fine\n")
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_exclude_glob(self):
        r = run_tool("--stdin", "--exclude", "*.md", stdin=DIFF)
        self.assertEqual((r.returncode, r.stdout), (1, "a.txt:3\n"))


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=cwd, check=True, capture_output=True)


class GitMode(unittest.TestCase):
    def test_old_dash_passes_new_dash_fails_unknown_base_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            repo = pathlib.Path(d)
            git(repo, "init", "-q", "-b", "main")
            (repo / "f.txt").write_text(f"old {D} text\n", encoding="utf-8")
            git(repo, "add", "f.txt")
            git(repo, "commit", "-q", "-m", "base")
            git(repo, "switch", "-q", "-c", "topic")
            (repo / "f.txt").write_text(f"old {D} text\nsecond line\n", encoding="utf-8")
            git(repo, "commit", "-q", "-am", "clean addition")
            r = run_tool("--base", "main", cwd=repo)
            self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
            (repo / "f.txt").write_text(f"old {D} text\nsecond line\nthird {D}\n", encoding="utf-8")
            git(repo, "commit", "-q", "-am", "dash addition")
            r = run_tool("--base", "main", cwd=repo)
            self.assertEqual((r.returncode, r.stdout), (1, "f.txt:3\n"))
            r = run_tool("--base", "no-such-ref", cwd=repo)
            self.assertEqual(r.returncode, 2)
            self.assertIn("no_em_dash:", r.stderr)


if __name__ == "__main__":
    unittest.main()
