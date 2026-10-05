#!/usr/bin/env python3
"""Write WebP copies beside the PNG card images, and wrap an <img> in <picture> (WS-11).

  python3 tools/make_webp.py IMAGE.png [IMAGE.png ...]

Each WebP is written next to its PNG (`images/cards/store.png` gives `images/cards/store.webp`),
at most 760 px wide (a card shows at about 360 CSS px, so this covers a 2x screen), quality 82
(estimated; look at the result). The source image is never changed, and an existing .webp is
never overwritten. Converter: Pillow if it imports, else the `cwebp` command, else the script
prints UNCHECKED and exits 3. Prints "<webp> <width>x<height> <bytes>" per file.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import urllib.parse

MAX_W = 760
QUALITY = 82


def png_size(path) -> tuple:
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"make_webp: {path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def target_size(width: int, height: int) -> tuple:
    if width <= MAX_W:
        return width, height
    return MAX_W, round(height * MAX_W / width)


def picture(img_tag: str, webp_rel: str, width: int, height: int) -> str:
    """Wrap one <img ...> in <picture> with a WebP source; the img keeps its attributes and gains width and height."""
    tag, n = re.subn(r"<img\b", f'<img width="{width}" height="{height}"', img_tag, count=1)
    if n != 1:
        raise ValueError("not an <img> tag")
    return f'<picture><source type="image/webp" srcset="{urllib.parse.quote(webp_rel)}">{tag}</picture>'


def convert(src: pathlib.Path, dst: pathlib.Path, size: tuple):
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        with Image.open(src) as im:
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
            if im.size != size:
                im = im.resize(size, Image.LANCZOS)
            im.save(dst, "WEBP", quality=QUALITY, method=6)
        return "Pillow"
    exe = shutil.which("cwebp")
    if exe:
        subprocess.run([exe, "-q", str(QUALITY), "-m", "6", "-resize", str(size[0]), str(size[1]), str(src), "-o", str(dst)],
                       check=True, capture_output=True)
        return "cwebp"
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Write .webp copies beside PNG images.")
    ap.add_argument("images", nargs="+", type=pathlib.Path)
    a = ap.parse_args(argv)
    for src in a.images:
        dst = src.with_suffix(".webp")
        if dst.exists():
            print(f"{dst} exists; left alone")
            continue
        size = target_size(*png_size(src))
        used = convert(src, dst, size)
        if used is None:
            print("UNCHECKED: neither Pillow nor cwebp is available; no WebP was written")
            return 3
        print(f"{dst} {size[0]}x{size[1]} {dst.stat().st_size} ({used})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
