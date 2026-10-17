"""WS-13: the wall and dome kit (sun-wall.html options, /wall/ builder).

The pure helpers run under Node (skipped where node is absent; CI has node 22).
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
try:
    import cv2 as CV2
except ImportError:  # CI has no OpenCV: the decode test is skipped there
    CV2 = None
WALL = (REPO / "sun-wall.html").read_text(encoding="utf-8")
BUILDER = (REPO / "wall" / "index.html").read_text(encoding="utf-8")


class WallKitTest(unittest.TestCase):
    @unittest.skipUnless(NODE, "node is not installed")
    def test_helpers_and_builder_links(self):
        r = subprocess.run([NODE, str(REPO / "tools" / "tests" / "js" / "wall_kit_check.mjs"), str(REPO)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("wall kit: ok", r.stdout)

    def test_wall_page_is_a_real_document(self):
        self.assertRegex(WALL, r'<html lang="en">')
        self.assertEqual(WALL.count("<body>"), 1)
        self.assertTrue(WALL.rstrip().endswith("</html>"))

    def test_existing_wall_contract_is_kept(self):
        # the Mac app injects these and the suite contract check reads these markers
        for needle in ("window.WALL_LOOPS", "window.WALL_SHUFFLE", "window.WALL_ATTRIBUTION",
                       "window.WALL_PRODUCT", "// loadSunIndex begin", "// loadSunIndex end",
                       'fetch("manifest.json"', 'id="stage"', 'id="cap"', 'id="attr"'):
            self.assertIn(needle, WALL, needle)

    def test_new_options_and_wake_lock(self):
        for needle in ("wallOptions(location.search)", "navigator.wakeLock.request", "visibilitychange",
                       "body.dome", "requestFullscreen"):
            self.assertIn(needle, WALL, needle)

    def test_builder_is_registered_but_not_yet_linked(self):
        pages = {p["path"]: p for p in json.loads((REPO / "site.json").read_text(encoding="utf-8"))["pages"]}
        entry = pages["wall/index.html"]
        self.assertEqual(entry["url"], "/wall/")
        # map question q8 (is the wall a supported public page?) is Gilly's: unlinked until he answers
        self.assertFalse(entry["sitemap"])
        self.assertFalse(entry["palette"])
        for page in ("sun.html", "play/index.html", "index.html"):
            self.assertNotIn('href="/wall/"', (REPO / page).read_text(encoding="utf-8"), page)

    def test_sun_page_has_a_print_this_moment_link_that_follows_the_stage(self):
        page = (REPO / "sun.html").read_text(encoding="utf-8")
        self.assertEqual(page.count('id="stage-print"'), 1)
        self.assertIn("SunData.storeLink(st.id", page)
        # the older, plain store link is kept
        self.assertIn('href="https://myheliograph.com/?ref=gilly.space"', page)
        self.assertIn("store=1", WALL)

    def test_qr_level_loads_the_vendored_encoder_and_keeps_its_licence(self):
        vend = REPO / "assets" / "vendor" / "qrcode-generator"
        for name in ("qrcode.js", "LICENSE", "README.md"):
            self.assertTrue((vend / name).is_file(), name)
        self.assertIn("MIT", (vend / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn("/assets/vendor/qrcode-generator/qrcode.js", WALL)
        self.assertEqual(len((vend / "qrcode.js").read_bytes()), 56694, "byte for byte the 1.4.4 file")

    @unittest.skipUnless(NODE and CV2, "node or OpenCV is not installed; CI skips the decode")
    def test_the_code_decodes_to_the_store_link(self):
        import numpy as np
        want = "https://myheliograph.com/?utm_source=wall&d=2026-09-30&t=14:20&wl=171"
        r = subprocess.run([NODE, str(REPO / "tools" / "tests" / "js" / "wall_kit_check.mjs"), str(REPO), "--matrix", want],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = json.loads(r.stdout.strip().splitlines()[-1])
        n = len(rows)
        img = np.full(((n + 8) * 8, (n + 8) * 8), 255, dtype=np.uint8)
        for y, line in enumerate(rows):
            for x, ch in enumerate(line):
                if ch == "1":
                    img[(y + 4) * 8:(y + 5) * 8, (x + 4) * 8:(x + 5) * 8] = 0
        got, _pts, _ = CV2.QRCodeDetector().detectAndDecode(img)
        self.assertEqual(got, want)
        # able to fail: a different text must not decode to this one
        r2 = subprocess.run([NODE, str(REPO / "tools" / "tests" / "js" / "wall_kit_check.mjs"), str(REPO), "--matrix", want + "x"],
                            capture_output=True, text=True)
        self.assertNotEqual(r2.stdout.strip().splitlines()[-1], r.stdout.strip().splitlines()[-1])

    def test_builder_form_fields(self):
        for name in ("shape", "clock", "caption", "attrib", "loops", "shuffle"):
            self.assertRegex(BUILDER, rf'name="{name}"')
        self.assertIn('<main id="main"', BUILDER)
        self.assertIsNone(re.search(chr(0x2014), BUILDER + WALL))


if __name__ == "__main__":
    unittest.main()
