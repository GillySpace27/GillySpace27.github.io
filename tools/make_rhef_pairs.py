#!/usr/bin/env python3
"""Make a before/after RHEF image for a tab on gilly.space/rhef (RH-10).

  python3 tools/make_rhef_pairs.py NAME FILE.fits [--out assets/sw]

Writes <out>/rhef-<NAME>-compare.jpg, 1320 x 660: the left half is the map at a linear scale
(1st to 99.5th percentile), the right half is sunkit_image.radial.rhef(map) at its defaults,
nothing tuned. That is the "halves" layout assets/sun-compare.js reads. It also prints the
header values a caption needs (TELESCOP, INSTRUME, WAVELNTH, DATE-OBS), read from the file, so
the caption quotes the file and not memory. Never overwrites an existing image.

Needs sunpy, sunkit-image and Pillow (fastRHEF's requirements.lock has the first two); exit 3
(UNCHECKED) when they are missing. RHEF output is a visualization, not a calibrated radiance.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

HALF = 660


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name", help="lowercase tab name, e.g. kcor or punch")
    ap.add_argument("fits")
    ap.add_argument("--out", default="assets/sw")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z0-9]+", args.name):
        print("FAIL: NAME must be lowercase letters and digits (Pages is case-sensitive)", file=sys.stderr)
        return 2
    dest = pathlib.Path(args.out) / f"rhef-{args.name}-compare.jpg"
    if dest.exists():
        print(f"FAIL: {dest} exists; move it aside first", file=sys.stderr)
        return 2
    try:
        import numpy as np
        import sunpy.map
        from PIL import Image
        from sunkit_image.radial import rhef
        import sunkit_image
    except ImportError as e:
        print(f"UNCHECKED: {e}", file=sys.stderr)
        return 3

    m = sunpy.map.Map(args.fits)
    data = np.asarray(m.data, dtype=float)
    finite = data[np.isfinite(data)]
    lo, hi = np.percentile(finite, [1, 99.5])
    raw = np.clip((data - lo) / (hi - lo), 0, 1)
    out = np.asarray(rhef(m).data, dtype=float)
    out = np.clip(np.nan_to_num(out, nan=0.0), 0, 1)

    def half(a):
        im = Image.fromarray((np.flipud(a) * 255).astype("uint8"), mode="L")
        return im.resize((HALF, HALF), Image.LANCZOS)

    pair = Image.new("L", (2 * HALF, HALF))
    pair.paste(half(raw), (0, 0))
    pair.paste(half(out), (HALF, 0))
    dest.parent.mkdir(parents=True, exist_ok=True)
    pair.convert("RGB").save(dest, quality=85)
    print(f"{dest} written with sunkit-image {sunkit_image.__version__}")
    for key in ("TELESCOP", "INSTRUME", "DETECTOR", "WAVELNTH", "WAVEUNIT", "DATE-OBS"):
        print(f"  {key} = {m.meta.get(key.lower(), 'absent')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
