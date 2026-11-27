"""Homebrew sections and the reel on the software pages."""
import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGES = {"heliogram/index.html": "heliogram", "heliofits/index.html": "hfpeek",
         "heliofits-studio/index.html": "hfstudio"}


class BrewPages(unittest.TestCase):
    def test_each_app_page_has_tile_panel_and_the_script_that_fills_them(self):
        for page, cask in PAGES.items():
            text = (ROOT / page).read_text()
            self.assertEqual(text.count(f'data-brew="{cask}"'), 2, page)
            # the tag itself: a comment naming the file must not satisfy this
            self.assertRegex(text, r'<script src="/assets/product\.js\?v=\w+"></script>', page)
            self.assertIn(f"brew install --cask gillyspace27/tap/{cask}", text, page)

    def test_reel_pages_load_the_reel_in_the_head(self):
        for page in [*PAGES, "rhef/index.html"]:
            head = (ROOT / page).read_text().split("</head>")[0]
            self.assertRegex(head, r'<script src="/assets/reel\.js\?v=\w+"></script>', page)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_cask_and_file_versions(self):
        js = ("const p=require('./assets/product.js');console.log(JSON.stringify(["
              "p.caskVersion('cask \"a\" do\\n  version \"1.5.2,14\"\\nend'),p.caskVersion('404: Not Found'),"
              "p.hrefVersion('https://x/v9/HelioFITS-1.5.1-b13.zip'),p.hrefVersion('https://x/y.zip')]))")
        out = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), ["1.5.2", "", "1.5.1", ""])


if __name__ == "__main__":
    unittest.main()
