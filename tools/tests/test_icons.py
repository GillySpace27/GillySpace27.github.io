"""WS-11: the icons rule of tools/check_site.py and the partials that use the sprite
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
FIX = TOOLS / "tests" / "fixtures"
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402

IDS = {"arxiv", "orcid", "ads", "github", "linkedin-square", "soundcloud", "envelope-o"}


def lines(findings) -> list[str]:
    return [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]


class IconsRuleTest(unittest.TestCase):
    def test_an_icon_font_class_fails_with_file_and_line(self):
        code, findings = check_site.run(FIX / "font-icon", ["icons"])
        self.assertEqual(code, 1)
        self.assertEqual(len(findings), 1, lines(findings))
        self.assertTrue(lines(findings)[0].startswith("FAIL icons index.html:3 fa fa-github :: icon-font class on a live page"))

    def test_an_archived_page_is_exempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "site"
            shutil.copytree(FIX / "font-icon", root)
            (root / "tools").mkdir()
            (root / "tools" / "archived_pages.txt").write_text("# test\nindex.html\n")
            self.assertEqual(check_site.run(root, ["icons"]), (0, []))

    def test_ok_site_and_the_real_tree_are_clean(self):
        self.assertEqual(check_site.run(FIX / "ok-site", ["icons"]), (0, []))
        code, findings = check_site.run(REPO, ["icons"])
        self.assertEqual((code, lines(findings)), (0, []))


class PartialsTest(unittest.TestCase):
    def test_the_partials_only_use_symbols_that_exist(self):
        for rel in ("partials/header.html", "partials/footer.html"):
            used = set(re.findall(r'<use href="/assets/icons\.svg#([^"]+)"', (REPO / rel).read_text(encoding="utf-8")))
            self.assertTrue(used, rel)
            self.assertLessEqual(used, IDS, rel)

    def test_the_service_worker_precaches_the_sprite_not_the_icon_fonts(self):
        sw = (REPO / "sw.js").read_text(encoding="utf-8")
        self.assertIn("'/assets/icons.svg'", sw)
        self.assertNotIn("font-awesome.min.css", sw)
        self.assertNotIn("academicons.min.css", sw)


if __name__ == "__main__":
    unittest.main()
