"""WS-16, the rest: the stage shares too, and cards and stage offer the movie file and the
two handoffs (Heliogram for the desktop, the store for a print).

Run: python3 -m unittest discover -s tools/tests -p 'test_share_handoffs.py' -v
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SUN = (ROOT / "sun.html").read_text(encoding="utf-8")


def stage() -> str:
    i = SUN.index('<section id="stage"')
    return SUN[i:SUN.index("</section>", i)]


def card_template() -> str:
    i = SUN.index("function renderCard(")
    return SUN[i:SUN.index("function renderFailed(", i)]


class Handoffs(unittest.TestCase):
    def test_stage_has_share_still_movie_and_both_handoffs(self):
        s = stage()
        self.assertIn('id="stage-share-btn"', s)
        self.assertIn('id="stage-still"', s)
        self.assertRegex(s, r'<a id="stage-movie"[^>]*\bdownload\b')
        self.assertIn('href="/heliogram/"', s)
        self.assertIn('href="https://myheliograph.com/?ref=gilly.space"', s)

    def test_stage_links_follow_the_channel_on_show(self):
        self.assertIn('addEventListener("sun:stage", syncStageShare)', SUN)
        self.assertIn('addEventListener("sun:card", syncStageShare)', SUN)
        self.assertRegex(SUN, r'getElementById\("stage-share-btn"\)\.addEventListener\("click"')

    def test_each_card_offers_the_movie_file(self):
        self.assertRegex(card_template(), r'<a href="\$\{u\(m\.video, v\)\}"[^>]*\bdownload\b')

    def test_never_heliograph_dot_com(self):
        self.assertIsNone(re.search(r"(?<!my)heliograph\.com", SUN))


if __name__ == "__main__":
    unittest.main()
