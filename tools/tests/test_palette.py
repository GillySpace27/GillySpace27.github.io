"""WS-19: command palette on phones, fuzzy ranking, channels, and a 404 that suggests pages.

Run: python3 -m unittest discover -s tools/tests -p 'test_palette.py' -v
The ranking tests run assets/site.js's fuzzyScore and ITEMS in Node (skipped without node).
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE_JS = (ROOT / "assets" / "site.js").read_text(encoding="utf-8")
HEADER = (ROOT / "partials" / "header.html").read_text(encoding="utf-8")
PAGE_404 = (ROOT / "404.html").read_text(encoding="utf-8")
NODE = shutil.which("node")
EM = chr(0x2014)  # spelled as a code point so this file holds no em dash


def region(text: str, begin: str, end: str) -> str:
    i = text.index(begin)
    return text[i:text.index(end, i)]


def rank(query: str, path_mode: bool = False) -> list[str]:
    """URLs in ranked order, as the palette (or the 404 page) would show them."""
    fn = region(SITE_JS, "/* fuzzy-score begin */", "/* fuzzy-score end */")
    items = region(SITE_JS, "var ITEMS = [", "];") + "];"
    js = fn + "\n" + items + "\n" + (
        "var q = %s, pathMode = %s;\n"
        "var hay = function (it) { return pathMode ? it.u + ' ' + it.t + ' ' + it.k : it.t + ' ' + it.k; };\n"
        "var out = ITEMS.filter(function (it) { return !pathMode || it.u.charAt(0) === '/'; })\n"
        "  .map(function (it) { return [fuzzyScore(q, hay(it)), it.u]; })\n"
        "  .filter(function (x) { return x[0] > 0; })\n"
        "  .sort(function (a, b) { return b[0] - a[0]; });\n"
        "console.log(JSON.stringify(out.map(function (x) { return x[1]; })));\n"
    ) % (json.dumps(query), "true" if path_mode else "false")
    r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


class Palette(unittest.TestCase):
    def test_header_has_a_search_button_for_phones(self):
        self.assertRegex(HEADER, r'<button id="cmdkOpen"[^>]*aria-label="Search pages"')

    def test_items_have_no_em_dash_and_list_every_sun_channel(self):
        items = region(SITE_JS, "var ITEMS = [", "];")
        self.assertNotIn(EM, items)
        for cid in ("rainbow", "171", "193", "211", "304", "335", "94", "131", "1600", "1700", "composite_uv", "dem"):
            self.assertIn(f"u: '/sun.html#{cid}'", items, cid)

    def test_items_and_scorer_are_shared_with_the_404_page(self):
        self.assertIn("window.GillySite = { fuzzyScore: fuzzyScore, items: ITEMS };", SITE_JS)

    @unittest.skipUnless(NODE, "SKIP: node not installed")
    def test_ranking(self):
        self.assertEqual(rank("fits stu")[0], "/heliofits-studio/")
        self.assertEqual(rank("304")[0], "/sun.html#304")
        self.assertTrue(rank("enso")[0].startswith("/enso/"))  # accents ignored: "enso" finds Ensō
        self.assertEqual(rank("zzqx"), [])

    @unittest.skipUnless(NODE, "SKIP: node not installed")
    def test_404_path_suggestions(self):
        self.assertEqual(rank("heliofit", path_mode=True)[0], "/heliofits/")
        self.assertIn("/rhef/", rank("rhef", path_mode=True)[:3])


class NotFound(unittest.TestCase):
    def test_lowercase_redirect_still_runs_first(self):
        lower = PAGE_404.index("location.pathname.toLowerCase()")
        self.assertLess(lower, PAGE_404.index('id="suggestions"'))

    def test_suggestions_read_the_shared_scorer_after_site_js(self):
        site = PAGE_404.index('<script src="/assets/site.js')
        self.assertLess(site, PAGE_404.index("window.GillySite"))

    def test_no_em_dash_in_404(self):
        self.assertNotIn(EM, PAGE_404)


if __name__ == "__main__":
    unittest.main()
