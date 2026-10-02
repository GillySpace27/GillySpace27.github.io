"""assets/sun.js under Node as a bare runtime (no npm): the WS-5 loader and the WS-15 Stage helpers.

Skipped where node is not installed; CI has node 22.
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py')
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node is not installed")
class SunJsTest(unittest.TestCase):
    def run_check(self, name: str) -> str:
        r = subprocess.run([NODE, str(REPO / "tools" / "tests" / "js" / name), str(REPO)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_loader(self):
        self.assertIn("sun.js: ok", self.run_check("sun_js_check.mjs"))

    def test_stage_helpers(self):
        self.assertIn("sun stage: ok", self.run_check("sun_stage_check.mjs"))

    def test_no_em_dash_in_sun_js(self):
        self.assertNotIn("—", (REPO / "assets" / "sun.js").read_text(encoding="utf-8"))

    def test_stage_dom_the_script_queries_is_in_sun_html(self):
        js = (REPO / "assets" / "sun.js").read_text(encoding="utf-8")
        page = (REPO / "sun.html").read_text(encoding="utf-8")
        wanted = set(re.findall(r'querySelector\("#(stage-[a-z]+)"\)', js))
        self.assertGreaterEqual(len(wanted), 9, wanted)
        for ident in sorted(wanted):
            self.assertEqual(page.count(f'id="{ident}"'), 1, ident)


if __name__ == "__main__":
    unittest.main()
