"""Tests for heliosoftware/feed/append_record.py and build_feed.py (suite SU-11).

Run: python3 -m unittest discover -s tools/tests -p 'test_release_feed.py' -v
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FEED = ROOT / "heliosoftware" / "feed"
sys.path.insert(0, str(FEED))
import append_record  # noqa: E402

SHA = "a" * 64
D = chr(0x2014)


def asset(name="Heliogram-0.8.dmg", sha=SHA):
    return (f"name={name},url=https://gilly.space/heliogram/{name},sha256={sha},bytes=12226044,"
            "platform=macos-universal,confirmed=true")


class Writer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.notes = self.dir / "notes.txt"
        self.notes.write_text("Short text, no dash.\n", encoding="utf-8")

    def run_writer(self, *extra, product="heliogram", version="0.8", channel="direct"):
        argv = [sys.executable, str(FEED / "append_record.py"), "--feed-dir", str(self.dir), "--product", product,
                "--version", version, "--date", "2026-10-02", "--channel", channel,
                "--url", "https://gilly.space/heliogram/", "--notes-file", str(self.notes), *extra]
        return subprocess.run(argv, capture_output=True, text=True)

    def feed(self, product="heliogram"):
        return json.loads((self.dir / f"{product}.json").read_text(encoding="utf-8"))

    def test_creates_the_file_and_the_record(self):
        r = self.run_writer("--build", "8", "--tag", "v0.8-build.8", "--asset", asset())
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.feed()
        self.assertEqual((data["product"], data["name"], data["page"]),
                         ("heliogram", "Heliogram", "https://gilly.space/heliogram/"))
        rec = data["records"][0]
        self.assertEqual(list(rec), ["version", "build", "date", "channel", "tag", "url", "notes", "assets"])
        self.assertEqual(rec["assets"][0]["sha256"], SHA)
        self.assertIs(rec["assets"][0]["confirmed"], True)
        self.assertEqual(rec["assets"][0]["bytes"], 12226044)

    def test_a_second_record_leaves_the_first_untouched(self):
        self.assertEqual(self.run_writer("--build", "8", "--asset", asset()).returncode, 0)
        first = self.feed()["records"][0]
        self.assertEqual(self.run_writer("--build", "9", "--asset", asset("Heliogram-0.9.dmg"), version="0.9").returncode, 0)
        recs = self.feed()["records"]
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0], first)

    def test_binary_asset_without_sha256_is_refused_and_nothing_is_written(self):
        bad = "name=x.dmg,url=https://gilly.space/x.dmg,bytes=3,platform=macos,confirmed=true"
        r = self.run_writer("--asset", bad)
        self.assertEqual(r.returncode, 1)
        self.assertIn("sha256 is missing or not 64 lowercase hex", r.stderr)
        self.assertFalse((self.dir / "heliogram.json").exists())

    def test_uppercase_sha256_is_refused(self):
        r = self.run_writer("--asset", asset(sha="A" * 64))
        self.assertEqual(r.returncode, 1)

    def test_channel_that_ships_a_file_needs_an_asset(self):
        r = self.run_writer()
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs at least one asset", r.stderr)

    def test_notes_with_an_em_dash_are_refused(self):
        self.notes.write_text(f"two words {D} apart\n", encoding="utf-8")
        r = self.run_writer("--asset", asset())
        self.assertEqual(r.returncode, 1)
        self.assertIn("U+2014", r.stderr)
        self.assertFalse((self.dir / "heliogram.json").exists())

    def test_duplicate_version_and_build_exit_3_and_change_nothing(self):
        self.assertEqual(self.run_writer("--build", "8", "--asset", asset()).returncode, 0)
        before = (self.dir / "heliogram.json").read_bytes()
        r = self.run_writer("--build", "8", "--asset", asset())
        self.assertEqual(r.returncode, 3)
        self.assertEqual((self.dir / "heliogram.json").read_bytes(), before)

    def test_releases_latest_is_refused(self):
        r = self.run_writer("--asset", asset().replace("https://gilly.space/heliogram/", "https://github.com/o/r/releases/latest/"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("/releases/latest", r.stderr)

    def test_app_store_channel_needs_no_asset(self):
        self.notes.write_text("Opening the app now opens the viewer.\n", encoding="utf-8")
        argv = [sys.executable, str(FEED / "append_record.py"), "--feed-dir", str(self.dir), "--product", "heliofits",
                "--version", "1.4.0", "--build", "10", "--date", "2026-10-02", "--channel", "mac-app-store",
                "--url", "https://apps.apple.com/app/id6790952544", "--notes-file", str(self.notes)]
        r = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.feed("heliofits")["records"][0]["assets"], [])

    def test_unknown_product_is_a_usage_error(self):
        self.assertEqual(self.run_writer("--asset", asset(), product="nope").returncode, 2)

    def test_optional_name_is_kept(self):
        r = self.run_writer("--name", "Heliograph", "--asset", asset("Heliograph-0.7.dmg"), version="0.7")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.feed()["records"][0]["name"], "Heliograph")


if __name__ == "__main__":
    unittest.main()
