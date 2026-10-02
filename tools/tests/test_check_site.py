"""Tests for tools/check_site.py (run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

Each bad fixture under tools/tests/fixtures/ must fail with its own message,
and ok-site must pass every rule, so no rule can pass by never firing.
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402

FIX = TOOLS / "tests" / "fixtures"


def lines(findings) -> list[str]:
    return [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]


class FixtureTest(unittest.TestCase):
    def run_on(self, name_or_path, only=None):
        root = name_or_path if isinstance(name_or_path, pathlib.Path) else FIX / name_or_path
        code, findings = check_site.run(root, only)
        return code, lines(findings)

    def copy(self, name: str) -> pathlib.Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dst = pathlib.Path(tmp.name) / name
        shutil.copytree(FIX / name, dst)
        return dst

    def test_ok_site_passes_every_rule(self):
        code, out = self.run_on("ok-site")
        self.assertEqual(code, 0, "\n".join(out))
        self.assertEqual([ln for ln in out if not ln.startswith("SKIP ")], [])

    def test_bad_case_link(self):
        code, out = self.run_on("bad-case-link", ["link"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL link index.html:3 /JHV/ :: no tracked file for /JHV/"
                      " (case differs: tracked as jhv/index.html)", out)

    def test_stub_to_nowhere(self):
        code, out = self.run_on("stub-to-nowhere", ["stub"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL stub hfs/index.html:4 https://gilly.space/heliofits-studio/ :: "
                      "redirect target is not a tracked page", out)

    def test_missing_enclosure(self):
        code, out = self.run_on("missing-enclosure", ["feed"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL feed heliograph/appcast.xml:7 https://gilly.space/heliograph/Heliograph-0.7.dmg :: "
                      "enclosure is not tracked; signed update downloads would 404", out)

    def test_no_legacy_appcast(self):
        code, out = self.run_on("no-legacy-appcast", ["feed"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL feed heliograph/appcast.xml:0 - :: "
                      "update feed file is not tracked; installed apps poll this URL", out)

    def test_oversize_file(self):
        root = self.copy("oversize-file")
        for name in ("big.bin", "allowed.bin"):
            with open(root / name, "wb") as fh:
                fh.truncate(check_site.SIZE_LIMIT_BYTES + 1)   # sparse: no real disk use
        code, out = self.run_on(root, ["size"])
        self.assertEqual(code, 1)
        self.assertIn(f"FAIL size big.bin:0 - :: {check_site.SIZE_LIMIT_BYTES + 1} bytes is over "
                      f"{check_site.SIZE_LIMIT_BYTES}; add it to tools/size_allowlist.txt only with Gilly's yes", out)
        self.assertFalse([ln for ln in out if "allowed.bin" in ln], out)

    def test_known_failure_prints_known_and_passes(self):
        root = self.copy("bad-case-link")
        (root / "tools").mkdir()
        (root / "tools" / "known_failures.txt").write_text("# fixture\nlink index.html /JHV/\n")
        code, out = self.run_on(root, ["link"])
        self.assertEqual(code, 0, out)
        self.assertTrue(out[0].startswith("KNOWN link index.html:3 /JHV/"), out)

    def test_stamp_skips_a_script_without_check(self):
        root = self.copy("ok-site")
        (root / "bump-assets.py").write_text(
            "import pathlib\npathlib.Path('WROTE').write_text('x')\n")
        code, out = self.run_on(root, ["stamp"])
        self.assertEqual(code, 0)
        self.assertIn("SKIP stamp bump-assets.py:0 - :: script has no --check yet", out)
        self.assertFalse((root / "WROTE").exists())


class HelperTest(unittest.TestCase):
    def test_resolve_order_and_case(self):
        files = {"index.html", "shop.html", "shop/index.html", "jhv/index.html", "a.pdf"}
        self.assertEqual(check_site.resolve("/", files), "index.html")
        self.assertEqual(check_site.resolve("/jhv/", files), "jhv/index.html")
        self.assertEqual(check_site.resolve("/jhv", files), "jhv/index.html")
        self.assertEqual(check_site.resolve("/shop", files), "shop.html")
        self.assertEqual(check_site.resolve("/a.pdf", files), "a.pdf")
        self.assertIsNone(check_site.resolve("/JHV/", files))

    def test_parse_redirect_target(self):
        html = (FIX / "ok-site" / "jhv" / "index.html").read_text()
        self.assertEqual(check_site.parse_redirect_target(html), "https://gilly.space/Research.html")
        self.assertEqual(check_site.parse_redirect_target('<script>location.replace("/x/");</script>'), "/x/")
        self.assertIsNone(check_site.parse_redirect_target("<p>no redirect</p>"))

    def test_feed_enclosures(self):
        xml = (FIX / "ok-site" / "heliograph" / "appcast.xml").read_text()
        self.assertEqual(check_site.feed_enclosures(xml), [("https://gilly.space/heliograph/App-1.0.dmg", 4)])

    def test_sun_product_ids(self):
        html = 'const PRODUCTS = [\n    ["rainbow","Rainbow"],\n    ["171","AIA 171"], ["94","AIA 94"],\n  ];\n'
        self.assertEqual(check_site.sun_product_ids(html), ["rainbow", "171", "94"])


class WorkflowTest(unittest.TestCase):
    def test_check_yml_runs_the_floor(self):
        wf = (TOOLS.parent / ".github" / "workflows" / "check.yml").read_text()
        for needle in ("workflow_call:", "contents: read", "runs-on: ubuntu-latest",
                       "python3 -m unittest discover -s tools/tests -p 'test_*.py'",
                       "python3 tools/check_site.py",
                       'node --check "$RUNNER_TEMP/worker.mjs"'):
            self.assertIn(needle, wf)


# ---- rule `contract` (WS-4) -----------------------------------------------------
import pathlib, re, shutil, subprocess, sys, tempfile, unittest  # noqa: E401


class ContractTests(unittest.TestCase):
    """contracts/*.md against sun.html, the Sun fixtures, the Heliogram feed and the Studio page."""

    REPO = pathlib.Path(__file__).resolve().parents[2]
    FIXTURE = REPO / "tools" / "tests" / "fixtures" / "contract-renamed-field"

    def run_contract(self, root):
        r = subprocess.run(
            [sys.executable, str(self.REPO / "tools" / "check_site.py"),
             "--root", str(root), "--only", "contract"],
            capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def copy_fixture(self, tmp):
        site = pathlib.Path(tmp) / "site"
        shutil.copytree(self.FIXTURE, site)
        return site

    def test_renamed_field_fails(self):
        code, out = self.run_contract(self.FIXTURE)
        self.assertIn("FAIL contract fixtures/sun/manifest/171.json", out)
        self.assertIn("lacks field img1k", out)
        self.assertEqual(code, 1, out)

    def test_restored_field_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self.copy_fixture(tmp)
            p = site / "fixtures" / "sun" / "manifest" / "171.json"
            p.write_text(p.read_text().replace('"img_1k"', '"img1k"'))
            code, out = self.run_contract(site)
            self.assertNotIn("FAIL", out)
            self.assertEqual(code, 0, out)

    def test_ids_block_out_of_step_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self.copy_fixture(tmp)
            p = site / "contracts" / "sun-bucket.md"
            p.write_text(p.read_text().replace("dem\n", ""))
            code, out = self.run_contract(site)
            self.assertIn("differs from sun.html PRODUCTS", out)
            self.assertEqual(code, 1, out)

    def test_ungated_fixture_bucket_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self.copy_fixture(tmp)
            p = site / "sun.html"
            text, n = re.subn(r"(?m)^  const BUCKET = .*$", '  const BUCKET = "/fixtures/sun/";',
                              p.read_text())
            self.assertEqual(n, 1)
            p.write_text(text)
            code, out = self.run_contract(site)
            self.assertIn("fixture path not gated on localhost", out)
            self.assertEqual(code, 1, out)

    # end of ContractTests


if __name__ == "__main__":
    unittest.main()
