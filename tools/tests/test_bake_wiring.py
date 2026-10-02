"""WS-10: tools/check_site.py runs tools/bake.py --check as rule "bake"
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
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "tests"))
import check_site  # noqa: E402
import test_bake  # noqa: E402  (its SITE, PAGE and SITE_JS describe a tiny site)


def lines(findings) -> list[str]:
    return [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]


class WiringTest(unittest.TestCase):
    def test_bake_check_is_an_external_check(self):
        self.assertIn(("bake", "tools/bake.py", ["python3", "tools/bake.py", "--check"]),
                      check_site.EXTERNAL_CHECKS)

    def test_a_hand_edit_makes_check_site_fail_and_name_the_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "tools" / "templates").mkdir(parents=True)
            (root / "assets").mkdir()
            shutil.copy(TOOLS / "bake.py", root / "tools" / "bake.py")
            for name in ("stub.html", "stub-shop.html"):
                shutil.copy(TOOLS / "templates" / name, root / "tools" / "templates" / name)
            (root / "site.json").write_text(json.dumps(test_bake.SITE, indent=2, ensure_ascii=True) + "\n")
            (root / "assets" / "site.js").write_text(test_bake.SITE_JS)
            for name in ("index.html", "one.html", "old.html", "gone.html"):
                (root / name).write_text(test_bake.PAGE)
            (root / "sitemap.xml").write_text("<urlset/>\n")
            self.assertEqual(check_site.run(root, ["bake"])[0], 1, "an unbaked tree must fail")
            subprocess.run([sys.executable, str(root / "tools" / "bake.py"), "--root", str(root)],
                           check=True, capture_output=True)
            self.assertEqual(check_site.run(root, ["bake"]), (0, []))
            page = root / "index.html"
            page.write_text(page.read_text().replace(">One<", ">ONE<"))
            code, findings = check_site.run(root, ["bake"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL bake index.html:0 - :: noscript", lines(findings))


if __name__ == "__main__":
    unittest.main()
