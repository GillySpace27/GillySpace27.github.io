"""Tests for tools/feed_studio_release.py (run: python3 -m unittest discover -s tools/tests -p 'test_feed*.py').

Every test uses a synthetic release and a temporary feed directory; nothing here reaches the network.
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402
import feed_studio_release as fsr  # noqa: E402

REPO = TOOLS.parent
V = "9.9.9"   # synthetic; never a real release
HEX = "ab" * 32


def release(names=None, body="### New in 9.9.9\n\n#### Area\n- A **new** `thing` works\n- Second", **kw):
    names = names if names is not None else [f"HFStudio-{V}.dmg", f"HFStudio-{V}.zip", "HFStudio-Guide.pdf",
                                               "HFStudio-Guide.md", "fabric_suvi.json.gz"]
    rel = {"tag_name": f"v{V}", "draft": False, "prerelease": True, "published_at": "2030-01-02T03:04:05Z",
           "html_url": f"https://github.com/GillySpace27/HelioFITS-Studio/releases/tag/v{V}", "body": body,
           "assets": [{"name": n, "size": 10, "digest": "sha256:" + HEX,
                       "browser_download_url": f"https://github.com/x/releases/download/v{V}/{n}"} for n in names]}
    rel.update(kw)
    return rel


class FeedStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        for rel in (check_site.CONTRACT_STUDIO, "heliosoftware/feed/heliofits-studio.json"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / rel, self.root / rel)
        self.feed = self.root / "heliosoftware/feed/heliofits-studio.json"
        self.real_fetch = fsr.fetch_release

    def tearDown(self):
        fsr.fetch_release = self.real_fetch
        self.tmp.cleanup()

    def run_main(self, rel, *args):
        fsr.fetch_release = lambda version=None: rel
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = fsr.main([*args, "--root", str(self.root)])
        return code, err.getvalue()

    def newest(self):
        return json.loads(self.feed.read_text(encoding="utf-8"))["records"][-1]

    def test_appends_contract_assets_only_unconfirmed_by_default(self):
        code, _ = self.run_main(release(), V)
        self.assertEqual(code, 0)
        rec = self.newest()
        self.assertEqual((rec["version"], rec["date"], rec["channel"]), (V, "2030-01-02", "github-prerelease"))
        self.assertEqual(rec["notes"], "A new thing works.")
        self.assertEqual([a["name"] for a in rec["assets"]], [f"HFStudio-{V}.dmg", f"HFStudio-{V}.zip", "HFStudio-Guide.pdf"])
        self.assertTrue(all(a["sha256"] == HEX and a["confirmed"] is False for a in rec["assets"]))

    def test_confirm_sets_only_named_platforms(self):
        self.run_main(release(), V, "--confirm", "macos-arm64")
        flags = {a["platform"]: a["confirmed"] for a in self.newest()["assets"]}
        self.assertEqual(flags, {"macos-arm64": True, "any-java25": False, "guide": False})

    def test_duplicate_is_refused(self):
        self.run_main(release(), V)
        before = self.feed.read_text(encoding="utf-8")
        code, err = self.run_main(release(), V)
        self.assertEqual(code, 3)
        self.assertEqual(self.feed.read_text(encoding="utf-8"), before)

    def test_refusals_write_nothing(self):
        before = self.feed.read_text(encoding="utf-8")
        cases = {
            "draft": release(draft=True),
            "no dmg": release(names=[f"HFStudio-{V}.zip"]),
            "no digest": release() | {"assets": [{"name": f"HFStudio-{V}.dmg", "size": 1, "browser_download_url": "https://x/a"}]},
            "no notes": release(body="Nothing new here"),
            "em dash": release(body="### New in 9.9.9\n- A " + fsr.ar.DASH + " B"),
        }
        for label, rel in cases.items():
            with self.subTest(label):
                code, err = self.run_main(rel, V)
                self.assertEqual(code, 1, err)
                self.assertEqual(self.feed.read_text(encoding="utf-8"), before)

    def test_check_reports_missing_then_present(self):
        self.assertEqual(self.run_main(release(), "--check")[0], 1)
        self.run_main(release(), V)
        self.assertEqual(self.run_main(release(), "--check")[0], 0)


if __name__ == "__main__":
    unittest.main()
