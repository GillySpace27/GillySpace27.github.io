"""Tests for SU-10's offline additions to tools/check_site.py: shortlinks, case, lowercaser.

Trees are built in temporary folders (no committed fixtures, because a pair of paths that
differ only by case cannot exist on a case-insensitive disk). Run:
python3 -m unittest discover -s tools/tests -p 'test_check_site_su10.py' -v
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import check_site  # noqa: E402

ORIGIN = "https://gilly.space"
STUDIO = ORIGIN + "/heliofits-studio/"
SL = "heliosoftware/spec/shortlinks.json"
PLAIN = "<!doctype html>\n<title>page</title>\n"


def stub(target: str) -> str:
    return ('<!doctype html>\n'
            f'<meta http-equiv="refresh" content="0; url={target}">\n'
            f'<script>location.replace("{target}");</script>\n')


def links(*entries) -> str:
    return json.dumps({"version": 1, "links": [{"path": p, "target": t, "kind": "redirect"} for p, t in entries]})


class Tree(unittest.TestCase):
    def tree(self, files: dict) -> pathlib.Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return root

    def lines(self, root, rule):
        code, findings = check_site.run(root, [rule])
        return code, [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]


class Shortlinks(Tree):
    def test_clean_tree_passes(self):
        root = self.tree({"jhv/index.html": stub(STUDIO), "heliofits-studio/index.html": PLAIN,
                          SL: links(("jhv/", STUDIO))})
        self.assertEqual(self.lines(root, "shortlinks"), (0, []))

    def test_changed_stub_target_fails_naming_the_link(self):
        root = self.tree({"jhv/index.html": stub(ORIGIN + "/elsewhere/"), "heliofits-studio/index.html": PLAIN,
                          SL: links(("jhv/", STUDIO))})
        code, out = self.lines(root, "shortlinks")
        self.assertEqual(code, 1)
        self.assertIn("FAIL shortlinks jhv/index.html:2 https://gilly.space/heliofits-studio/ :: stub redirects to "
                      "https://gilly.space/elsewhere/ but shortlinks.json says https://gilly.space/heliofits-studio/", out)

    def test_removed_stub_fails(self):
        root = self.tree({"heliofits-studio/index.html": PLAIN, SL: links(("jhv/", STUDIO))})
        code, out = self.lines(root, "shortlinks")
        self.assertEqual(code, 1)
        self.assertIn("FAIL shortlinks jhv/index.html:0 https://gilly.space/heliofits-studio/ :: "
                      "listed short link has no tracked page", out)

    def test_page_that_stopped_redirecting_fails(self):
        root = self.tree({"jhv/index.html": PLAIN, "heliofits-studio/index.html": PLAIN, SL: links(("jhv/", STUDIO))})
        code, out = self.lines(root, "shortlinks")
        self.assertEqual(code, 1)
        self.assertIn("FAIL shortlinks jhv/index.html:0 https://gilly.space/heliofits-studio/ :: "
                      "listed short link is no longer a redirect stub", out)

    def test_unlisted_stub_warns_without_failing(self):
        root = self.tree({"jhv/index.html": stub(STUDIO), "hfs/index.html": stub(STUDIO),
                          "heliofits-studio/index.html": PLAIN, SL: links(("jhv/", STUDIO))})
        code, out = self.lines(root, "shortlinks")
        self.assertEqual(code, 0)
        self.assertIn("WARN shortlinks hfs/index.html:2 https://gilly.space/heliofits-studio/ :: redirect stub is not in "
                      "shortlinks.json (run python3 tools/check_site.py --write-shortlinks)", out)

    def test_missing_json_is_skipped(self):
        root = self.tree({"jhv/index.html": stub(STUDIO)})
        code, out = self.lines(root, "shortlinks")
        self.assertEqual(code, 0)
        self.assertEqual(out, ["SKIP shortlinks heliosoftware/spec/shortlinks.json:0 - :: no shortlinks.json in this tree"])

    def test_write_shortlinks_round_trip(self):
        root = self.tree({"jhv/index.html": stub(STUDIO), "shop/index.html": stub("/shop"),
                          "heliofits-studio/index.html": PLAIN, "shop.html": PLAIN})
        self.assertEqual(check_site.main(["--root", str(root), "--write-shortlinks"]), 0)
        data = json.loads((root / SL).read_text(encoding="utf-8"))
        self.assertEqual(data["links"], [{"path": "jhv/", "target": STUDIO, "kind": "redirect"},
                                         {"path": "shop/", "target": ORIGIN + "/shop", "kind": "redirect"}])
        self.assertEqual(self.lines(root, "shortlinks"), (0, []))


class CaseAndLowercaser(Tree):
    def test_case_twins_function(self):
        files = {"JHV/index.html", "jhv/index.html", "a.html"}
        self.assertEqual(check_site.case_twins(files), [("JHV/index.html", "jhv/index.html")])

    def test_case_rule_names_both_paths(self):
        ctx = check_site.Ctx(root=pathlib.Path("."), files={"Foo/x.html", "foo/x.html"}, pages=[])
        out = check_site.check_case_twins(ctx)
        self.assertEqual([(f.level, f.rule, f.path, f.target) for f in out],
                         [("FAIL", "case", "foo/x.html", "Foo/x.html")])

    def test_lowercases_function(self):
        ok = "if (location.pathname !== location.pathname.toLowerCase()) location.replace(x);"
        self.assertTrue(check_site.lowercases(ok))
        self.assertFalse(check_site.lowercases("<p>nothing here</p>"))

    def test_lowercaser_rule_fails_when_the_line_is_gone(self):
        root = self.tree({"404.html": "<!doctype html><title>404</title>\n"})
        code, out = self.lines(root, "lowercaser")
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("FAIL lowercaser 404.html:0 - :: no longer sends a cased address"))


if __name__ == "__main__":
    unittest.main()
