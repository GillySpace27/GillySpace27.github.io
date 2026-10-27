"""Homepage front door (WS-14): a live Sun card, a Software card, one store name.

Run: python3 -m unittest discover -s tools/tests -p 'test_front_door.py' -v
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")


def article(marker: str) -> str:
    """The <article> ... </article> that contains marker."""
    i = INDEX.index(marker)
    return INDEX[INDEX.rindex("<article", 0, i):INDEX.index("</article>", i)]


class FrontDoor(unittest.TestCase):
    def test_sun_card_keeps_its_static_thumbnail_and_a_fallback(self):
        card = article('id="sun-card"')
        self.assertIn("card--sun", card)
        self.assertIn('src="https://the-sun-now.s3.us-east-2.amazonaws.com/thumb/rhef_171_thumb.png"', card)
        self.assertIn("onerror=", card)
        self.assertIn('href="sun.html"', card)

    def test_live_wiring_reads_the_171_manifest_through_the_shared_loader(self):
        script = INDEX[INDEX.index("sun-card goes live"):]
        script = script[:script.index("</script>")]
        self.assertRegex(script, r'"/assets/sun\.js\?v=\w+"')
        self.assertIn("loadManifest('171')", script)
        self.assertIn("prefers-reduced-motion", script)
        self.assertIn("saveData", script)
        for attr in ("muted = true", "playsInline = true", "preload = 'none'"):
            self.assertIn(attr, script)

    def test_software_card_follows_the_sun_card(self):
        sun = INDEX.index('id="sun-card"')
        sw = INDEX.index('<a href="/heliosoftware/">', sun)
        self.assertLess(sw, INDEX.index("Gilly&Cranmer2020.pdf"))
        self.assertNotIn("<article", INDEX[INDEX.index("</article>", sun) + 10:INDEX.rindex("<article", 0, sw)])
        i = sw
        card = INDEX[INDEX.rindex("<article", 0, i):INDEX.index("</article>", i)]
        self.assertIn("/assets/sw/heliogram.png", card)
        self.assertIn("/assets/sw/heliofits-studio.png", card)
        self.assertNotIn("HelioSoftware", card)

    def test_no_public_store_label_says_solar_archive(self):
        for rel in ("index.html", "shop.html", "shop/index.html", "assets/site.js", "sun.html",
                    "tools/templates/stub-shop.html"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"Solar Archive", text), rel)


if __name__ == "__main__":
    unittest.main()
