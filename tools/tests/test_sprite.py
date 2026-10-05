"""WS-11: assets/icons.svg and the builder that makes it
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
IDS = {"arxiv", "orcid", "ads", "github", "linkedin-square", "soundcloud", "envelope-o"}


class SpriteTest(unittest.TestCase):
    def sprite(self) -> str:
        return (REPO / "assets" / "icons.svg").read_text(encoding="utf-8")

    def test_every_icon_has_a_symbol_with_an_outline(self):
        symbols = re.findall(
            r'<symbol id="([^"]+)" viewBox="([^"]+)"><path transform="scale\(1 -1\)" d="([^"]+)"/></symbol>', self.sprite())
        self.assertEqual({s[0] for s in symbols}, IDS)
        for name, box, d in symbols:
            self.assertEqual(len(box.split()), 4, name)
            self.assertGreater(len(d), 100, name)

    def test_the_sprite_is_what_the_builder_makes(self):
        r = subprocess.run([sys.executable, str(TOOLS / "build_icons.py"), "--check"], capture_output=True, text=True, cwd=REPO)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_the_sprite_names_its_sources_and_has_no_em_dash(self):
        text = self.sprite()
        self.assertIn("Font Awesome 4.6.3", text)
        self.assertIn("Academicons", text)
        self.assertIn("SIL OFL 1.1", text)
        self.assertNotIn(chr(0x2014), text)


if __name__ == "__main__":
    unittest.main()
