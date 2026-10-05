"""Tests for heliosoftware/spec/tools/diff_luts.py (suite SU-12).

Run: python3 -m unittest discover -s tools/tests -p 'test_diff_luts.py' -v
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "heliosoftware" / "spec" / "tools" / "diff_luts.py"
_spec = importlib.util.spec_from_file_location("diff_luts", TOOL)
dl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dl)

RAMP = [[i, 255 - i, (i * 3) % 256] for i in range(256)]
GGR_BW = ("GIMP Gradient\nName: test\n1\n"
          "0.000000 0.500000 1.000000 0.000000 0.000000 0.000000 1.000000 1.000000 1.000000 1.000000 1.000000 0 0 0 0\n")


class Diff(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.t = pathlib.Path(tmp.name)
        (self.t / "ref").mkdir()
        (self.t / "cand").mkdir()
        self.put(self.t / "ref" / "sdoaia171.json", "sdoaia171", RAMP)

    def put(self, path, name, rgb):
        path.write_text(json.dumps({"name": name, "source": "t", "rgb": rgb}), encoding="utf-8")

    def run_tool(self, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = dl.main(["--ref", str(self.t / "ref"), *extra])
        return code, buf.getvalue()

    def test_identical_table_is_ok(self):
        self.put(self.t / "cand" / "sdoaia171.json", "sdoaia171", RAMP)
        code, out = self.run_tool("--candidate", str(self.t / "cand"))
        self.assertEqual(code, 0)
        self.assertIn("sdoaia171 maxdiff=0 OK", out)
        self.assertIn("diff_luts: 1 compared, 0 over tol", out)

    def test_a_seeded_wrong_table_fails(self):
        wrong = [list(row) for row in RAMP]
        wrong[100][1] += 5
        self.put(self.t / "cand" / "sdoaia171.json", "sdoaia171", wrong)
        code, out = self.run_tool("--candidate", str(self.t / "cand"))
        self.assertEqual(code, 1)
        self.assertIn("sdoaia171 maxdiff=5 OVER", out)
        code, out = self.run_tool("--candidate", str(self.t / "cand"), "--tol", "5")
        self.assertEqual(code, 0)
        self.assertIn("sdoaia171 maxdiff=5 OK", out)

    def test_csv_candidate_and_an_unknown_name(self):
        rows = "# SOURCE: t\nr,g,b\n" + "\n".join("%d,%d,%d" % tuple(r) for r in RAMP) + "\n"
        (self.t / "cand" / "sdoaia171.csv").write_text(rows, encoding="utf-8")
        (self.t / "cand" / "other.csv").write_text(rows, encoding="utf-8")
        code, out = self.run_tool("--candidate", str(self.t / "cand"))
        self.assertEqual(code, 0)
        self.assertIn("sdoaia171 maxdiff=0 OK", out)
        self.assertIn("NOREF other", out)

    def test_gimp_gradient_ends_and_length(self):
        name, rgb = dl.load_ggr_text(GGR_BW, "t.ggr")
        self.assertEqual(name, "test")
        self.assertEqual(len(rgb), 256)
        self.assertEqual((rgb[0], rgb[255]), ([0, 0, 0], [255, 255, 255]))
        self.assertTrue(all(rgb[i][0] <= rgb[i + 1][0] for i in range(255)))
        rev = GGR_BW.replace("0.000000 0.000000 0.000000 1.000000 1.000000 1.000000 1.000000 1.000000",
                             "1.000000 1.000000 1.000000 1.000000 0.000000 0.000000 0.000000 1.000000")
        _, rgb = dl.load_ggr_text(rev, "t.ggr")
        self.assertEqual((rgb[0], rgb[255]), ([255, 255, 255], [0, 0, 0]))

    def test_aia_ggr_file_maps_to_the_sdoaia_name(self):
        (self.t / "cand" / "AIA171.ggr").write_text(GGR_BW, encoding="utf-8")
        _, own = dl.load_ggr_text(GGR_BW, "AIA171.ggr")
        self.put(self.t / "ref" / "sdoaia171.json", "sdoaia171", own)
        code, out = self.run_tool("--candidate", str(self.t / "cand"))
        self.assertEqual(code, 0)
        self.assertIn("sdoaia171 maxdiff=0 OK", out)

    def test_hsv_segments_are_unchecked_not_wrong(self):
        hsv = GGR_BW.replace(" 0 0 0 0\n", " 0 1 0 0\n")
        (self.t / "cand" / "AIA171.ggr").write_text(hsv, encoding="utf-8")
        code, out = self.run_tool("--candidate", str(self.t / "cand"))
        self.assertEqual(code, 0)
        self.assertIn("UNCHECKED", out)
        self.assertIn("HSV", out)

    def test_unreadable_reference_is_exit_2(self):
        (self.t / "ref" / "broken.json").write_text("{", encoding="utf-8")
        code, _ = self.run_tool("--candidate", str(self.t / "cand"))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
