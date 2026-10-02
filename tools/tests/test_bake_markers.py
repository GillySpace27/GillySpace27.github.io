"""WS-10: the bake markers are in site.js and in the pages that carry a <noscript> nav
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import json
import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


class MarkersTest(unittest.TestCase):
    def test_markers_are_in_place(self):
        js = read("assets/site.js")
        self.assertEqual(js.count("/* bake:header-fallback */"), 1)
        self.assertEqual(js.count("/* bake:palette-items */"), 1)
        self.assertEqual(js.count("/* /bake */"), 2)
        pages = json.loads(read("site.json"))["pages"]
        marked = [p["path"] for p in pages if "<!-- bake:noscript -->" in read(p["path"])]
        carrying = [p["path"] for p in pages if "<noscript>" in read(p["path"])]
        self.assertEqual(len(carrying), 16, carrying)
        self.assertEqual(marked, carrying)


if __name__ == "__main__":
    unittest.main()
