"""Tests for tools/release_pr.py and feed_studio_release.py --confirm-from-page (WS-22).

Nothing here reaches the network or pushes; the git work happens in a temporary repository.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402
import feed_studio_release as fsr  # noqa: E402
import release_pr  # noqa: E402

REC = {"version": "9.9.9", "date": "2026-11-02", "channel": "mac-app-store",
       "url": "https://apps.apple.com/app/id0", "notes": "Synthetic, never a real release."}


class FindRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, records):
        (self.dir / "heliofits.json").write_text(json.dumps({"product": "heliofits", "records": records}))

    def test_finds_by_version_and_build(self):
        self.write([dict(REC, build=1), dict(REC, build=2)])
        self.assertEqual(release_pr.find_record(self.dir, "heliofits", "9.9.9", 1)["build"], 1)
        self.assertEqual(release_pr.find_record(self.dir, "heliofits", "9.9.9")["build"], 2)

    def test_missing_record_refuses(self):
        self.write([REC])
        with self.assertRaises(release_pr.PRError):
            release_pr.find_record(self.dir, "heliofits", "1.0.0")

    def test_invalid_record_refuses(self):
        self.write([dict(REC, notes="")])
        with self.assertRaises(release_pr.PRError):
            release_pr.find_record(self.dir, "heliofits", "9.9.9")

    def test_branch_name(self):
        self.assertEqual(release_pr.branch_name("heliofits", dict(REC, build=13)), "release/heliofits-9.9.9-build.13")
        self.assertEqual(release_pr.branch_name("heliofits-studio", REC), "release/heliofits-studio-9.9.9")


class RefreshVersionTextTests(unittest.TestCase):
    def test_raises_only_older_text_of_that_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            page = root / "p.html"
            page.write_text('<span data-release="heliofits" data-release-field="version">1.5.0</span>\n'
                            '<span data-release="heliogram" data-release-field="version">0.8</span>\n')
            newer = root / "q.html"
            newer.write_text('<span data-release="heliofits" data-release-field="version">10.0.0</span>\n')
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            changed = release_pr.refresh_version_text(root, "heliofits", "9.9.9")
            self.assertEqual(changed, ["p.html"])
            text = page.read_text()
            self.assertIn('data-release-field="version">9.9.9<', text)
            self.assertIn('data-release-field="version">0.8<', text)
            self.assertIn(">10.0.0<", newer.read_text())


class ConfirmFromPageTests(unittest.TestCase):
    def test_real_page_confirms_guide_and_flagged_macs_only(self):
        text = (REPO / check_site.STUDIO_PAGE).read_text(encoding="utf-8")
        got = fsr.confirmed_from_page(text)
        self.assertIn("guide", got)
        self.assertTrue(got <= {"guide", "macos-arm64", "macos-x64"})

    def test_flags_are_read(self):
        page = "const PLATFORMS = {\n  mac: { confirmed: false },\n  intel: { confirmed: true },\n};\n"
        self.assertEqual(fsr.confirmed_from_page(page), {"guide", "macos-x64"})

    def test_no_platforms_refuses(self):
        with self.assertRaises(fsr.FeedError):
            fsr.confirmed_from_page("<html></html>")


if __name__ == "__main__":
    unittest.main()
