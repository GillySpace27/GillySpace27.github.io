"""WS-10: the real tree carries no drift, and a hand edit is caught
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent


def run_bake(root: pathlib.Path, *args: str):
    r = subprocess.run([sys.executable, str(root / "tools" / "bake.py"), "--root", str(root), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


class TreeTest(unittest.TestCase):
    def test_real_tree_has_no_drift(self):
        self.assertEqual(run_bake(REPO, "--check"), (0, ""))

    def test_a_hand_edit_is_drift_that_names_the_page_and_bake_repairs_it(self):
        site = json.loads((REPO / "site.json").read_text(encoding="utf-8"))
        rels = {"site.json", "assets/site.js", "partials/header.html", "sitemap.xml", "tools/bake.py",
                "tools/templates/stub.html", "tools/templates/stub-shop.html", "tools/archived_pages.txt"}
        rels |= {p["path"] for p in site["pages"]} | {s["path"] for s in site["stubs"]}
        # WS-16: the share target reads sun.html and the fixture manifests, writes s/<id>/index.html
        rels |= {"sun.html", "tools/templates/share.html"}
        rels |= {f"fixtures/sun/manifest/{e['id']}.json" for e in site["share"]}
        rels |= {f"s/{e['id']}/index.html" for e in site["share"]}
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel in rels:
                if (REPO / rel).is_file():
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(REPO / rel, root / rel)
            self.assertEqual(run_bake(root, "--check"), (0, ""), "the copy starts clean")
            page = root / "Research.html"
            text = page.read_text(encoding="utf-8")
            self.assertEqual(text.count('<a href="/sun.html">The Sun</a> ·'), 1)
            page.write_text(text.replace('<a href="/sun.html">The Sun</a> ·', '<a href="/sun.html">THE SUN</a> ·'),
                            encoding="utf-8")
            self.assertEqual(run_bake(root, "--check"), (1, "DRIFT Research.html noscript\n"))
            self.assertEqual(run_bake(root)[0], 0)
            self.assertEqual(run_bake(root, "--check"), (0, ""))


if __name__ == "__main__":
    unittest.main()
