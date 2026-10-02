#!/usr/bin/env python3
"""Capture the Sun fixtures once, by read-only GET of public objects in the-sun-now.

Run from the repo root: python3 fixtures/sun/capture.py
Writes fixtures/sun/manifest/<id>.json and fixtures/sun/image_times.txt with the
bytes the bucket served, and one 8x8 grey PNG at every thumb and img1k key the
manifests name. Never writes to the bucket. Refuses to run when fixtures exist
unless --refresh is given (they are tracked; a refresh is a deliberate, separate
commit).
"""
from __future__ import annotations

import json
import pathlib
import re
import struct
import sys
import urllib.request
import zlib

BUCKET = "https://the-sun-now.s3.us-east-2.amazonaws.com/"
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "fixtures" / "sun"
SAFE_KEY = re.compile(r"[A-Za-z0-9_./-]+")


def product_ids() -> list[str]:
    sun = (ROOT / "sun.html").read_text(encoding="utf-8")
    m = re.search(r"const PRODUCTS = \[(.*?)\];", sun, re.S)
    if not m:
        raise SystemExit("PRODUCTS literal not found in sun.html; re-read it")
    return re.findall(r'\["([^"]+)",', m.group(1))


def get(key: str) -> bytes:
    with urllib.request.urlopen(BUCKET + key, timeout=30) as r:
        return r.read()


def placeholder_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    raw = b"".join(b"\x00" + b"\x80" * 8 for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def main() -> int:
    if (OUT / "manifest").exists() and "--refresh" not in sys.argv[1:]:
        print(f"{OUT / 'manifest'} exists; pass --refresh to overwrite", file=sys.stderr)
        return 1
    ids = product_ids()
    if len(ids) != 12:
        print(f"expected 12 PRODUCTS ids in sun.html, found {len(ids)}", file=sys.stderr)
        return 1
    png = placeholder_png()
    for pid in ids:
        body = get(f"manifest/{pid}.json")
        m = json.loads(body)
        dest = OUT / "manifest" / f"{pid}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        for field in ("thumb", "img1k"):
            key = m[field]
            if not SAFE_KEY.fullmatch(key) or ".." in key:
                print(f"refusing key {key!r} in manifest/{pid}.json", file=sys.stderr)
                return 1
            (OUT / key).parent.mkdir(parents=True, exist_ok=True)
            (OUT / key).write_bytes(png)
        print(f"captured manifest/{pid}.json updated={m.get('updated')}")
    (OUT / "image_times.txt").write_bytes(get("image_times.txt"))
    print("captured image_times.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
