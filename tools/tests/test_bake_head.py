"""WS-11: the head target of tools/bake.py, on a throwaway template
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import importlib
import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

DOT = chr(0xB7)
TEMPLATE = f"""\
<!-- authoring notes, ignored -->
<!-- bake:template -->
<meta charset="utf-8">
<!-- a comment that spans
     two lines -->

<title>__PAGE_TITLE__ {DOT} gilly.space</title>
<meta name="description" content="__PAGE_DESCRIPTION__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:title" content="__PAGE_TITLE__ {DOT} gilly.space">
<meta property="og:url" content="https://gilly.space/__PAGE_PATH__">
<meta property="og:image" content="__OG_IMAGE__">
<!-- /bake:template -->
<!-- after the template, ignored: __CF_BEACON_TOKEN__ -->
"""
PAGE = {"path": "a.html", "url": "/a.html", "title": "A &amp; B", "description": "About A."}


def bake():
    return importlib.import_module("bake")


class HeadTest(unittest.TestCase):
    def ctx(self, template: str = TEMPLATE):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        (root / "partials").mkdir()
        (root / "partials" / "head.html").write_text(template, encoding="utf-8")
        return bake().Ctx(root, {})

    def test_template_drops_comments_and_blank_lines(self):
        self.assertEqual(bake().head_template(self.ctx()).split("\n"), [
            '<meta charset="utf-8">',
            f"<title>__PAGE_TITLE__ {DOT} gilly.space</title>",
            '<meta name="description" content="__PAGE_DESCRIPTION__">',
            '<link rel="canonical" href="__CANONICAL__">',
            f'<meta property="og:title" content="__PAGE_TITLE__ {DOT} gilly.space">',
            '<meta property="og:url" content="https://gilly.space/__PAGE_PATH__">',
            '<meta property="og:image" content="__OG_IMAGE__">',
        ])

    def test_defaults(self):
        out = bake().render_head(self.ctx(), PAGE)
        self.assertIn(f"<title>A &amp; B {DOT} gilly.space</title>", out)
        self.assertIn('<meta name="description" content="About A.">', out)
        self.assertIn('<link rel="canonical" href="https://gilly.space/a.html">', out)
        self.assertIn('<meta property="og:url" content="https://gilly.space/a.html">', out)
        self.assertIn('<meta property="og:image" content="https://gilly.space/images/bg.jpg">', out)

    def test_overrides(self):
        page = dict(PAGE, head_title="Full title", canonical="https://example.org/x", og_image="https://example.org/i.png")
        out = bake().render_head(self.ctx(), page)
        self.assertIn("<title>Full title</title>", out)
        self.assertIn('<meta property="og:title" content="Full title">', out)
        self.assertIn('<link rel="canonical" href="https://example.org/x">', out)
        self.assertIn('<meta property="og:image" content="https://example.org/i.png">', out)
        self.assertIn('<meta property="og:url" content="https://gilly.space/a.html">', out)

    def test_og_url_override_replaces_only_the_og_url(self):
        page = dict(PAGE, canonical="https://gilly.space/a", og_url="https://gilly.space/a")
        out = bake().render_head(self.ctx(), page)
        self.assertIn('<meta property="og:url" content="https://gilly.space/a">', out)
        self.assertIn('<link rel="canonical" href="https://gilly.space/a">', out)
        self.assertNotIn("a.html", out)

    def test_no_canonical_drops_the_canonical_and_og_url_lines(self):
        out = bake().render_head(self.ctx(), dict(PAGE, no_canonical=True))
        self.assertNotIn("canonical", out)
        self.assertNotIn("og:url", out)
        self.assertIn('<meta property="og:image"', out)
        self.assertIn('<meta name="description"', out)

    def test_head_problems_without_a_canonical_wants_none(self):
        head = ('<html lang="en"><head><title>t</title><meta name="description" content="d">'
                '<meta property="og:image" content="i"></head>')
        self.assertEqual(bake().head_problems(head, canonical=False), [])
        self.assertEqual(bake().head_problems(head), ["canonical link appears 0 times in <head>"])
        both = head.replace("</head>", '<link rel="canonical" href="c"><meta property="og:url" content="u"></head>')
        self.assertEqual(bake().head_problems(both, canonical=False),
                         ["canonical link appears 1 times in <head>", "og:url appears 1 times in <head>"])

    def test_the_home_page_has_an_empty_path(self):
        out = bake().render_head(self.ctx(), dict(PAGE, path="index.html", url="/"))
        self.assertIn('<meta property="og:url" content="https://gilly.space/">', out)

    def test_a_page_without_a_description_is_an_error(self):
        with self.assertRaises(bake().BakeError) as cm:
            bake().render_head(self.ctx(), {k: v for k, v in PAGE.items() if k != "description"})
        self.assertIn("a.html has no description", str(cm.exception))

    def test_an_unfilled_placeholder_is_an_error(self):
        ctx = self.ctx(TEMPLATE.replace("__OG_IMAGE__", "__MYSTERY__"))
        with self.assertRaises(bake().BakeError) as cm:
            bake().render_head(ctx, PAGE)
        self.assertIn("unfilled placeholder __MYSTERY__", str(cm.exception))

    def test_head_problems_names_what_is_missing_or_doubled(self):
        good = ('<html lang="en"><head><title>t</title><meta name="description" content="d">'
                '<link rel="canonical" href="c"><meta property="og:image" content="i"></head>')
        self.assertEqual(bake().head_problems(good), [])
        bad = good.replace('lang="en"', 'lang="fr"').replace("<title>t</title>", "<title>t</title><title>u</title>")
        self.assertEqual(bake().head_problems(bad), ['<html> lacks lang="en"', "<title> appears 2 times in <head>"])


if __name__ == "__main__":
    unittest.main()
