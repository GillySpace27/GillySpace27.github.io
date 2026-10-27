#!/usr/bin/env python3
"""Make the RHEF "unroll" teaching movie for gilly.space/rhef (RH-10).

  python3 tools/make_rhef_unroll.py [--out assets/sw] [--frames-only DIR]

A teaching visual, not a figure from the paper, and not solar data: the Sun in it is synthetic
(a disk, a corona that fades with height, a few streamers and some noise), made here from a fixed
seed so every run draws the same picture. The movie shows the idea of RHEF in four steps:

  1. the synthetic image at a linear brightness scale (a bright ball in a dark void);
  2. it unrolls into a strip: radius runs down, angle runs across, so each row is one ring;
  3. each row is replaced by the rank of its values within that row (average rank / n);
  4. the strip rolls back up into the disk.

Step 3 is the RHEF kernel on equal-width rings of the synthetic image, with no Upsilon curve. The
warp between disk and strip is an interpolation of sample positions, chosen to look smooth, not a
step of the method. RHEF output is a visualization, not a calibrated radiance.

Writes rhef-unroll.mp4 (H.264, needs ffmpeg on PATH) and rhef-unroll-poster.jpg into --out.
Needs numpy and Pillow. Exit 3 (UNCHECKED) when one of them, or ffmpeg, is missing.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

SIZE = 480          # frame side in pixels
FPS = 24
SEED = 20251102     # any fixed value; it only makes the synthetic noise repeatable
NBINS = 160         # equal-width rings out to the frame corner


def synthetic_sun(np, size=SIZE, seed=SEED):
    """A synthetic solar-looking image: disk, corona falling off with height, streamers, noise."""
    rng = np.random.default_rng(seed)
    c = (size - 1) / 2.0
    y, x = np.mgrid[0:size, 0:size]
    dx, dy = x - c, y - c
    r = np.hypot(dx, dy) / (size * 0.22)          # radius in units of the disk radius
    th = np.arctan2(dy, dx)
    # Rays: brightness that varies with angle (smoothed random values around the circle).
    k = np.ones(15) / 15.0
    ang = np.convolve(np.tile(rng.standard_normal(720), 3), k, mode="same")[720:1440]
    rays = 1 + 0.9 * ang[((th + np.pi) / (2 * np.pi) * 719).astype(int)]
    streamers = (1 + 1.5 * np.cos(th) ** 16 + 1.0 * np.cos(th + 0.4) ** 30) * np.clip(rays, 0.2, None)
    corona = np.where(r > 1, 0.6 * np.clip(r, 1, None) ** -7.0 * streamers, 0.0)
    # Disk: limb brightening, two bright active regions and soft blotches.
    blot = rng.standard_normal((size // 16, size // 16))
    blot = np.kron(blot, np.ones((16, 16)))[:size, :size]
    for axis in (0, 1):
        blot = np.apply_along_axis(lambda a: np.convolve(a, np.ones(17) / 17.0, mode="same"), axis, blot)
    ar = sum(1.5 * np.exp(-((dx - ox) ** 2 + (dy - oy) ** 2) / (2 * 12.0 ** 2))
             for ox, oy in ((-40, -25), (35, 30)))
    disk = np.where(r <= 1, (0.8 + 0.2 * np.clip(r, 0, 1) ** 2) * (1 + 0.5 * blot) + ar, 0.0)
    img = disk + corona
    return img + 1e-4 * rng.random((size, size))


def rank_rings(np, img, nbins=NBINS):
    """Rank each pixel among the pixels of its ring: average rank / n, in (0, 1]."""
    size = img.shape[0]
    c = (size - 1) / 2.0
    y, x = np.mgrid[0:size, 0:size]
    r = np.hypot(x - c, y - c)
    edges = np.linspace(0, r.max() + 1e-9, nbins + 1)
    idx = np.clip(np.searchsorted(edges, r, side="right") - 1, 0, nbins - 1).ravel()
    vals = img.ravel()
    out = np.empty_like(vals)
    order = np.lexsort((vals, idx))
    sidx, svals = idx[order], vals[order]
    start = 0
    n_all = len(order)
    while start < n_all:
        stop = start
        while stop < n_all and sidx[stop] == sidx[start]:
            stop += 1
        n = stop - start
        seg = svals[start:stop]
        ranks = np.arange(1, n + 1, dtype=float)
        # average ranks over runs of equal values
        i = 0
        while i < n:
            j = i
            while j + 1 < n and seg[j + 1] == seg[i]:
                j += 1
            if j > i:
                ranks[i:j + 1] = (i + 1 + j + 1) / 2.0
            i = j + 1
        out[order[start:stop]] = ranks / n
        start = stop
    return out.reshape(img.shape)


def warp(np, img, t):
    """Sample img on a grid between the frame (t=0) and the unrolled strip (t=1).

    In the strip, column u is the angle (0 to 2 pi from the left edge, starting at the top of
    the disk) and row v is the radius (0 at the top row to the frame corner at the bottom)."""
    size = img.shape[0]
    c = (size - 1) / 2.0
    v, u = np.mgrid[0:size, 0:size].astype(float)
    rmax = c * np.sqrt(2)
    th = u / size * 2 * np.pi - np.pi / 2
    rad = v / (size - 1) * rmax
    px, py = c + rad * np.cos(th), c + rad * np.sin(th)
    sx = (1 - t) * u + t * px
    sy = (1 - t) * v + t * py
    xi = np.clip(np.rint(sx).astype(int), 0, size - 1)
    yi = np.clip(np.rint(sy).astype(int), 0, size - 1)
    return img[yi, xi]


def smooth(t):
    return t * t * (3 - 2 * t)


def frames(np, raw, ranked):
    """Yield (array in [0, 1], caption) for each frame of the movie."""
    def hold(img, cap, n):
        for _ in range(n):
            yield img, cap
    lin = np.clip(raw / np.percentile(raw, 99.5), 0, 1)
    rk = ranked
    n = FPS
    yield from hold(lin, "1. The image, at a linear scale", int(1.5 * n))
    for k in range(2 * n):
        yield warp(np, lin, smooth(k / (2 * n - 1))), "2. Unroll: each row is one ring"
    strip_raw, strip_rank = warp(np, lin, 1.0), warp(np, rk, 1.0)
    yield from hold(strip_raw, "2. Unroll: each row is one ring", n // 2)
    rows = np.arange(SIZE)[:, None]
    for k in range(2 * n):
        cut = smooth(k / (2 * n - 1)) * SIZE
        yield np.where(rows < cut, strip_rank, strip_raw), "3. Rank each value within its row"
    yield from hold(strip_rank, "3. Rank each value within its row", n // 2)
    for k in range(2 * n):
        yield warp(np, rk, 1 - smooth(k / (2 * n - 1))), "4. Roll it back up"
    yield from hold(rk, "4. RHEF: every ring uses the full range", 2 * n)


def render(np, Image, ImageDraw, arr, caption):
    g = (np.clip(arr, 0, 1) * 255).astype("uint8")
    im = Image.fromarray(g, mode="L").convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, SIZE - 30, SIZE, SIZE], fill=(0, 0, 0))
    d.text((10, SIZE - 22), caption, fill=(240, 240, 240))
    d.text((SIZE - 190, 8), "synthetic Sun; teaching visual", fill=(200, 200, 200))
    return im


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="assets/sw", help="folder for rhef-unroll.mp4 and the poster")
    args = ap.parse_args(argv)
    try:
        import numpy as np
        from PIL import Image, ImageDraw
    except ImportError as e:
        print(f"UNCHECKED: {e}", file=sys.stderr)
        return 3
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("UNCHECKED: ffmpeg not on PATH", file=sys.stderr)
        return 3
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = synthetic_sun(np)
    ranked = rank_rings(np, raw)
    with tempfile.TemporaryDirectory() as tmp:
        count = 0
        for i, (arr, cap) in enumerate(frames(np, raw, ranked)):
            render(np, Image, ImageDraw, arr, cap).save(f"{tmp}/f{i:04d}.png")
            count += 1
        render(np, Image, ImageDraw, ranked, "RHEF: every ring uses the full range").save(
            out / "rhef-unroll-poster.jpg", quality=85)
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/f%04d.png",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "32", "-movflags", "+faststart",
               "-map_metadata", "-1", "-fflags", "+bitexact",
               "-metadata", "comment=RHEF unroll: a teaching visual on a synthetic Sun, not solar data",
               str(out / "rhef-unroll.mp4")]
        subprocess.run(cmd, check=True)
    print(f"{out / 'rhef-unroll.mp4'} {count} frames at {FPS} fps")
    print(f"{out / 'rhef-unroll-poster.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
