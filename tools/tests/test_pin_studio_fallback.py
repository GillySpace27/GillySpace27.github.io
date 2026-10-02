"""Tests for tools/pin_studio_fallback.py (run: python3 -m unittest discover -s tools/tests -p 'test_pin*.py').

Every test works on a copy of the real page and contract in a temporary directory;
nothing here reaches the network.
"""
from __future__ import annotations

import contextlib
import io
import pathlib
import shutil
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402
import pin_studio_fallback as pin  # noqa: E402

REPO = TOOLS.parent
NEW = "9.9.9"   # synthetic; never a real release


def assets_for(version):
    doc = REPO / check_site.CONTRACT_STUDIO
    return {t.replace("{v}", version) for t in check_site.contract_block(doc, "assets")}


class PinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        for rel in (check_site.STUDIO_PAGE, check_site.CONTRACT_STUDIO):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / rel, self.root / rel)
        self.page = self.root / check_site.STUDIO_PAGE
        self.before = self.page.read_text(encoding="utf-8")
        self.old = check_site.STUDIO_PIN_RE.search(self.before).group(1)
        self.real_assets = pin.release_assets

    def tearDown(self):
        pin.release_assets = self.real_assets
        self.tmp.cleanup()

    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pin.main([*args, "--root", str(self.root)])
        return code, out.getvalue(), err.getvalue()

    def test_pins_every_occurrence_and_leaves_platforms(self):
        n = len(pin.version_rx(self.old).findall(self.before))
        self.assertGreater(n, 0)
        code, out, err = self.run_main(NEW)
        self.assertEqual(code, 0, err)
        after = self.page.read_text(encoding="utf-8")
        self.assertEqual(len(pin.version_rx(self.old).findall(after)), 0)
        self.assertEqual(len(pin.version_rx(NEW).findall(after)), n)
        self.assertEqual(pin.PLATFORMS_RE.search(after).group(0), pin.PLATFORMS_RE.search(self.before).group(0))
        self.assertIn(f"pinned {self.old} -> {NEW}: {n} occurrences", out)
        self.assertIn("confirmed mac=true (unchanged)", out)

    def test_dry_run_writes_nothing(self):
        code, out, _ = self.run_main(NEW, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would pin", out)
        self.assertEqual(self.page.read_text(encoding="utf-8"), self.before)

    def test_new_version_already_present_refuses(self):
        self.page.write_text(self.before + f"<!-- {NEW} -->\n", encoding="utf-8")
        code, _, err = self.run_main(NEW)
        self.assertEqual(code, 1)
        self.assertIn("already occurs", err)

    def test_boundaries(self):
        rx = pin.version_rx("0.8.2")
        self.assertEqual(rx.findall("v0.8.2/HFStudio-0.8.2.dmg Version 0.8.2 ·"), ["0.8.2"] * 3)
        self.assertEqual(rx.findall("10.8.2 0.8.20 0.8.2.1"), [])

    def test_from_github_bogus_version_names_missing_asset(self):
        pin.release_assets = lambda url=pin.RELEASES_API: ("v0.8.3", assets_for("0.8.3"))
        code, _, err = self.run_main(NEW, "--from-github")
        self.assertEqual(code, 1)
        self.assertIn(f"MISSING HFStudio-{NEW}.dmg", err)
        self.assertIn("newest release is v0.8.3", err)
        self.assertEqual(self.page.read_text(encoding="utf-8"), self.before)

    def test_from_github_missing_linux_asset_refuses(self):
        names = assets_for(NEW) - {f"HFStudio-{NEW}-linux.tar.gz"}
        pin.release_assets = lambda url=pin.RELEASES_API: ("v" + NEW, names)
        code, _, err = self.run_main("--from-github")
        self.assertEqual(code, 1)
        self.assertIn(f"MISSING HFStudio-{NEW}-linux.tar.gz", err)

    def test_from_github_complete_release_pins_newest(self):
        pin.release_assets = lambda url=pin.RELEASES_API: ("v" + NEW, assets_for(NEW))
        code, out, err = self.run_main("--from-github")
        self.assertEqual(code, 0, err)
        self.assertIn(f"-> {NEW}", out)


if __name__ == "__main__":
    unittest.main()
