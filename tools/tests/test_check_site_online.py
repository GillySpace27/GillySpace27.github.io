"""Tests for SU-10's --online mode and the fallback rule in tools/check_site.py.

No sockets: a fake getter answers from a table. The real fetch() is exercised by the
Gilly-run verification in the task file. Run:
python3 -m unittest discover -s tools/tests -p 'test_check_site_online.py' -v
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
LOWER = (b"<script>if (location.pathname !== location.pathname.toLowerCase()) "
         b"location.replace(location.pathname.toLowerCase());</script>")


def F(status, url, body):
    return check_site.Fetched(status, url, body)


def stub(target: str) -> bytes:
    return (f'<!doctype html>\n<meta http-equiv="refresh" content="0; url={target}">\n'
            f'<script>location.replace("{target}");</script>\n').encode()


def fake(table):
    calls = []

    def getter(url):
        calls.append(url)
        return table.get(url, F(404, url, b""))
    getter.calls = calls
    return getter


class Online(unittest.TestCase):
    def tree(self, files: dict) -> pathlib.Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = pathlib.Path(tmp.name)
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return root

    def shortlinks_tree(self, *entries):
        data = {"version": 1, "links": [{"path": p, "target": t, "kind": "redirect"} for p, t in entries]}
        return self.tree({SL: json.dumps(data)})

    def online(self, root, table, base=ORIGIN):
        code, findings = check_site.run_online(root, getter=fake(table), base=base)
        return code, [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]

    def good_table(self):
        return {ORIGIN + "/jhv/": F(200, ORIGIN + "/jhv/", stub(STUDIO)),
                STUDIO: F(200, STUDIO, b"<html>Studio</html>"),
                ORIGIN + "/JHV/": F(404, ORIGIN + "/JHV/", LOWER)}

    def test_follow_reaches_the_final_page(self):
        got = check_site.follow(ORIGIN + "/jhv/", fake(self.good_table()))
        self.assertEqual((got.status, got.url), (200, STUDIO))

    def test_follow_detects_a_loop(self):
        table = {ORIGIN + "/a/": F(200, ORIGIN + "/a/", stub(ORIGIN + "/b/")),
                 ORIGIN + "/b/": F(200, ORIGIN + "/b/", stub(ORIGIN + "/a/"))}
        got = check_site.follow(ORIGIN + "/a/", fake(table))
        self.assertEqual(got.status, -1)

    def test_live_shortlinks_pass(self):
        root = self.shortlinks_tree(("jhv/", STUDIO))
        self.assertEqual(self.online(root, self.good_table()), (0, []))

    def test_wrong_destination_names_the_link(self):
        root = self.shortlinks_tree(("jhv/", STUDIO))
        table = self.good_table()
        table[STUDIO] = F(200, ORIGIN + "/other/", b"<html>x</html>")
        code, out = self.online(root, table)
        self.assertEqual(code, 1)
        self.assertIn("FAIL live-shortlink jhv/:0 https://gilly.space/heliofits-studio/ :: "
                      "ended at https://gilly.space/other/, expected https://gilly.space/heliofits-studio/", out)

    def test_empty_destination_fails(self):
        root = self.shortlinks_tree(("jhv/", STUDIO))
        table = self.good_table()
        table[STUDIO] = F(200, STUDIO, b"  \n")
        code, out = self.online(root, table)
        self.assertEqual(code, 1)
        self.assertIn("FAIL live-shortlink jhv/:0 https://gilly.space/heliofits-studio/ :: "
                      "empty page at https://gilly.space/heliofits-studio/", out)

    def test_http_404_destination_fails(self):
        root = self.shortlinks_tree(("jhv/", STUDIO))
        table = self.good_table()
        del table[STUDIO]
        code, out = self.online(root, table)
        self.assertEqual(code, 1)
        self.assertIn("FAIL live-shortlink jhv/:0 https://gilly.space/heliofits-studio/ :: "
                      "HTTP 404 at https://gilly.space/heliofits-studio/", out)

    def test_loop_names_the_link(self):
        root = self.shortlinks_tree(("jhv/", STUDIO))
        table = self.good_table()
        table[STUDIO] = F(200, STUDIO, stub(ORIGIN + "/jhv/"))
        code, out = self.online(root, table)
        self.assertEqual(code, 1)
        self.assertTrue(any(ln.startswith("FAIL live-shortlink jhv/:0 ") and "redirect loop" in ln for ln in out), out)

    def test_base_is_rewritten_for_local_servers(self):
        base = "http://127.0.0.1:8123"
        root = self.shortlinks_tree(("jhv/", STUDIO))
        table = {base + "/jhv/": F(200, base + "/jhv/", stub(STUDIO)),
                 base + "/heliofits-studio/": F(200, base + "/heliofits-studio/", b"<html>Studio</html>"),
                 base + "/JHV/": F(404, base + "/JHV/", LOWER)}
        getter = fake(table)
        code, findings = check_site.run_online(root, getter=getter, base=base)
        self.assertEqual((code, findings), (0, []))
        self.assertTrue(all(u.startswith(base) for u in getter.calls), getter.calls)

    def test_live_lowercaser(self):
        root = self.shortlinks_tree()
        self.assertEqual(self.online(root, self.good_table()), (0, []))
        table = self.good_table()
        table[ORIGIN + "/JHV/"] = F(404, ORIGIN + "/JHV/", b"<html>Lost in space</html>")
        code, out = self.online(root, table)
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("FAIL live-lowercaser JHV/:0 - :: the live 404 page does not lowercase"), out)


class Fallback(unittest.TestCase):
    def run_rule(self, page_text, records):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root / "heliosoftware" / "feed").mkdir(parents=True)
            (root / "heliosoftware" / "feed" / "heliofits-studio.json").write_text(
                json.dumps({"product": "heliofits-studio", "records": records}), encoding="utf-8")
            (root / "heliofits-studio").mkdir()
            (root / "heliofits-studio" / "index.html").write_text(page_text, encoding="utf-8")
            code, findings = check_site.run(root, ["fallback"])
            return code, [f"{f.level} {f.rule} {f.path}:{f.line} {f.target} :: {f.msg}" for f in findings]

    PAGE = '<p>Version <span data-release="heliofits-studio" data-release-field="version">{v}</span></p>\n'

    def test_older_fallback_fails(self):
        code, out = self.run_rule(self.PAGE.format(v="0.8.2"), [{"version": "0.8.2"}, {"version": "0.8.3"}])
        self.assertEqual(code, 1)
        self.assertIn("FAIL fallback heliofits-studio/index.html:1 heliofits-studio :: static fallback 0.8.2 is older "
                      "than the feed's 0.8.3 (heliosoftware/feed/heliofits-studio.json); re-pin the page", out)

    def test_current_or_empty_fallback_passes(self):
        self.assertEqual(self.run_rule(self.PAGE.format(v="v0.8.3"), [{"version": "0.8.3"}]), (0, []))
        self.assertEqual(self.run_rule(self.PAGE.format(v=""), [{"version": "0.8.3"}]), (0, []))


if __name__ == "__main__":
    unittest.main()
