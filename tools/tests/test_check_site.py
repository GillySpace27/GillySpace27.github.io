"""Tests for tools/check_site.py (run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

Each bad fixture under tools/tests/fixtures/ must fail with its own message,
and ok-site must pass every rule, so no rule can pass by never firing.
"""
from __future__ import annotations

import pathlib
import re
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


class NoJekyllTest(unittest.TestCase):
    """A page that links a .md file needs .nojekyll: Pages' default Jekyll pass would
    publish that file as .html and the .md URL would 404."""

    run_on = FixtureTest.run_on
    copy = FixtureTest.copy

    def site_linking_md(self, with_marker: bool):
        root = self.copy("ok-site")
        (root / "spec.md").write_text("# spec\n")
        (root / "index.html").write_text('<!doctype html>\n<a href="/spec.md">spec</a>\n', encoding="utf-8")
        if with_marker:
            (root / ".nojekyll").write_text("")
        return root

    def test_md_link_without_nojekyll_fails(self):
        code, out = self.run_on(self.site_linking_md(False), ["nojekyll"])
        self.assertEqual(code, 1, "\n".join(out))
        self.assertIn("FAIL nojekyll index.html:2 /spec.md :: links a .md file but .nojekyll is not tracked;"
                      " Pages' default Jekyll pass would serve /spec.html instead", out)

    def test_md_link_with_nojekyll_passes(self):
        code, out = self.run_on(self.site_linking_md(True), ["nojekyll"])
        self.assertEqual((code, [ln for ln in out if not ln.startswith("SKIP ")]), (0, []))

    def test_site_without_md_links_needs_no_marker(self):
        code, out = self.run_on("ok-site", ["nojekyll"])
        self.assertEqual((code, [ln for ln in out if not ln.startswith("SKIP ")]), (0, []))

    def test_real_tree_has_the_marker_and_every_spec_md_link_resolves(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        self.assertTrue((root / ".nojekyll").is_file(), ".nojekyll must be tracked at the repo root")
        self.assertEqual((root / ".nojekyll").stat().st_size, 0)
        code, out = self.run_on(root, ["nojekyll", "link"])
        self.assertEqual(code, 0, "\n".join(out))
        index = (root / "heliosoftware" / "spec" / "index.html").read_text(encoding="utf-8")
        mds = re.findall(r'href="((?!https?:)[^"#?]+\.md)"', index)
        self.assertIn("agent-preamble.md", mds)
        for rel in mds:
            self.assertTrue((root / "heliosoftware" / "spec" / rel).is_file(), rel)


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

    def test_frozen_feed_missing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = pathlib.Path(tmp)
            (site / "contracts").mkdir()
            shutil.copy(self.REPO / "contracts" / "heliogram-publish.md", site / "contracts")
            (site / "heliograph").mkdir()
            shutil.copy(self.REPO / "heliograph" / "version.json", site / "heliograph")
            code, out = self.run_contract(site)
            self.assertIn("FAIL contract heliograph/appcast.xml", out)
            self.assertIn("frozen path not tracked", out)
            self.assertEqual(code, 1, out)

    def test_version_json_lost_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = pathlib.Path(tmp)
            (site / "contracts").mkdir()
            shutil.copy(self.REPO / "contracts" / "heliogram-publish.md", site / "contracts")
            shutil.copytree(self.REPO / "heliograph", site / "heliograph")
            (site / "heliograph" / "version.json").write_text('{"version": "0.7", "build": 7}\n')
            code, out = self.run_contract(site)
            self.assertIn("version.json lost keys page", out)
            self.assertEqual(code, 1, out)
    def heliogram_site(self, tmp):
        site = pathlib.Path(tmp)
        (site / "contracts").mkdir()
        shutil.copy(self.REPO / "contracts" / "heliogram-publish.md", site / "contracts")
        shutil.copytree(self.REPO / "heliograph", site / "heliograph")
        (site / "heliogram").mkdir()
        (site / "heliogram" / "index.html").write_text("interim page\n")
        return site

    def test_interim_heliogram_page_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_contract(self.heliogram_site(tmp))
            self.assertNotIn("publish.sh writes this", out)
            self.assertEqual(code, 0, out)

    def test_published_heliogram_missing_dmg_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self.heliogram_site(tmp)
            shutil.copy(self.REPO / "heliograph" / "version.json", site / "heliogram")
            code, out = self.run_contract(site)
            self.assertIn("FAIL contract heliogram/Heliogram.dmg", out)
            self.assertEqual(code, 1, out)

    def test_studio_template_renamed_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = pathlib.Path(tmp)
            (site / "contracts").mkdir()
            doc = (self.REPO / "contracts" / "studio-release-assets.md").read_text()
            self.assertIn("HFStudio-{v}-linux.tar.gz\n", doc)
            (site / "contracts" / "studio-release-assets.md").write_text(
                doc.replace("HFStudio-{v}-linux.tar.gz\n", "HFStudio-{v}-linux.tgz\n"))
            (site / "heliofits-studio").mkdir()
            shutil.copy(self.REPO / "heliofits-studio" / "index.html", site / "heliofits-studio")
            code, out = self.run_contract(site)
            self.assertIn("PLATFORMS.linux matches 0 assets", out)
            self.assertIn("no fallback link to v", out)
            self.assertEqual(code, 1, out)
    def _studio_site(self, tmp, page_edit):
        site = pathlib.Path(tmp)
        (site / "contracts").mkdir()
        shutil.copy(self.REPO / "contracts" / "studio-release-assets.md", site / "contracts")
        (site / "heliofits-studio").mkdir()
        page = (self.REPO / "heliofits-studio" / "index.html").read_text()
        (site / "heliofits-studio" / "index.html").write_text(page_edit(page))
        return site

    def test_studio_optional_intel_from_older_release_passes(self):
        # 0.8.5 shipped without an Intel dmg: its fallback may stay on an older release.
        rx = re.compile(r"v[\d.]+/HFStudio-[\d.]+-intel\.dmg")
        with tempfile.TemporaryDirectory() as tmp:
            site = self._studio_site(tmp, lambda p: rx.sub("v0.0.1/HFStudio-0.0.1-intel.dmg", p))
            code, out = self.run_contract(site)
            self.assertNotIn("FAIL contract heliofits-studio", out)
            self.assertEqual(code, 0, out)

    def test_studio_optional_intel_link_removed_fails(self):
        rx = re.compile(r"https://github.com/GillySpace27/HelioFITS-Studio/releases/download/v[\d.]+/HFStudio-[\d.]+-intel\.dmg")
        with tempfile.TemporaryDirectory() as tmp:
            site = self._studio_site(tmp, lambda p: rx.sub("#", p))
            code, out = self.run_contract(site)
            self.assertIn("-intel.dmg", out)
            self.assertIn("FAIL contract heliofits-studio", out)
            self.assertEqual(code, 1, out)

    def test_real_tree_contracts_pass(self):
        code, out = self.run_contract(self.REPO)
        self.assertNotIn("FAIL contract", out)
        self.assertNotIn("SKIP contract", out)
        self.assertEqual(code, 0, out)
    def _restored_fixture(self, tmp):
        site = self.copy_fixture(tmp)
        p = site / "fixtures" / "sun" / "manifest" / "171.json"
        p.write_text(p.read_text().replace('"img_1k"', '"img1k"'))
        (site / "assets").mkdir(exist_ok=True)
        return site

    def test_sun_js_reads_unknown_field_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self._restored_fixture(tmp)
            (site / "assets" / "sun.js").write_text("const x = m.img_1k;\n")
            code, out = self.run_contract(site)
            self.assertIn("FAIL contract assets/sun.js:1 m.img_1k", out)
            self.assertEqual(code, 1, out)

    def test_sun_js_ungated_fixture_bucket_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self._restored_fixture(tmp)
            (site / "assets" / "sun.js").write_text('  const BUCKET = "/fixtures/sun/";\n')
            code, out = self.run_contract(site)
            self.assertIn("FAIL contract assets/sun.js:1 BUCKET", out)
            self.assertIn("fixture path not gated on localhost", out)
            self.assertEqual(code, 1, out)

    def test_real_sun_js_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = self._restored_fixture(tmp)
            shutil.copy(self.REPO / "assets" / "sun.js", site / "assets" / "sun.js")
            # the real contract lists the optional fields (through, times) that sun.js reads
            shutil.copy(self.REPO / "contracts" / "sun-bucket.md", site / "contracts" / "sun-bucket.md")
            code, out = self.run_contract(site)
            self.assertNotIn("FAIL", out)
            self.assertEqual(code, 0, out)

    # end of ContractTests


if __name__ == "__main__":
    unittest.main()
