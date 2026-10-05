"""Repo hygiene: no build artifacts tracked, and .gitignore keeps them out.

tools/tests/__pycache__/*.pyc is tracked on master (an older accident that is
not untracked here); it is the only place a .pyc may be tracked.
"""
from __future__ import annotations

import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWED_PREFIX = "tools/tests/__pycache__/"


class RepoHygieneTest(unittest.TestCase):
    def test_no_tracked_pyc_outside_the_master_exception(self):
        try:
            out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        bad = [p for p in out.splitlines()
               if (p.endswith(".pyc") or "/__pycache__/" in p or p.startswith("__pycache__/"))
               and not p.startswith(ALLOWED_PREFIX)]
        self.assertEqual(bad, [], "tracked build artifacts: %s" % bad)

    def test_gitignore_excludes_pycache_and_pyc(self):
        lines = {l.strip() for l in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()}
        self.assertIn("__pycache__/", lines)
        self.assertIn("*.pyc", lines)


if __name__ == "__main__":
    unittest.main()
