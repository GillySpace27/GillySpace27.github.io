"""WS-10: the warn-only parity rule of tools/check_site.py
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402

HEADER = """\
<header><nav class="site-nav" aria-label="Primary">
<a href="/a.html">A</a>
<div class="nav-drop"><a href="/b/">B<span class="nav-drop__caret" aria-hidden="true"></span></a>
<div class="nav-drop__menu"><a href="/b/x/"><span><b>X</b></span></a></div></div>
</nav></header>
"""
JS = """\
  var HEADER_FALLBACK = '<nav class="site-nav" aria-label="Primary"><a href="/a.html">A</a> <a href="/b/">B</a></nav>';
  var ITEMS = [
      { t: 'A', u: '/a.html', k: 'a' }
    ];
"""
GOOD = '<noscript><nav aria-label="Primary"><a href="/a.html">A</a> <a href="/b/">B</a></nav></noscript>\n'
BAD = '<noscript><nav aria-label="Primary"><a href="/a.html">A</a></nav></noscript>\n'


def lines(findings) -> list[str]:
    return [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]


class ParityTest(unittest.TestCase):
    def test_reports_the_copies_that_disagree_with_the_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "partials").mkdir()
            (root / "assets").mkdir()
            (root / "partials" / "header.html").write_text(HEADER)
            (root / "assets" / "site.js").write_text(JS)
            (root / "good.html").write_text(GOOD)
            (root / "bad.html").write_text(BAD)
            (root / "plain.html").write_text("<noscript><a href='/'>Home</a></noscript>\n")
            code, findings = check_site.run(root, ["parity"])
        self.assertEqual(code, 0, "parity is warn-only")
        self.assertEqual(sorted(lines(findings)), [
            "WARN parity assets/site.js:2 ITEMS :: command palette has no entry for /b/",
            "WARN parity bad.html:1 noscript :: differs from partials/header.html: missing /b/",
        ])

    def test_a_tree_without_a_header_partial_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "index.html").write_text(BAD)
            self.assertEqual(check_site.run(pathlib.Path(tmp), ["parity"]), (0, []))

    def test_nav_links_skips_the_drop_down_menu(self):
        self.assertEqual(check_site.nav_links(HEADER), [("/a.html", "A"), ("/b/", "B")])


if __name__ == "__main__":
    unittest.main()
