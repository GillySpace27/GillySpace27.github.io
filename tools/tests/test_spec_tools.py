"""Tests for the stdlib tools under heliosoftware/spec/ and for the folder itself.

Run from the Website root:  python3 -m unittest tools.tests.test_spec_tools
or:                         python3 -m unittest discover -s tools/tests -p 'test_*.py'
Each tool is imported by path, so the working directory does not matter.
"""
import contextlib
import hashlib
import importlib.util
import io
import os
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True      # never leave __pycache__ inside spec/
ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "heliosoftware" / "spec"


def load_tool(rel):
    """Import heliosoftware/spec/<rel> by path; FileNotFoundError when it does not exist."""
    path = SPEC / rel
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(mod, *argv):
    """Call mod.main(argv) and return (exit code, captured stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = mod.main(list(argv))
        except SystemExit as err:
            code = err.code
    return code, out.getvalue()


def sha(data):
    return hashlib.sha256(data).hexdigest()


class SpecSumsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool("spec_sums.py")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)
        (self.dir / "a.txt").write_text("alpha\n")
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "b.txt").write_text("beta\n")

    def sums(self, flag):
        return run(self.tool, flag, "--dir", str(self.dir))

    def test_write_then_check(self):
        code, out = self.sums("--write")
        self.assertEqual((code, out), (0, "spec_sums: wrote 2 entries\n"))
        text = (self.dir / "SHA256SUMS").read_text()
        self.assertEqual(text, f"{sha(b'alpha' + bytes([10]))}  a.txt\n{sha(b'beta' + bytes([10]))}  sub/b.txt\n")
        first = (self.dir / "SHA256SUMS").read_bytes()
        self.sums("--write")
        self.assertEqual((self.dir / "SHA256SUMS").read_bytes(), first, "a second write is byte-identical")
        code, out = self.sums("--check")
        self.assertEqual((code, out), (0, "spec_sums: 2 files match SHA256SUMS\n"))

    def test_changed_byte_is_a_mismatch(self):
        self.sums("--write")
        (self.dir / "a.txt").write_text("alphb\n")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("MISMATCH a.txt\n", out)
        self.assertIn("spec_sums: 1 problem(s)", out)

    def test_new_file_is_extra(self):
        self.sums("--write")
        (self.dir / "c.txt").write_text("gamma\n")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("EXTRA c.txt\n", out)

    def test_removed_file_is_missing(self):
        self.sums("--write")
        os.remove(self.dir / "sub" / "b.txt")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("MISSING sub/b.txt\n", out)

    def test_excluded_paths_are_not_listed(self):
        (self.dir / ".claude" / "worktrees" / "w").mkdir(parents=True)
        (self.dir / ".claude" / "worktrees" / "w" / "x.txt").write_text("worktree\n")
        (self.dir / "__pycache__").mkdir()
        (self.dir / "__pycache__" / "m.cpython-311.pyc").write_bytes(b"pyc")
        (self.dir / "top.pyc").write_bytes(b"pyc")
        (self.dir / ".DS_Store").write_bytes(b"ds")
        self.sums("--write")
        listed = [ln.split("  ", 1)[1] for ln in (self.dir / "SHA256SUMS").read_text().splitlines()]
        self.assertEqual(listed, ["a.txt", "sub/b.txt"])
        self.assertEqual(self.sums("--check")[0], 0)

    def test_missing_sums_file(self):
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("MISSING SHA256SUMS", out)

    def test_malformed_line(self):
        (self.dir / "SHA256SUMS").write_text("not a hash line\n")
        code, out = self.sums("--check")
        self.assertEqual(code, 1)
        self.assertIn("SHA256SUMS:1", out)


# end of spec tool tests
if __name__ == "__main__":
    unittest.main()
