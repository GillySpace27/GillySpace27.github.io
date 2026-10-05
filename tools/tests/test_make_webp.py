"""WS-11: tools/make_webp.py (run: python3 -m unittest discover -s tools/tests -p 'test_*.py').

The conversion test needs Pillow or cwebp and is skipped without one; the size and markup
functions are pure.
"""
from __future__ import annotations

import importlib
import pathlib
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))


def mw():
    return importlib.import_module("make_webp")


def write_png(path: pathlib.Path, w: int, h: int) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80\x40\xc0" * w for _ in range(h))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def have_converter() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return shutil.which("cwebp") is not None


class SizeTest(unittest.TestCase):
    def test_png_size_reads_the_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "a.png"
            write_png(p, 1120, 597)
            self.assertEqual(mw().png_size(p), (1120, 597))
            p.write_bytes(b"not a png at all, not at all")
            with self.assertRaises(SystemExit):
                mw().png_size(p)

    def test_target_size_caps_the_width_and_keeps_the_ratio(self):
        self.assertEqual(mw().target_size(1120, 597), (760, 405))
        self.assertEqual(mw().target_size(760, 488), (760, 488))
        self.assertEqual(mw().target_size(684, 442), (684, 442))


class PictureTest(unittest.TestCase):
    def test_wraps_an_img_and_keeps_its_attributes(self):
        img = '<img class="card__img" loading="lazy" src="images/cards/store.png" alt="Store">'
        self.assertEqual(
            mw().picture(img, "images/cards/store.webp", 760, 405),
            '<picture><source type="image/webp" srcset="images/cards/store.webp">'
            '<img width="760" height="405" class="card__img" loading="lazy" src="images/cards/store.png" alt="Store"></picture>')

    def test_a_space_in_the_path_is_encoded_in_srcset_only(self):
        img = '<img class="card__img" src="images/thumbs/Paper Tile.png" alt="">'
        out = mw().picture(img, "images/thumbs/Paper Tile.webp", 684, 442)
        self.assertIn('srcset="images/thumbs/Paper%20Tile.webp"', out)
        self.assertIn('src="images/thumbs/Paper Tile.png"', out)

    def test_not_an_img_is_an_error(self):
        with self.assertRaises(ValueError):
            mw().picture("<div>", "x.webp", 1, 1)


class ConvertTest(unittest.TestCase):
    @unittest.skipUnless(have_converter(), "neither Pillow nor cwebp is available (UNCHECKED)")
    def test_writes_a_smaller_webp_beside_the_png_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "big.png"
            write_png(src, 1000, 500)
            before = src.read_bytes()
            self.assertEqual(mw().main([str(src)]), 0)
            webp = src.with_suffix(".webp")
            self.assertTrue(webp.is_file())
            self.assertEqual(webp.read_bytes()[:4], b"RIFF")
            self.assertEqual(src.read_bytes(), before)
            mtime = webp.stat().st_mtime_ns
            self.assertEqual(mw().main([str(src)]), 0)
            self.assertEqual(webp.stat().st_mtime_ns, mtime)


if __name__ == "__main__":
    unittest.main()
