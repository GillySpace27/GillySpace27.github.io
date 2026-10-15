"""Tests for heliosoftware/spec/tools/tokens.py (suite SU-20).

Run: python3 -m unittest discover -s tools/tests -p 'test_tokens.py' -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "heliosoftware" / "spec" / "tools" / "tokens.py"
_spec = importlib.util.spec_from_file_location("tokens", TOOL)
tk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tk)

SITE_CSS = ROOT / "assets" / "site.css"


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = tk.main(list(argv))
    return code, out.getvalue()


class Tokens(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.t = pathlib.Path(tmp.name)

    def copy(self, text=None):
        p = self.t / "x.css"
        p.write_text(SITE_CSS.read_text(encoding="utf-8") if text is None else text, encoding="utf-8")
        return p

    def test_site_css_matches_the_spec(self):
        code, out = run("--check", str(SITE_CSS))
        self.assertEqual(code, 0, out)

    def test_seeded_drift_fails_and_write_restores_the_file_byte_for_byte(self):
        p = self.copy()
        p.write_text(p.read_text().replace("--rule: #3a362c;", "--rule: #3a362d;", 1))
        code, out = run("--check", str(p))
        self.assertEqual(code, 1)
        self.assertIn("DRIFT", out)
        self.assertIn(":root.dark --rule", out)
        code, out = run("--write", str(p))
        self.assertEqual(code, 0, out)
        self.assertEqual(p.read_text(), SITE_CSS.read_text())

    def test_missing_token_is_reported_and_written_back(self):
        p = self.copy()
        p.write_text(p.read_text().replace("  --maxw: 1080px;           /* page container        */\n", "", 1))
        code, out = run("--check", str(p))
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)
        self.assertEqual(run("--write", str(p))[0], 0)
        self.assertEqual(run("--check", str(p))[0], 0)

    def test_extra_token_stays_and_keeps_the_check_red(self):
        p = self.copy()
        p.write_text(p.read_text().replace("  --bg: #1a1814;\n", "  --bg: #1a1814;\n  --new: red;\n", 1))
        self.assertEqual(run("--check", str(p))[0], 1)
        code, out = run("--write", str(p))
        self.assertEqual(code, 1)
        self.assertIn("EXTRA", out)
        self.assertIn("--new: red;", p.read_text())

    def test_file_without_a_block_is_a_usage_error_and_is_not_written(self):
        p = self.copy(":root { --bg: #fff; }\n")
        self.assertEqual(run("--check", str(p))[0], 2)
        self.assertEqual(run("--write", str(p))[0], 2)
        self.assertEqual(p.read_text(), ":root { --bg: #fff; }\n")

    def test_empty_block_gets_both_rules(self):
        p = self.copy(f"body{{}}\n{tk.BEGIN}\n{tk.END}\n")
        self.assertEqual(run("--write", str(p))[0], 0)
        text = p.read_text()
        self.assertIn(":root {", text)
        self.assertIn(":root.dark {", text)
        self.assertEqual(run("--check", str(p))[0], 0)


if __name__ == "__main__":
    unittest.main()
