"""WS-11: the 20 shell pages carry a baked head and nothing was lost on the way
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import importlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

VERIFICATION = '<meta name="google-site-verification" content="gBmU3RrJO0EJM2ZK92nWp1mKEWWL5MvmJLVxTDAgF-c">'


def bake():
    return importlib.import_module("bake")


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def shell_pages() -> list:
    pages = json.loads(read("site.json"))["pages"]
    return [p["path"] for p in pages if "<!-- bake:head -->" in read(p["path"])]


class ShellPagesTest(unittest.TestCase):
    def test_twenty_pages_carry_the_marker(self):
        self.assertEqual(len(shell_pages()), 20, shell_pages())

    def test_each_has_one_title_description_canonical_og_image_and_lang(self):
        pages = shell_pages()
        self.assertEqual(len(pages), 20)
        for rel in pages:
            self.assertEqual(bake().head_problems(read(rel)), [], rel)

    def test_the_search_console_meta_is_on_every_shell_page_exactly_once(self):
        pages = shell_pages()
        self.assertEqual(len(pages), 20)
        for rel in pages:
            self.assertEqual(read(rel).count(VERIFICATION), 1, rel)

    def test_values_that_differ_for_a_reason_are_preserved(self):
        self.assertIn('<meta property="og:image" content="https://the-sun-now.s3.us-east-2.amazonaws.com/1k/rhef_rainbow_1k.png">',
                      read("sun.html"))
        self.assertIn('<link rel="canonical" href="https://apps.apple.com/app/id6790952544">', read("heliofits/index.html"))
        self.assertIn('<link rel="canonical" href="https://gilly.space/shop">', read("shop.html"))
        self.assertIn("<title>HelioFITS Studio</title>", read("heliofits-studio/index.html"))
        self.assertIn('<meta property="og:image" content="https://gilly.space/assets/sw/rhef-compare.jpg">', read("rhef/index.html"))

    def test_no_og_image_is_missing_on_any_shell_page(self):
        pages = shell_pages()
        self.assertEqual(len(pages), 20)
        self.assertEqual([r for r in pages if 'property="og:image"' not in read(r)], [])

    def test_bake_check_is_clean(self):
        r = subprocess.run([sys.executable, str(TOOLS / "bake.py"), "--check"], capture_output=True, text=True, cwd=REPO)
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class DriftTest(unittest.TestCase):
    def test_a_hand_edited_pre_paint_script_is_drift_that_names_the_page(self):
        site = json.loads(read("site.json"))
        rels = {"site.json", "assets/site.js", "partials/head.html", "partials/header.html", "sitemap.xml", "tools/bake.py",
                "tools/templates/stub.html", "tools/templates/stub-shop.html", "tools/archived_pages.txt"}
        rels |= {p["path"] for p in site["pages"]} | {s["path"] for s in site["stubs"]}
        # WS-16: the share target reads sun.html and the fixture manifests, writes s/<id>/index.html
        rels |= {"sun.html", "tools/templates/share.html"}
        rels |= {f"fixtures/sun/manifest/{e['id']}.json" for e in site["share"]}
        rels |= {f"s/{e['id']}/index.html" for e in site["share"]}

        def run_bake(root, *args):
            r = subprocess.run([sys.executable, str(root / "tools" / "bake.py"), "--root", str(root), *args],
                               capture_output=True, text=True)
            return r.returncode, r.stdout

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel in rels:
                if (REPO / rel).is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(REPO / rel, root / rel)
            self.assertEqual(run_bake(root, "--check"), (0, ""), "the copy starts clean")
            page = root / "sun.html"
            text = page.read_text(encoding="utf-8")
            self.assertEqual(text.count("|| 'system'"), 1)
            page.write_text(text.replace("|| 'system'", "|| 'light'"), encoding="utf-8")
            self.assertEqual(run_bake(root, "--check"), (1, "DRIFT sun.html head\n"))
            self.assertEqual(run_bake(root, "--only", "head")[0], 0)
            self.assertEqual(run_bake(root, "--check"), (0, ""))


if __name__ == "__main__":
    unittest.main()
