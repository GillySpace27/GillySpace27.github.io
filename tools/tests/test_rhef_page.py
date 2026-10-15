"""RH-10: gilly.space/rhef as the RHEF home (tabs, unroll movie, implementations table, Cite it).

Static checks on rhef/index.html: every tab panel is a working compare figure whose image is
tracked, the movie never plays on its own, the BibTeX names the published paper, and the page
publishes none of the withheld oRHEF 2.0 expected values (suite Q18).
"""
import html.parser
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGE = ROOT / "rhef" / "index.html"


class _Tags(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags():
    p = _Tags()
    p.feed(PAGE.read_text(encoding="utf-8"))
    return p.tags


class RhefPageTest(unittest.TestCase):
    def setUp(self):
        self.text = PAGE.read_text(encoding="utf-8")
        self.tags = tags()

    def test_tab_panels_are_compare_figures_with_tracked_images(self):
        panels = [a for t, a in self.tags if a.get("role") == "tabpanel"]
        self.assertGreaterEqual(len(panels), 1)
        tabs = [a for t, a in self.tags if a.get("role") == "tab"]
        self.assertEqual(len(tabs), len(panels), "one tab per panel")
        for a in tabs:
            self.assertIn(a.get("aria-controls"), {p.get("id") for p in panels})
        for m in re.finditer(r'<section[^>]*role="tabpanel"[^>]*>(.*?)</section>', self.text, re.S):
            body = m.group(1)
            self.assertIn("data-compare=", body)
            for src in re.findall(r'<img[^>]*src="(/assets/sw/[^"]+)"', body):
                self.assertTrue((ROOT / src.lstrip("/")).is_file(), src)

    def test_the_first_figure_is_still_the_no_js_fallback(self):
        self.assertIn('src="/assets/sw/rhef-compare.jpg"', self.text)
        self.assertIn('class="sw-mark sw-mark--rhef', self.text)

    def test_movie_is_user_started_and_labelled_a_teaching_visual(self):
        videos = [a for t, a in self.tags if t == "video"]
        self.assertEqual(len(videos), 1)
        v = videos[0]
        self.assertNotIn("autoplay", v)
        self.assertIn("controls", v)
        self.assertEqual(v.get("preload"), "none")
        self.assertTrue((ROOT / v["poster"].lstrip("/")).is_file())
        srcs = [a["src"] for t, a in self.tags if t == "source"]
        self.assertTrue(srcs and all((ROOT / s.lstrip("/")).is_file() for s in srcs))
        self.assertIn("synthetic", self.text)
        self.assertIn("not a figure from the paper", self.text)

    def test_bibtex_names_the_published_paper(self):
        m = re.search(r'<pre[^>]*id="rhef-bibtex"[^>]*><code>(.*?)</code></pre>', self.text, re.S)
        self.assertIsNotNone(m)
        bib = m.group(1)
        for want in ("10.1007/s11207-025-02578-x", "Solar Physics", "2025", "{300}", "{174}",
                     "2511.02798", "Cranmer"):
            self.assertIn(want, bib)
        self.assertIn('data-copy="rhef-bibtex"', self.text)

    def test_implementations_table_uses_registered_deviation_ids(self):
        conv = (ROOT / "heliosoftware/spec/rhef/conventions.md").read_text(encoding="utf-8")
        known = set(re.findall(r"^\| `([A-Z0-9-]+)` \|", conv, re.M))
        m = re.search(r'<table[^>]*id="rhef-implementations"[^>]*>(.*?)</table>', self.text, re.S)
        self.assertIsNotNone(m)
        used = set(re.findall(r"<code>([A-Z][A-Z0-9-]+)</code>", m.group(1)))
        self.assertTrue(used)
        self.assertEqual(used - known, set(), "deviation ids not in conventions.md")

    def test_no_withheld_orhef_expected_values(self):
        self.assertNotIn("expected_oRHEF", self.text)
        self.assertNotIn("/releases/latest", self.text)


if __name__ == "__main__":
    unittest.main()
