"""WS-16: per-channel share stubs (s/<id>/), site.json "share", and SunData.share
(run: python3 -m unittest discover -s tools/tests -p 'test_*.py').
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1]
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import bake  # noqa: E402
import check_site  # noqa: E402

NODE = shutil.which("node")
IDS = ["rainbow", "171", "193", "211", "304", "335", "94", "131", "1600", "1700", "composite_uv", "dem"]


def read(rel: str) -> str:
    return bake.read_file(REPO / rel)


class ShareStubTest(unittest.TestCase):
    def test_site_json_share_is_the_products_in_order(self):
        share = json.loads(read("site.json"))["share"]
        self.assertEqual([e["id"] for e in share], IDS)
        for e in share:
            self.assertEqual(sorted(e), ["id", "og_image", "title"])
            self.assertEqual(e["id"], e["id"].lower(), "Pages is case-sensitive: lowercase ids only")

    def test_share_ids_are_the_sun_contract_ids(self):
        ctx = bake.Ctx(REPO, json.loads(read("site.json")))
        self.assertEqual([e["id"] for e in bake.share_entries(ctx)], IDS)

    def test_every_stub_unfurls_and_redirects_to_its_card(self):
        for e in json.loads(read("site.json"))["share"]:
            text = read(f"s/{e['id']}/index.html")
            self.assertNotIn("__", text, e["id"])
            self.assertIn(f'<meta property="og:image" content="{e["og_image"]}">', text)
            self.assertTrue(e["og_image"].startswith("https://the-sun-now.s3.us-east-2.amazonaws.com/1k/"), e["id"])
            self.assertIn(f'<meta property="og:title" content="The Sun: {html.escape(e["title"], quote=True)}">', text)
            self.assertIn(f'<meta property="og:url" content="https://gilly.space/s/{e["id"]}/">', text)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', text)
            self.assertIn(f'<meta http-equiv="refresh" content="0; url=/sun.html#{e["id"]}">', text)
            self.assertIn(f'location.replace("/sun.html#{e["id"]}");', text)
            self.assertNotIn("heliograph.com", text)

    def test_stubs_are_not_in_the_sitemap_or_the_pages_list(self):
        self.assertNotIn("/s/", read("sitemap.xml"))
        self.assertFalse([p for p in json.loads(read("site.json"))["pages"] if p["path"].startswith("s/")])

    def test_check_site_stub_rule_follows_every_share_redirect(self):
        code, findings = check_site.run(REPO, ["stub"])
        self.assertEqual(code, 0, [f.msg for f in findings])
        self.assertFalse([f for f in findings if f.path.startswith("s/")], "no finding on an s/ stub")

    def test_a_label_with_markup_characters_is_escaped(self):
        tpl = read("tools/templates/share.html")
        out = bake.render_share_stub({"id": "x", "title": 'A "b" <i> & c', "og_image": "https://e.test/a?b=1&c=2"}, tpl)
        self.assertIn("The Sun: A &quot;b&quot; &lt;i&gt; &amp; c", out)
        self.assertIn("https://e.test/a?b=1&amp;c=2", out)

    def test_uppercase_id_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "sun.html").write_text('  const PRODUCTS = [\n    ["Rainbow","R"],\n  ];\n')
            with self.assertRaises(bake.BakeError) as cm:
                bake.share_entries(bake.Ctx(root, {}))
            self.assertIn("must be lowercase", str(cm.exception))

    def test_bake_rewrites_a_hand_edited_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for rel in ["sun.html", "tools/templates/share.html"] + \
                    [f"fixtures/sun/manifest/{i}.json" for i in IDS] + [f"s/{i}/index.html" for i in IDS]:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / rel, root / rel)
            mini = {"schema": 1, "nav": [], "pages": [], "palette_extra": [], "stubs": [],
                    "share": json.loads(read("site.json"))["share"]}
            (root / "site.json").write_text(json.dumps(mini, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            run = lambda *a: subprocess.run([sys.executable, str(TOOLS / "bake.py"), "--root", str(root), "--only", "share", *a],  # noqa: E731
                                            capture_output=True, text=True)
            self.assertEqual((run("--check").returncode, run("--check").stdout), (0, ""))
            stub = root / "s" / "171" / "index.html"
            stub.write_text(stub.read_text().replace("AIA 171", "AIA 172"))
            r = run("--check")
            self.assertEqual((r.returncode, r.stdout), (1, "DRIFT s/171/index.html share\n"))
            self.assertEqual(run().returncode, 0)
            self.assertEqual(run("--check").returncode, 0)


@unittest.skipUnless(NODE, "node is not installed")
class SunDataShareTest(unittest.TestCase):
    def test_share_paths_run_under_node(self):
        r = subprocess.run([NODE, str(REPO / "tools" / "tests" / "js" / "sun_share_check.mjs"), str(REPO)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sun share: ok", r.stdout)


class ShareMarkupTest(unittest.TestCase):
    def test_sun_html_has_the_share_button_toast_and_highlight(self):
        page = read("sun.html")
        self.assertEqual(page.count('data-action="share"'), 1, "one Share button in the card template")
        self.assertEqual(page.count('id="sun-toast"'), 1)
        self.assertIn("is-hl", page)
        css = read("assets/site.css")
        for sel in ("#sun-toast.show", ".card--sun.is-hl", 'button[data-action="share"]'):
            self.assertIn(sel, css, sel)

    def test_no_em_dash_or_heliograph_com_in_what_ws16_wrote(self):
        for rel in ("tools/templates/share.html", "tools/bake.py", "s/171/index.html"):
            text = read(rel)
            self.assertNotIn(chr(0x2014), text, rel)
            self.assertFalse(re.search(r"heliograph\.com", text.replace("myheliograph.com", "")), rel)


if __name__ == "__main__":
    unittest.main()
