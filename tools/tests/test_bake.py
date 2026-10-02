"""WS-10: tools/bake.py and site.json (run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

RealTreeTest compares what bake.py renders with what the tracked files hold today, so a
renamed link or a reworded label fails here before it reaches a page. MiniTest runs the
CLI on a throwaway site, so no test writes into the real checkout.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))


def bake():
    return importlib.import_module("bake")


def real_site() -> dict:
    return json.loads((REPO / "site.json").read_text(encoding="utf-8"))


def read(rel: str) -> str:
    return bake().read_file(REPO / rel)


class RealTreeTest(unittest.TestCase):
    def test_site_json_is_canonical(self):
        raw = read("site.json")
        self.assertEqual(raw, json.dumps(json.loads(raw), indent=2, ensure_ascii=True) + "\n")

    def test_header_fallback_is_what_site_js_has(self):
        m = re.search(r"var HEADER_FALLBACK = (?:/\* bake:header-fallback \*/ )?('(?:[^'\\\n]|\\.)*')",
                      read("assets/site.js"))
        self.assertIsNotNone(m, "HEADER_FALLBACK not found in assets/site.js")
        self.assertEqual(m.group(1), bake().render_header_fallback(real_site()))

    def test_palette_items_are_what_site_js_has(self):
        js = read("assets/site.js")
        start = js.index("var ITEMS = [\n") + len("var ITEMS = [\n")
        end = js.index("\n    ];", start)
        body = "\n".join(ln for ln in js[start:end].split("\n") if "bake" not in ln)
        self.assertEqual(body, bake().render_palette_items(real_site()))

    def test_stubs_reproduce_the_tracked_files(self):
        ctx = bake().Ctx(REPO, real_site())
        for stub in real_site()["stubs"]:
            self.assertEqual(bake().render_stub(ctx, stub), read(stub["path"]), stub["path"])

    def test_header_nav_is_what_the_partial_has(self):
        html = read("partials/header.html")
        start_tag = '<nav class="site-nav" aria-label="Primary">\n'
        start = html.index(start_tag) + len(start_tag)
        end = html.index("\n    </nav>", start)
        body = "\n".join(ln for ln in html[start:end].split("\n") if "bake" not in ln)
        self.assertEqual(body, bake().render_header_nav(real_site()))


class RegionTest(unittest.TestCase):
    def test_html_region_keeps_the_closing_indent(self):
        text = "a\n  <!-- bake:x -->\n  old\n  <!-- /bake -->\nb\n"
        self.assertEqual(bake().replace_region(text, "x", "  new", "html"),
                         "a\n  <!-- bake:x -->\n  new\n  <!-- /bake -->\nb\n")

    def test_js_inline_region(self):
        text = "var A = /* bake:a */ 'old' /* /bake */;\n"
        self.assertEqual(bake().replace_region(text, "a", "'new'", "js-inline"),
                         "var A = /* bake:a */ 'new' /* /bake */;\n")

    def test_no_region_is_an_error(self):
        with self.assertRaises(bake().BakeError) as cm:
            bake().replace_region("nothing here", "x", "b", "html")
        self.assertIn("expected exactly 1 '<!-- bake:x -->', found 0", str(cm.exception))

    def test_two_regions_is_an_error(self):
        text = "<!-- bake:x -->\n<!-- /bake -->\n<!-- bake:x -->\n<!-- /bake -->\n"
        with self.assertRaises(bake().BakeError) as cm:
            bake().replace_region(text, "x", "b", "html")
        self.assertIn("found 2", str(cm.exception))


SITE = {
    "schema": 1,
    "nav": [{"label": "One", "href": "/one.html"}, {"label": "Two", "href": "/two/"}],
    "pages": [
        {"path": "index.html", "url": "/", "title": "Home", "palette": "Home", "keywords": "home",
         "sitemap": True, "priority": "1.0", "archived": False},
        {"path": "one.html", "url": "/one.html", "title": "One", "palette": "One", "keywords": "uno",
         "sitemap": True, "priority": "0.5", "archived": False},
        {"path": "old.html", "url": "/old.html", "title": "Old", "palette": None, "keywords": "",
         "sitemap": True, "priority": "0.1", "archived": True},
        {"path": "gone.html", "url": "/gone.html", "title": "Gone", "palette": None, "keywords": "",
         "sitemap": True, "priority": "0.1", "archived": False},
    ],
    "palette_extra": [{"t": "Toggle theme", "u": "#theme", "k": "dark"}],
    "stubs": [{"path": "go/index.html", "title": "Go", "target": "https://gilly.space/one.html",
               "template": "stub.html"}],
    "share": [],
}
PAGE = "<html><body>\n<!-- bake:noscript -->\n<noscript></noscript>\n<!-- /bake -->\n</body></html>\n"
SITE_JS = ("var HEADER_FALLBACK = /* bake:header-fallback */ '' /* /bake */;\n"
           "function f() {\n    var ITEMS = [\n      /* bake:palette-items */\n      /* /bake */\n    ];\n}\n")


class MiniTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name) / "mini"
        (self.root / "assets").mkdir(parents=True)
        (self.root / "tools" / "templates").mkdir(parents=True)
        for name in ("stub.html", "stub-shop.html"):
            (self.root / "tools" / "templates" / name).write_text(read("tools/templates/" + name), encoding="utf-8")
        (self.root / "site.json").write_text(json.dumps(SITE, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        (self.root / "assets" / "site.js").write_text(SITE_JS, encoding="utf-8")
        for name in ("index.html", "one.html", "old.html", "gone.html"):
            (self.root / name).write_text(PAGE, encoding="utf-8")
        (self.root / "sitemap.xml").write_text("<urlset/>\n", encoding="utf-8")
        (self.root / "tools" / "archived_pages.txt").write_text("# test\ngone.html\n", encoding="utf-8")

    def run_bake(self, *args):
        r = subprocess.run([sys.executable, str(TOOLS / "bake.py"), "--root", str(self.root), *args],
                           capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_first_bake_then_check_is_clean(self):
        code, out = self.run_bake()
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"bake: 7 file\(s\) written")
        self.assertEqual(self.run_bake("--check"), (0, ""))

    def test_check_names_a_hand_edited_noscript_and_bake_fixes_it(self):
        self.run_bake()
        page = self.root / "index.html"
        page.write_text(page.read_text().replace(">One<", ">ONE<"), encoding="utf-8")
        code, out = self.run_bake("--check")
        self.assertEqual((code, out), (1, "DRIFT index.html noscript\n"))
        self.assertEqual(self.run_bake()[0], 0)
        self.assertEqual(self.run_bake("--check"), (0, ""))

    def test_check_never_writes(self):
        before = (self.root / "index.html").read_text()
        code, out = self.run_bake("--check")
        self.assertEqual(code, 1)
        self.assertIn("DRIFT index.html noscript", out)
        self.assertEqual((self.root / "index.html").read_text(), before)

    def test_missing_marker_is_an_error_not_a_skip(self):
        (self.root / "assets" / "site.js").write_text("var HEADER_FALLBACK = '';\n", encoding="utf-8")
        code, out = self.run_bake("--check")
        self.assertEqual(code, 1)
        self.assertIn("ERROR bake: expected exactly 1 '/* bake:header-fallback */', found 0", out)

    def test_header_fallback_palette_and_stub_content(self):
        self.run_bake()
        js = (self.root / "assets" / "site.js").read_text()
        self.assertIn("<a href=\"/one.html\">One</a> <a href=\"/two/\">Two</a>", js)
        self.assertIn("      { t: 'Home', u: '/', k: 'home' },\n      { t: 'One', u: '/one.html', k: 'uno' },\n"
                      "      { t: 'Toggle theme', u: '#theme', k: 'dark' }\n      /* /bake */\n    ];", js)
        stub = (self.root / "go" / "index.html").read_text()
        self.assertIn("<title>Go</title>", stub)
        self.assertIn('location.replace("https://gilly.space/one.html");', stub)

    def test_sitemap_skips_archived_and_listed_pages(self):
        self.run_bake()
        sm = (self.root / "sitemap.xml").read_text()
        self.assertIn("<loc>https://gilly.space/</loc><priority>1.0</priority>", sm)
        self.assertIn("<loc>https://gilly.space/one.html</loc>", sm)
        self.assertNotIn("old.html", sm)       # "archived": true
        self.assertNotIn("gone.html", sm)      # listed in tools/archived_pages.txt

    def test_check_ignores_a_lastmod_only_difference(self):
        self.run_bake()
        sm = self.root / "sitemap.xml"
        sm.write_text(re.sub(r"<lastmod>[^<]*</lastmod>", "<lastmod>1999-01-01</lastmod>", sm.read_text()), encoding="utf-8")
        self.assertEqual(self.run_bake("--check"), (0, ""))

    def test_only_limits_the_targets(self):
        self.run_bake()
        page = self.root / "one.html"
        page.write_text(page.read_text().replace(">One<", ">ONE<"), encoding="utf-8")
        self.assertEqual(self.run_bake("--check", "--only", "stubs"), (0, ""))
        self.assertEqual(self.run_bake("--check", "--only", "noscript"), (1, "DRIFT one.html noscript\n"))


if __name__ == "__main__":
    unittest.main()
