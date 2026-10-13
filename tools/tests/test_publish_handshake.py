"""SU-14 Task 1: the publish-handshake spec page agrees with the Heliogram contract."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "heliosoftware" / "spec" / "publish-handshake.md"
CONTRACT = ROOT / "contracts" / "heliogram-publish.md"
INDEX = ROOT / "heliosoftware" / "spec" / "index.html"


def row(product):
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| {product} |"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            return cells
    return None


def paths(cell):
    return set(re.findall(r"`([^`]+)`", cell))


class PublishHandshakeTest(unittest.TestCase):
    def test_page_exists_with_one_heliogram_row(self):
        self.assertTrue(SPEC.is_file(), "heliosoftware/spec/publish-handshake.md is missing")
        lines = SPEC.read_text(encoding="utf-8").splitlines()
        self.assertEqual(sum(1 for l in lines if l.startswith("| Heliogram |")), 1)

    def test_website_owns_the_heliogram_pages(self):
        cells = row("Heliogram")
        self.assertIsNotNone(cells)
        writes, never = paths(cells[1]), paths(cells[2])
        for page in ("heliogram/index.html", "heliogram/privacy.html"):
            self.assertIn(page, never)
            self.assertNotIn(page, writes)
        self.assertFalse(writes & never, "a path is both written and never written")

    def test_frozen_heliograph_files_are_never_written(self):
        text = CONTRACT.read_text(encoding="utf-8")
        frozen = re.search(r"```frozen\n(.*?)```", text, re.S).group(1).split()
        never = paths(row("Heliogram")[2])
        writes = paths(row("Heliogram")[1])
        for f in frozen:
            if f == "heliograph/index.html":
                # SU-1: the redirect page is the one heliograph/ file publish.sh writes.
                self.assertIn(f, writes)
            else:
                self.assertIn(f, never)

    def test_spec_index_lists_the_page(self):
        self.assertEqual(INDEX.read_text(encoding="utf-8").count('href="publish-handshake.md"'), 1)


if __name__ == "__main__":
    unittest.main()
